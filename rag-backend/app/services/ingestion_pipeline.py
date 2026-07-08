from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import IngestionTask
from app.services.document_service import upsert_document_record
from app.services.ingestion_task_service import task_node, update_ingestion_task
from app.services.knowledge_base_service import resolve_knowledge_base
from app.services.rag_service import (
    detect_file_type,
    extract_filename,
    get_document_character_count,
    ingest_document,
)
from app.services.storage_service import get_stored_file_metadata


class IngestionTaskCancelled(Exception):
    pass


def ensure_task_active(db: Session, task: IngestionTask) -> None:
    db.refresh(task)
    if task.status == "cancelled":
        raise IngestionTaskCancelled("Ingestion task was cancelled.")


def run_ingestion_pipeline(db: Session, task: IngestionTask) -> IngestionTask:
    knowledge_base = resolve_knowledge_base(db, task.knowledge_base_id)
    source = task.source
    if not source:
        raise ValueError("Ingestion task source is empty.")

    ensure_task_active(db, task)
    with task_node(db, task, "inspect_document", "Inspecting document text") as details:
        character_count, _ = get_document_character_count(source)
        storage_metadata = get_stored_file_metadata(source)
        details.update(
            {
                "character_count": character_count,
                "storage_provider": storage_metadata.provider,
                "file_size": storage_metadata.file_size,
            }
        )

    ensure_task_active(db, task)
    with task_node(db, task, "chunk_embed_index", "Chunking, embedding, and indexing") as details:
        chunks, skipped = ingest_document(
            knowledge_base.collection_name,
            source,
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
            filename=extract_filename(source),
            file_type=detect_file_type(source),
            source=source,
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

    message = "Document indexed successfully"
    if chunks == 0 and skipped > 0:
        message = "Document already indexed; no new chunks added"
    if chunk_status == "failed":
        message = "Document indexing produced no chunks"

    ensure_task_active(db, task)
    return update_ingestion_task(
        db,
        task,
        status=chunk_status,
        current_node="finalize_task",
        message=message,
        chunks=chunks,
        skipped=skipped,
        error=message if chunk_status == "failed" else "",
    )
