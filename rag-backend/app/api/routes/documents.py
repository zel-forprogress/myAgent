import logging
from time import perf_counter

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
    RetrievalTestRequest,
    RetrievalTestResponse,
)
from app.services.document_service import (
    count_document_records,
    delete_document_record,
    list_document_infos,
    sync_document_records,
    update_document_record_status,
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
from app.services.ingestion_queue_service import enqueue_ingestion_task, revoke_ingestion_task
from app.services.knowledge_base_service import resolve_knowledge_base
from app.services.rag_service import (
    detect_file_type,
    delete_document,
    delete_keyword_chunks,
    extract_filename,
    get_milvus_client,
    normalize_source,
    retrieve_sources_multi,
)
from app.services.storage_service import (
    delete_stored_file,
    get_stored_file_metadata,
    is_managed_upload_source,
    save_uploaded_file,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/retrieval/test", response_model=RetrievalTestResponse)
def test_retrieval(
    request: RetrievalTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> RetrievalTestResponse:
    try:
        _ = current_user
        question = request.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")

        knowledge_bases = resolve_knowledge_bases(db, request.knowledge_base_ids)
        started = perf_counter()
        sources = retrieve_sources_multi(
            collection_names=[item.collection_name for item in knowledge_bases],
            question=question,
            top_k=request.top_k,
        )
        duration_ms = int((perf_counter() - started) * 1000)
        return RetrievalTestResponse(
            question=question,
            top_k=request.top_k,
            knowledge_base_ids=[item.id for item in knowledge_bases],
            knowledge_base_names=[item.name for item in knowledge_bases],
            collection_names=[item.collection_name for item in knowledge_bases],
            duration_ms=duration_ms,
            source_count=len(sources),
            sources=sources,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Retrieval test failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
            status="pending",
            current_node="record_document",
            message="Document registered, waiting for indexing",
            filename=extract_filename(normalized_source),
            source=normalized_source,
        )
        task = enqueue_ingestion_task(db, task)
        return IngestResponse(
            success=True,
            message=task.message or "Document queued for indexing",
            chunks=0,
            skipped=0,
            knowledge_base_id=knowledge_base.id,
            knowledge_base_name=knowledge_base.name,
            collection=knowledge_base.collection_name,
            stored_path=normalized_source,
            filename=extract_filename(normalized_source),
            file_type=detect_file_type(normalized_source),
            status=task.status,
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
            status="pending",
            current_node="record_document",
            message="Document uploaded, waiting for indexing",
            filename=extract_filename(stored_file.source),
            source=normalize_source(stored_file.source),
        )

        task = enqueue_ingestion_task(db, task)
        message = task.message or "Document queued for indexing"

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
            status=task.status,
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


@router.post("/ingestion/tasks/{task_id}/retry", response_model=IngestionTaskResponse)
def retry_ingestion_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> IngestionTaskResponse:
    try:
        _ = current_user
        task = get_ingestion_task(db, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Ingestion task not found")
        if task.status not in {"failed"}:
            raise HTTPException(status_code=400, detail="Only failed ingestion tasks can be retried")
        update_ingestion_task(
            db,
            task,
            status="pending",
            current_node="retry",
            message="Retry requested",
            chunks=0,
            skipped=0,
            retry_count=0,
            error="",
        )
        task = enqueue_ingestion_task(db, task)
        return serialize_ingestion_task(task, include_logs=True)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Retry ingestion task failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ingestion/tasks/{task_id}/cancel", response_model=IngestionTaskResponse)
def cancel_ingestion_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> IngestionTaskResponse:
    try:
        _ = current_user
        task = get_ingestion_task(db, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Ingestion task not found")
        if task.status not in {"pending", "queued", "running", "retrying"}:
            raise HTTPException(
                status_code=400,
                detail="Only pending, queued, running, or retrying ingestion tasks can be cancelled",
            )

        revoke_ingestion_task(db, task)
        update_document_record_status(
            db,
            knowledge_base_id=task.knowledge_base_id,
            source=task.source,
            status="cancelled",
        )
        task = update_ingestion_task(
            db,
            task,
            status="cancelled",
            current_node="cancel",
            message="Ingestion task cancelled",
            error="",
        )
        return serialize_ingestion_task(task, include_logs=True)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Cancel ingestion task failed")
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
            message="Re-index document",
        )
        update_ingestion_task(
            db,
            task,
            status="pending",
            current_node="prepare_indexing",
            message="Document indexing task created",
        )
        task = enqueue_ingestion_task(db, task)
        return IngestResponse(
            success=True,
            message=task.message or "Document queued for indexing",
            chunks=0,
            skipped=0,
            knowledge_base_id=knowledge_base.id,
            knowledge_base_name=knowledge_base.name,
            collection=knowledge_base.collection_name,
            stored_path=normalized_source,
            filename=extract_filename(normalized_source),
            file_type=detect_file_type(normalized_source),
            status=task.status,
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
