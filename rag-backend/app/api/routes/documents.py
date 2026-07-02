import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_admin
from app.models import User
from app.schemas import (
    DeleteDocumentRequest,
    DeleteDocumentResponse,
    DocumentsResponse,
    IngestRequest,
    IngestResponse,
    IngestionTaskListResponse,
    IngestionTaskResponse,
)
from app.services.document_service import (
    count_document_records,
    delete_document_record,
    list_document_infos,
    sync_document_records,
    upsert_document_record,
)
from app.services.ingestion_task_service import (
    create_ingestion_task,
    get_ingestion_task,
    list_ingestion_tasks,
    serialize_ingestion_task,
    task_node,
    update_ingestion_task,
)
from app.services.knowledge_base_service import resolve_knowledge_base
from app.services.rag_service import (
    detect_file_type,
    delete_document,
    delete_keyword_chunks,
    extract_filename,
    get_document_character_count,
    get_document_uploaded_at,
    get_milvus_client,
    ingest_document,
    normalize_source,
)
from app.services.storage_service import (
    delete_stored_file,
    get_stored_file_metadata,
    is_managed_upload_source,
    save_uploaded_file,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: IngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> IngestResponse:
    try:
        _ = current_user
        knowledge_base = resolve_knowledge_base(db, request.knowledge_base_id)
        task = create_ingestion_task(
            db,
            knowledge_base=knowledge_base,
            task_type="register",
            filename=extract_filename(request.path),
            source=normalize_source(request.path),
            message="Register local document",
        )
        with task_node(db, task, "resolve_source", "Resolving local document source") as details:
            normalized_source = normalize_source(request.path)
            storage_metadata = get_stored_file_metadata(normalized_source)
            details.update(
                {
                    "source": normalized_source,
                    "storage_provider": storage_metadata.provider,
                    "file_size": storage_metadata.file_size,
                }
            )
        with task_node(db, task, "record_document", "Creating pending document record"):
            upsert_document_record(
                db,
                knowledge_base=knowledge_base,
                filename=extract_filename(normalized_source),
                file_type=detect_file_type(normalized_source),
                source=normalized_source,
                storage_provider=storage_metadata.provider,
                storage_bucket=storage_metadata.bucket,
                storage_object_key=storage_metadata.object_key,
                content_type=storage_metadata.content_type,
                file_size=storage_metadata.file_size,
                chunks=0,
                status="pending",
                character_count=0,
                uploaded_at=storage_metadata.uploaded_at,
            )
        update_ingestion_task(
            db,
            task,
            status="success",
            current_node="record_document",
            message="Document registered, ready for chunking",
            filename=extract_filename(normalized_source),
            source=normalized_source,
        )
        return IngestResponse(
            success=True,
            message="Document uploaded, ready for chunking",
            chunks=0,
            skipped=0,
            knowledge_base_id=knowledge_base.id,
            knowledge_base_name=knowledge_base.name,
            collection=knowledge_base.collection_name,
            stored_path=normalized_source,
            filename=extract_filename(normalized_source),
            file_type=detect_file_type(normalized_source),
            status="pending",
            character_count=0,
            uploaded_at=storage_metadata.uploaded_at,
            storage_provider=storage_metadata.provider,
            storage_bucket=storage_metadata.bucket,
            storage_object_key=storage_metadata.object_key,
            content_type=storage_metadata.content_type,
            file_size=storage_metadata.file_size,
            task_id=task.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Ingest failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ingest/upload", response_model=IngestResponse)
async def ingest_upload(
    knowledge_base_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> IngestResponse:
    try:
        _ = current_user
        knowledge_base = resolve_knowledge_base(db, knowledge_base_id)
        task = create_ingestion_task(
            db,
            knowledge_base=knowledge_base,
            task_type="upload",
            filename=file.filename or "",
            message="Upload document",
        )
        with task_node(db, task, "read_upload", "Reading uploaded file") as details:
            content = await file.read()
            details.update({"filename": file.filename or "", "bytes": len(content)})
        with task_node(db, task, "store_file", "Saving uploaded file") as details:
            stored_file = save_uploaded_file(
                file.filename or "",
                content,
                knowledge_base_slug=knowledge_base.slug,
            )
            details.update(
                {
                    "source": stored_file.source,
                    "provider": stored_file.provider,
                    "bucket": stored_file.bucket,
                    "object_key": stored_file.object_key,
                    "file_size": stored_file.file_size,
                }
            )
        with task_node(db, task, "record_document", "Creating pending document record"):
            upsert_document_record(
                db,
                knowledge_base=knowledge_base,
                filename=extract_filename(stored_file.source),
                file_type=detect_file_type(stored_file.source),
                source=normalize_source(stored_file.source),
                storage_provider=stored_file.provider,
                storage_bucket=stored_file.bucket,
                storage_object_key=stored_file.object_key,
                content_type=stored_file.content_type,
                file_size=stored_file.file_size,
                chunks=0,
                status="pending",
                character_count=0,
                uploaded_at=stored_file.uploaded_at,
            )
        update_ingestion_task(
            db,
            task,
            status="success",
            current_node="record_document",
            message="Document uploaded, ready for chunking",
            filename=extract_filename(stored_file.source),
            source=normalize_source(stored_file.source),
        )

        message = "Document uploaded, ready for chunking"

        return IngestResponse(
            success=True,
            message=message,
            chunks=0,
            skipped=0,
            knowledge_base_id=knowledge_base.id,
            knowledge_base_name=knowledge_base.name,
            collection=knowledge_base.collection_name,
            stored_path=stored_file.source,
            filename=extract_filename(stored_file.source),
            file_type=detect_file_type(stored_file.source),
            status="pending",
            character_count=0,
            uploaded_at=stored_file.uploaded_at,
            storage_provider=stored_file.provider,
            storage_bucket=stored_file.bucket,
            storage_object_key=stored_file.object_key,
            content_type=stored_file.content_type,
            file_size=stored_file.file_size,
            task_id=task.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Upload ingest failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/documents", response_model=DocumentsResponse)
def documents(
    knowledge_base_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DocumentsResponse:
    try:
        _ = current_user
        knowledge_base = resolve_knowledge_base(db, knowledge_base_id)
        sync_document_records(db, knowledge_base)
        total = count_document_records(db, knowledge_base.id)
        offset = (max(page, 1) - 1) * max(page_size, 1)
        return DocumentsResponse(
            knowledge_base_id=knowledge_base.id,
            knowledge_base_name=knowledge_base.name,
            collection=knowledge_base.collection_name,
            documents=list_document_infos(db, knowledge_base.id, offset=offset, limit=page_size),
            total=total,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("List documents failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ingestion/tasks", response_model=IngestionTaskListResponse)
def ingestion_tasks(
    knowledge_base_id: str | None = None,
    source: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> IngestionTaskListResponse:
    try:
        _ = current_user
        tasks, total = list_ingestion_tasks(
            db,
            knowledge_base_id=knowledge_base_id,
            source=source,
            limit=limit,
        )
        return IngestionTaskListResponse(
            tasks=[serialize_ingestion_task(task, include_logs=True) for task in tasks],
            total=total,
        )
    except Exception as exc:
        logger.exception("List ingestion tasks failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ingestion/tasks/{task_id}", response_model=IngestionTaskResponse)
def ingestion_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> IngestionTaskResponse:
    try:
        _ = current_user
        task = get_ingestion_task(db, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Ingestion task not found")
        return serialize_ingestion_task(task, include_logs=True)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Get ingestion task failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/documents/chunk", response_model=IngestResponse)
def chunk_document(
    request: DeleteDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> IngestResponse:
    try:
        _ = current_user
        knowledge_base = resolve_knowledge_base(db, request.knowledge_base_id)
        normalized_source = normalize_source(request.source)
        task = create_ingestion_task(
            db,
            knowledge_base=knowledge_base,
            task_type="chunk",
            filename=extract_filename(normalized_source),
            source=normalized_source,
            message="Chunk document",
        )
        with task_node(db, task, "inspect_document", "Inspecting document text") as details:
            character_count, _ = get_document_character_count(normalized_source)
            storage_metadata = get_stored_file_metadata(normalized_source)
            details.update(
                {
                    "character_count": character_count,
                    "storage_provider": storage_metadata.provider,
                    "file_size": storage_metadata.file_size,
                }
            )
        with task_node(db, task, "chunk_embed_index", "Chunking, embedding, and indexing") as details:
            chunks, skipped = ingest_document(
                knowledge_base.collection_name, normalized_source,
                embedding_model=knowledge_base.embedding_model,
                db=db,
                knowledge_base_id=knowledge_base.id,
            )
            details.update({"chunks": chunks, "skipped": skipped})
        chunk_status = "success" if chunks > 0 or skipped > 0 else "failed"
        with task_node(db, task, "update_document_record", "Updating document record"):
            upsert_document_record(
                db,
                knowledge_base=knowledge_base,
                filename=extract_filename(normalized_source),
                file_type=detect_file_type(normalized_source),
                source=normalized_source,
                storage_provider=storage_metadata.provider,
                storage_bucket=storage_metadata.bucket,
                storage_object_key=storage_metadata.object_key,
                content_type=storage_metadata.content_type,
                file_size=storage_metadata.file_size,
                chunks=chunks + skipped,
                status=chunk_status,
                character_count=character_count,
                uploaded_at=storage_metadata.uploaded_at,
            )
        message = "Document chunked successfully"
        if chunks == 0 and skipped > 0:
            message = "Document already chunked; no new chunks added"
        if chunk_status == "failed":
            message = "Document chunking produced no chunks"
        update_ingestion_task(
            db,
            task,
            status=chunk_status,
            current_node="update_document_record",
            message=message,
            chunks=chunks,
            skipped=skipped,
            error=message if chunk_status == "failed" else None,
        )
        return IngestResponse(
            success=True,
            message=message,
            chunks=chunks,
            skipped=skipped,
            knowledge_base_id=knowledge_base.id,
            knowledge_base_name=knowledge_base.name,
            collection=knowledge_base.collection_name,
            stored_path=normalized_source,
            filename=extract_filename(normalized_source),
            file_type=detect_file_type(normalized_source),
            status=chunk_status,
            character_count=character_count,
            uploaded_at=storage_metadata.uploaded_at,
            storage_provider=storage_metadata.provider,
            storage_bucket=storage_metadata.bucket,
            storage_object_key=storage_metadata.object_key,
            content_type=storage_metadata.content_type,
            file_size=storage_metadata.file_size,
            task_id=task.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Chunk document failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/documents/chunks")
def document_chunks(
    knowledge_base_id: str,
    source: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        _ = current_user
        knowledge_base = resolve_knowledge_base(db, knowledge_base_id)
        client = get_milvus_client()
        if not client.has_collection(knowledge_base.collection_name):
            return {"chunks": [], "source": source}
        client.load_collection(knowledge_base.collection_name)
        escaped = source.replace("\\", "\\\\").replace('"', '\\"')
        rows = client.query(
            collection_name=knowledge_base.collection_name,
            filter=f'source == "{escaped}"',
            output_fields=["text", "source"],
            limit=10000,
        )
        chunks = [
            {
                "id": row.get("id"),
                "text": row.get("text", ""),
                "source": row.get("source", ""),
            }
            for row in rows
        ]
        return {"chunks": chunks, "source": source, "total": len(chunks)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/documents", response_model=DeleteDocumentResponse)
def delete_documents(
    request: DeleteDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DeleteDocumentResponse:
    try:
        _ = current_user
        knowledge_base = resolve_knowledge_base(db, request.knowledge_base_id)
        deleted = delete_document(knowledge_base.collection_name, request.source)
        deleted_keyword_chunks = delete_keyword_chunks(
            db,
            knowledge_base_id=knowledge_base.id,
            source=request.source,
        )
        if deleted > 0 or deleted_keyword_chunks > 0:
            deleted_record = delete_document_record(
                db,
                knowledge_base_id=knowledge_base.id,
                source=request.source,
            )
            if deleted_record and (
                deleted_record.storage_provider == "s3"
                or is_managed_upload_source(deleted_record.source)
            ):
                delete_stored_file(deleted_record.source)
        message = "Document deleted successfully"
        if deleted == 0 and deleted_keyword_chunks == 0:
            message = "Document not found"
        return DeleteDocumentResponse(
            success=True,
            message=message,
            source=request.source,
            deleted=deleted,
            knowledge_base_id=knowledge_base.id,
            knowledge_base_name=knowledge_base.name,
            collection=knowledge_base.collection_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Delete document failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
