from collections import Counter
from hashlib import sha256
from io import BytesIO
from datetime import datetime
from pathlib import Path
import re
from typing import Iterable, List
from xml.etree import ElementTree
from zipfile import ZipFile

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pymilvus import DataType, MilvusClient
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import KnowledgeBase, KnowledgeBaseDocumentChunk
from app.schemas import DocumentInfo, SourceChunk
from app.services.observability import (
    extract_usage_details,
    start_generation,
    update_generation,
)
from app.services.storage_service import (
    StoredFileMetadata,
    detect_file_type,
    extract_filename,
    is_object_storage_source,
    normalize_source,
    read_file_bytes,
    resolve_document_path,
)


VALID_COLLECTION_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
KEYWORD_RE = re.compile(r"[A-Za-z0-9_./:-]+|[\u4e00-\u9fff]{2,}")


def is_valid_collection_name(collection_name: str) -> bool:
    return bool(collection_name) and VALID_COLLECTION_NAME_RE.fullmatch(collection_name) is not None


def get_embeddings(model: str | None = None) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=model or settings.embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        check_embedding_ctx_length=False,
        chunk_size=10,
    )


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.chat_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0,
    )


def get_milvus_client() -> MilvusClient:
    return MilvusClient(uri=settings.milvus_uri)


def ensure_vector_index(client: MilvusClient, collection_name: str) -> None:
    indexes = client.list_indexes(
        collection_name=collection_name,
        field_name="vector",
    )
    if indexes:
        return

    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )
    client.create_index(
        collection_name=collection_name,
        index_params=index_params,
    )


def ensure_collection(
    client: MilvusClient,
    collection_name: str,
    vector_dimension: int,
) -> None:
    if not is_valid_collection_name(collection_name):
        raise ValueError(f"Invalid Milvus collection name: {collection_name}")

    if client.has_collection(collection_name):
        ensure_vector_index(client, collection_name)
        client.load_collection(collection_name)
        return

    schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=vector_dimension)
    schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=1024)

    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )
    client.load_collection(collection_name)


def ensure_existing_collection_loaded(client: MilvusClient, collection_name: str) -> bool:
    if not is_valid_collection_name(collection_name):
        return False
    if not client.has_collection(collection_name):
        return False
    ensure_vector_index(client, collection_name)
    client.load_collection(collection_name)
    return True


def escape_milvus_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def source_variants(source: str) -> set[str]:
    normalized = normalize_source(source)
    return {
        source,
        normalized,
        source.replace("\\", "/"),
        source.replace("/", "\\"),
    }


def content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def sync_keyword_chunks(
    db: Session,
    *,
    knowledge_base_id: str,
    source: str,
    chunks: list[Document],
) -> None:
    normalized_source = normalize_source(source)
    variants = source_variants(normalized_source)

    db.query(KnowledgeBaseDocumentChunk).filter(
        KnowledgeBaseDocumentChunk.knowledge_base_id == knowledge_base_id,
        KnowledgeBaseDocumentChunk.source.in_(variants),
    ).delete(synchronize_session=False)

    for index, chunk in enumerate(chunks):
        text = chunk.page_content.strip()
        if not text:
            continue
        db.add(
            KnowledgeBaseDocumentChunk(
                knowledge_base_id=knowledge_base_id,
                source=chunk.metadata.get("source") or normalized_source,
                chunk_index=index,
                content=text,
                content_hash=content_hash(text),
            )
        )
    db.commit()


def delete_keyword_chunks(
    db: Session,
    *,
    knowledge_base_id: str,
    source: str,
) -> int:
    deleted = (
        db.query(KnowledgeBaseDocumentChunk)
        .filter(
            KnowledgeBaseDocumentChunk.knowledge_base_id == knowledge_base_id,
            KnowledgeBaseDocumentChunk.source.in_(source_variants(source)),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)


def extract_query_terms(question: str) -> list[str]:
    import jieba

    terms: list[str] = []
    seen_terms: set[str] = set()

    # Chinese: jieba segmentation
    for word in jieba.cut(question):
        word = word.strip()
        if len(word) >= 2 and word not in seen_terms:
            terms.append(word)
            seen_terms.add(word)
            if len(terms) >= 10:
                return terms

    # English / alphanumeric terms
    for term in KEYWORD_RE.findall(question.lower()):
        normalized_term = term.strip()
        if len(normalized_term) < 2 or normalized_term in seen_terms:
            continue
        if all("一" <= c <= "鿿" for c in normalized_term):
            continue
        terms.append(normalized_term)
        seen_terms.add(normalized_term)
        if len(terms) >= 10:
            break
    return terms


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def keyword_score(content: str, terms: list[str]) -> float:
    text = content.lower()
    raw_score = 0.0
    for term in terms:
        count = text.count(term)
        if count <= 0:
            continue
        raw_score += min(count, 5) * min(max(len(term), 2), 12)
    if raw_score <= 0:
        return 0.0
    return min(0.95, 0.45 + raw_score / 80)


def normalize_retrieval_score(score: float | None) -> float:
    if score is None:
        return 0.0
    return max(0.0, min(float(score), 1.0))


def calculate_rerank_score(source: SourceChunk) -> float:
    vector_score = normalize_retrieval_score(source.vector_score)
    keyword_score_value = normalize_retrieval_score(source.keyword_score)

    if vector_score > 0 and keyword_score_value > 0:
        return min(1.0, vector_score * 0.7 + keyword_score_value * 0.3 + 0.05)
    if vector_score > 0:
        return vector_score * 0.7
    return keyword_score_value * 0.3


def merge_source_scores(existing: SourceChunk, incoming: SourceChunk) -> SourceChunk:
    existing.vector_score = max(
        normalize_retrieval_score(existing.vector_score),
        normalize_retrieval_score(incoming.vector_score),
    ) or None
    existing.keyword_score = max(
        normalize_retrieval_score(existing.keyword_score),
        normalize_retrieval_score(incoming.keyword_score),
    ) or None

    if existing.vector_score and existing.keyword_score:
        existing.retrieval_type = "hybrid"
    elif existing.vector_score:
        existing.retrieval_type = "vector"
    elif existing.keyword_score:
        existing.retrieval_type = "keyword"

    existing.rerank_score = calculate_rerank_score(existing)
    existing.score = existing.rerank_score
    return existing


def get_existing_texts_by_sources(
    client: MilvusClient,
    collection_name: str,
    sources: Iterable[str],
) -> set[str]:
    existing_texts: set[str] = set()
    for source in sources:
        escaped_source = escape_milvus_string(source)
        rows = client.query(
            collection_name=collection_name,
            filter=f'source == "{escaped_source}"',
            output_fields=["text"],
            limit=10000,
        )
        existing_texts.update(row["text"] for row in rows)
    return existing_texts


def get_document_uploaded_at(source: str) -> str:
    try:
        metadata = get_source_metadata(source)
    except Exception:
        return ""
    return metadata.uploaded_at


def get_document_character_count(source: str) -> tuple[int, str]:
    """Returns (char_count, chunk_status).
    chunk_status: success | pending | failed"""
    try:
        text = extract_text_from_source(source).strip()
    except FileNotFoundError:
        return 0, "failed"
    except Exception:
        return 0, "failed"

    if not text:
        return 0, "failed"

    return len(text), "success"


def list_documents(collection_name: str) -> list[DocumentInfo]:
    client = get_milvus_client()
    if not ensure_existing_collection_loaded(client, collection_name):
        return []

    rows = client.query(
        collection_name=collection_name,
        filter="",
        output_fields=["source"],
        limit=10000,
    )
    source_counts = Counter(row["source"] for row in rows if row.get("source"))
    documents: list[DocumentInfo] = []
    for source, chunks in sorted(source_counts.items()):
        character_count, status = get_document_character_count(source)
        try:
            metadata = get_source_metadata(source)
        except Exception:
            metadata = StoredFileMetadata(
                source=source,
                provider="s3" if is_object_storage_source(source) else "local",
                bucket=None,
                object_key=None,
                content_type=None,
                file_size=0,
                uploaded_at="",
            )
        documents.append(
            DocumentInfo(
                filename=extract_filename(source),
                file_type=detect_file_type(source),
                source=source,
                chunks=chunks,
                status=status,
                character_count=character_count,
                uploaded_at=metadata.uploaded_at,
                storage_provider=metadata.provider,
                storage_bucket=metadata.bucket,
                storage_object_key=metadata.object_key,
                content_type=metadata.content_type,
                file_size=metadata.file_size,
            )
        )
    return documents


def collection_has_documents(collection_name: str) -> bool:
    if not is_valid_collection_name(collection_name):
        return False
    client = get_milvus_client()
    if not ensure_existing_collection_loaded(client, collection_name):
        return False

    rows = client.query(
        collection_name=collection_name,
        filter="",
        output_fields=["source"],
        limit=1,
    )
    return len(rows) > 0


def drop_collection_if_exists(collection_name: str) -> None:
    if not is_valid_collection_name(collection_name):
        return
    client = get_milvus_client()
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)


def delete_document(collection_name: str, source: str) -> int:
    client = get_milvus_client()
    if not ensure_existing_collection_loaded(client, collection_name):
        return 0

    deleted = 0
    for item in source_variants(source):
        escaped_source = escape_milvus_string(item)
        result = client.delete(
            collection_name=collection_name,
            filter=f'source == "{escaped_source}"',
        )
        deleted += result.get("delete_count", 0)

    if deleted > 0:
        client.flush(collection_name)
        client.load_collection(collection_name)

    return deleted


def extract_text_from_txt_or_md(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("TXT or Markdown files must be UTF-8 encoded.") from exc


def extract_text_from_pdf(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def extract_text_from_docx(content: bytes) -> str:
    with ZipFile(BytesIO(content)) as archive:
        try:
            xml_bytes = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError("DOCX file is missing word/document.xml.") from exc

    root = ElementTree.fromstring(xml_bytes)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []

    for paragraph in root.findall(".//w:p", namespace):
        runs = []
        for text_node in paragraph.findall(".//w:t", namespace):
            if text_node.text:
                runs.append(text_node.text)
        line = "".join(runs).strip()
        if line:
            paragraphs.append(line)

    return "\n\n".join(paragraphs)


def extract_text_from_bytes(content: bytes, source: str) -> str:
    suffix = Path(source).suffix.lower()
    if suffix in {".txt", ".md"}:
        return extract_text_from_txt_or_md(content)
    if suffix == ".pdf":
        return extract_text_from_pdf(content)
    if suffix == ".docx":
        return extract_text_from_docx(content)
    raise ValueError(f"Unsupported file type: {suffix}")


def extract_text_from_source(source: str) -> str:
    content = read_file_bytes(source)
    return extract_text_from_bytes(content, source)


def get_source_metadata(source: str) -> StoredFileMetadata:
    from app.services.storage_service import get_stored_file_metadata

    return get_stored_file_metadata(source)


def load_document_file(path: str) -> List[Document]:
    text = extract_text_from_source(path).strip()
    if not text:
        raise ValueError("Document content is empty after parsing.")

    source = normalize_source(path)
    return [
        Document(
            page_content=text,
            metadata={
                "source": source,
                "source_variants": source_variants(path),
            },
        )
    ]


def ingest_document(
    collection_name: str,
    path: str,
    embedding_model: str | None = None,
    db: Session | None = None,
    knowledge_base_id: str | None = None,
) -> tuple[int, int]:
    documents = load_document_file(path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.split_documents(documents)
    if not chunks:
        return 0, 0

    embeddings = get_embeddings(embedding_model)
    first_vector = embeddings.embed_query(chunks[0].page_content)

    client = get_milvus_client()
    ensure_collection(client, collection_name, vector_dimension=len(first_vector))

    variants = chunks[0].metadata.get("source_variants", set())
    existing_texts = get_existing_texts_by_sources(client, collection_name, variants)

    new_chunks: list[Document] = []
    seen_texts = set(existing_texts)
    for chunk in chunks:
        if chunk.page_content in seen_texts:
            continue
        new_chunks.append(chunk)
        seen_texts.add(chunk.page_content)

    skipped = len(chunks) - len(new_chunks)
    if not new_chunks:
        if db is not None and knowledge_base_id:
            sync_keyword_chunks(
                db,
                knowledge_base_id=knowledge_base_id,
                source=chunks[0].metadata.get("source") or path,
                chunks=chunks,
            )
        return 0, skipped

    texts = [chunk.page_content for chunk in new_chunks]
    vectors = embeddings.embed_documents(texts)
    rows = [
        {
            "vector": vector,
            "text": chunk.page_content,
            "source": chunk.metadata.get("source", ""),
        }
        for chunk, vector in zip(new_chunks, vectors)
    ]
    client.insert(collection_name=collection_name, data=rows)
    client.flush(collection_name)
    client.load_collection(collection_name)
    if db is not None and knowledge_base_id:
        sync_keyword_chunks(
            db,
            knowledge_base_id=knowledge_base_id,
            source=chunks[0].metadata.get("source") or path,
            chunks=chunks,
        )
    return len(new_chunks), skipped


def retrieve_sources(
    collection_name: str,
    question: str,
    top_k: int = 4,
    embedding_model: str | None = None,
) -> List[SourceChunk]:
    query_vector = get_embeddings(embedding_model).embed_query(question)
    client = get_milvus_client()
    ensure_collection(client, collection_name, vector_dimension=len(query_vector))

    search_results = client.search(
        collection_name=collection_name,
        data=[query_vector],
        limit=top_k,
        output_fields=["text", "source"],
        search_params={"metric_type": "COSINE"},
    )
    hits = search_results[0] if search_results else []
    sources: list[SourceChunk] = []
    for hit in hits:
        vector_score = normalize_retrieval_score(hit.get("distance", hit.get("score")))
        source = SourceChunk(
            content=hit["entity"]["text"],
            source=hit["entity"].get("source"),
            score=vector_score * 0.7,
            vector_score=vector_score,
            rerank_score=vector_score * 0.7,
            retrieval_type="vector",
        )
        sources.append(source)
    return sources


def retrieve_keyword_sources(
    collection_name: str,
    question: str,
    top_k: int = 4,
) -> List[SourceChunk]:
    terms = extract_query_terms(question)
    if not terms:
        return []

    filters = [
        KnowledgeBaseDocumentChunk.content.ilike(f"%{escape_like(term)}%", escape="\\")
        for term in terms
    ]
    if not filters:
        return []

    db = SessionLocal()
    try:
        rows = (
            db.query(KnowledgeBaseDocumentChunk)
            .join(KnowledgeBase, KnowledgeBaseDocumentChunk.knowledge_base_id == KnowledgeBase.id)
            .filter(KnowledgeBase.collection_name == collection_name)
            .filter(or_(*filters))
            .order_by(KnowledgeBaseDocumentChunk.id.desc())
            .limit(max(top_k * 5, 20))
            .all()
        )

        sources: list[SourceChunk] = []
        for row in rows:
            score = keyword_score(row.content, terms)
            if score <= 0:
                continue
            sources.append(
                SourceChunk(
                    content=row.content,
                    source=row.source,
                    score=score * 0.3,
                    keyword_score=score,
                    rerank_score=score * 0.3,
                    retrieval_type="keyword",
                )
            )
        sources.sort(key=lambda item: item.rerank_score or item.score or 0.0, reverse=True)
        return sources[:top_k]
    finally:
        db.close()


def retrieve_sources_multi(
    collection_names: list[str],
    question: str,
    top_k: int = 4,
    embedding_model: str | None = None,
) -> List[SourceChunk]:
    normalized_collection_names: list[str] = []
    seen_collection_names: set[str] = set()
    for collection_name in collection_names:
        if not collection_name or collection_name in seen_collection_names:
            continue
        normalized_collection_names.append(collection_name)
        seen_collection_names.add(collection_name)

    if not normalized_collection_names:
        return []

    candidate_k = max(top_k * 3, 12)
    merged_sources: list[SourceChunk] = []
    for collection_name in normalized_collection_names:
        merged_sources.extend(
            retrieve_sources(
                collection_name=collection_name,
                question=question,
                top_k=candidate_k,
                embedding_model=embedding_model,
            )
        )
        merged_sources.extend(
            retrieve_keyword_sources(
                collection_name=collection_name,
                question=question,
                top_k=candidate_k,
            )
        )

    deduplicated_by_chunk: dict[tuple[str, str], SourceChunk] = {}
    for source in merged_sources:
        key = (source.source or "", source.content)
        existing = deduplicated_by_chunk.get(key)
        if existing is None:
            source.rerank_score = calculate_rerank_score(source)
            source.score = source.rerank_score
            deduplicated_by_chunk[key] = source
            continue

        deduplicated_by_chunk[key] = merge_source_scores(existing, source)

    deduplicated_sources = list(deduplicated_by_chunk.values())
    deduplicated_sources.sort(key=lambda item: item.rerank_score or item.score or 0.0, reverse=True)
    return deduplicated_sources[:top_k]


def build_context(sources: List[SourceChunk]) -> str:
    return "\n\n".join(
        f"片段 {index + 1}:\n{source.content}"
        for index, source in enumerate(sources)
    )


def generate_answer_with_context(question: str, sources: List[SourceChunk]) -> str:
    context = build_context(sources)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是一个严谨的知识库问答助手。请只根据给定资料回答问题。"
                "如果资料中没有答案，请直接说资料中没有提到。",
            ),
            ("human", "资料:\n{context}\n\n问题: {question}"),
        ]
    )

    llm = get_llm()
    chain = prompt | llm

    generation_input = {
        "question": question,
        "context": context,
        "source_count": len(sources),
    }
    with start_generation(
        "qwen_rag_answer_call",
        input_data=generation_input,
        model=settings.chat_model,
        model_parameters={"temperature": 0},
        metadata={"node": "generate_rag_answer"},
    ) as generation:
        response = chain.invoke({"context": context, "question": question})
        update_generation(
            generation,
            output=response.content,
            usage_details=extract_usage_details(response),
        )

    return response.content


def chat_with_rag(
    collection_name: str,
    question: str,
    top_k: int = 4,
) -> tuple[str, List[SourceChunk]]:
    sources = retrieve_sources(collection_name=collection_name, question=question, top_k=top_k)
    answer = generate_answer_with_context(question, sources)
    return answer, sources
