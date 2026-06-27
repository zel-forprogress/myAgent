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
)
from app.services.document_service import (
    count_document_records,
    delete_document_record,
    list_document_infos,
    sync_document_records,
    upsert_document_record,
)
from app.services.knowledge_base_service import resolve_knowledge_base
from app.services.rag_service import (
    detect_file_type,
    delete_document,
    extract_filename,
    get_document_character_count,
    get_document_uploaded_at,
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
        normalized_source = normalize_source(request.path)
        chunks, skipped = ingest_document(
            knowledge_base.collection_name, normalized_source,
            embedding_model=knowledge_base.embedding_model,
        )
        character_count, status = get_document_character_count(normalized_source)
        storage_metadata = get_stored_file_metadata(normalized_source)
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
            status=status,
            character_count=character_count,
            uploaded_at=storage_metadata.uploaded_at,
        )
        message = "Document ingested successfully"
        if chunks == 0 and skipped > 0:
            message = "Document already ingested; no new chunks added"
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
            status=status,
            character_count=character_count,
            uploaded_at=storage_metadata.uploaded_at,
            storage_provider=storage_metadata.provider,
            storage_bucket=storage_metadata.bucket,
            storage_object_key=storage_metadata.object_key,
            content_type=storage_metadata.content_type,
            file_size=storage_metadata.file_size,
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
        content = await file.read()
        stored_file = save_uploaded_file(
            file.filename or "",
            content,
            knowledge_base_slug=knowledge_base.slug,
        )
        chunks, skipped = ingest_document(
            knowledge_base.collection_name, stored_file.source,
            embedding_model=knowledge_base.embedding_model,
        )
        character_count, status = get_document_character_count(stored_file.source)
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
            chunks=chunks + skipped,
            status=status,
            character_count=character_count,
            uploaded_at=stored_file.uploaded_at,
        )

        message = "Uploaded document ingested successfully"
        if chunks == 0 and skipped > 0:
            message = "Uploaded document already ingested; no new chunks added"

        return IngestResponse(
            success=True,
            message=message,
            chunks=chunks,
            skipped=skipped,
            knowledge_base_id=knowledge_base.id,
            knowledge_base_name=knowledge_base.name,
            collection=knowledge_base.collection_name,
            stored_path=stored_file.source,
            filename=extract_filename(stored_file.source),
            file_type=detect_file_type(stored_file.source),
            status=status,
            character_count=character_count,
            uploaded_at=stored_file.uploaded_at,
            storage_provider=stored_file.provider,
            storage_bucket=stored_file.bucket,
            storage_object_key=stored_file.object_key,
            content_type=stored_file.content_type,
            file_size=stored_file.file_size,
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
        if deleted > 0:
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
        if deleted == 0:
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
