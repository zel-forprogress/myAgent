from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import KnowledgeBase, KnowledgeBaseDocument
from app.schemas import DocumentInfo
from app.services.rag_service import list_documents as list_documents_from_collection


def _parse_uploaded_at(value: str) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.utcnow()


def _to_schema(record: KnowledgeBaseDocument) -> DocumentInfo:
    return DocumentInfo(
        filename=record.filename,
        file_type=record.file_type,
        source=record.source,
        chunks=record.chunks,
        status=record.status,
        character_count=record.character_count,
        uploaded_at=record.uploaded_at.isoformat() if record.uploaded_at else "",
        storage_provider=record.storage_provider,
        storage_bucket=record.storage_bucket,
        storage_object_key=record.storage_object_key,
        content_type=record.content_type,
        file_size=record.file_size,
    )


def upsert_document_record(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    filename: str,
    file_type: str,
    source: str,
    storage_provider: str,
    storage_bucket: str | None,
    storage_object_key: str | None,
    content_type: str | None,
    file_size: int,
    chunks: int,
    status: str,
    character_count: int,
    uploaded_at: str,
) -> KnowledgeBaseDocument:
    record = (
        db.query(KnowledgeBaseDocument)
        .filter(
            KnowledgeBaseDocument.knowledge_base_id == knowledge_base.id,
            KnowledgeBaseDocument.source == source,
        )
        .first()
    )

    if record is None:
        record = KnowledgeBaseDocument(
            knowledge_base_id=knowledge_base.id,
            filename=filename,
            file_type=file_type,
            source=source,
        )
        db.add(record)

    record.filename = filename
    record.file_type = file_type
    record.storage_provider = storage_provider
    record.storage_bucket = storage_bucket
    record.storage_object_key = storage_object_key
    record.content_type = content_type
    record.file_size = file_size
    record.chunks = chunks
    record.status = status
    record.character_count = character_count
    record.uploaded_at = _parse_uploaded_at(uploaded_at)

    db.commit()
    db.refresh(record)
    return record


def sync_document_records(db: Session, knowledge_base: KnowledgeBase) -> list[KnowledgeBaseDocument]:
    discovered_documents = list_documents_from_collection(knowledge_base.collection_name)
    seen_sources = set()

    for document in discovered_documents:
        seen_sources.add(document.source)
        upsert_document_record(
            db,
            knowledge_base=knowledge_base,
            filename=document.filename,
            file_type=document.file_type,
            source=document.source,
            storage_provider=document.storage_provider,
            storage_bucket=document.storage_bucket,
            storage_object_key=document.storage_object_key,
            content_type=document.content_type,
            file_size=document.file_size,
            chunks=document.chunks,
            status=document.status,
            character_count=document.character_count,
            uploaded_at=document.uploaded_at,
        )

    stale_records = (
        db.query(KnowledgeBaseDocument)
        .filter(KnowledgeBaseDocument.knowledge_base_id == knowledge_base.id)
        .all()
    )
    stale_deleted = False
    for record in stale_records:
        if record.source not in seen_sources:
            db.delete(record)
            stale_deleted = True

    if stale_deleted:
        db.commit()

    return list_document_records(db, knowledge_base.id)


def list_document_records(db: Session, knowledge_base_id: str) -> list[KnowledgeBaseDocument]:
    return (
        db.query(KnowledgeBaseDocument)
        .filter(KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id)
        .order_by(
            KnowledgeBaseDocument.uploaded_at.desc(),
            KnowledgeBaseDocument.updated_at.desc(),
            KnowledgeBaseDocument.id.desc(),
        )
        .all()
    )


def list_document_infos(db: Session, knowledge_base_id: str) -> list[DocumentInfo]:
    return [_to_schema(record) for record in list_document_records(db, knowledge_base_id)]


def delete_document_record(
    db: Session,
    *,
    knowledge_base_id: str,
    source: str,
) -> KnowledgeBaseDocument | None:
    record = (
        db.query(KnowledgeBaseDocument)
        .filter(
            KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,
            KnowledgeBaseDocument.source == source,
        )
        .first()
    )
    if record is not None:
        db.expunge(record)
        persistent_record = record
        record = (
            db.query(KnowledgeBaseDocument)
            .filter(
                KnowledgeBaseDocument.knowledge_base_id == knowledge_base_id,
                KnowledgeBaseDocument.source == source,
            )
            .first()
        )
        db.delete(record)
        db.commit()
        return persistent_record
    return None
