from __future__ import annotations

import hashlib
import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ChatSession, KnowledgeBase
from app.services.rag_service import collection_has_documents, drop_collection_if_exists
from app.services.storage_service import (
    build_knowledge_base_bucket_name,
    delete_bucket_if_empty,
    ensure_bucket_exists,
    is_object_storage_enabled,
)


def slugify_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    normalized = normalized.strip("-")
    if normalized:
        return normalized

    digest = hashlib.md5(name.strip().encode("utf-8")).hexdigest()[:8]
    return f"kb-{digest}"


def build_collection_name(slug: str) -> str:
    base = settings.milvus_collection
    if slug == "default":
        return base
    return f"{base}_{slug.replace('-', '_')}"


def list_knowledge_bases(db: Session) -> list[KnowledgeBase]:
    return db.query(KnowledgeBase).order_by(KnowledgeBase.created_at.asc()).all()


def get_knowledge_base(db: Session, knowledge_base_id: str) -> KnowledgeBase | None:
    return db.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_base_id).first()


def get_knowledge_base_by_name(db: Session, name: str) -> KnowledgeBase | None:
    return db.query(KnowledgeBase).filter(KnowledgeBase.name == name).first()


def create_knowledge_base(
    db: Session,
    name: str,
    collection_name: str | None = None,
    embedding_model: str | None = None,
) -> KnowledgeBase:
    trimmed_name = name.strip()
    if not trimmed_name:
        raise ValueError("Knowledge base name is required.")

    existing = get_knowledge_base_by_name(db, trimmed_name)
    if existing is not None:
        raise ValueError("Knowledge base name already exists.")

    slug = slugify_name(trimmed_name)
    base_slug = slug
    index = 1
    while db.query(KnowledgeBase).filter(KnowledgeBase.slug == slug).first() is not None:
        index += 1
        slug = f"{base_slug}-{index}"

    resolved_collection = (collection_name or "").strip() or build_collection_name(slug)
    resolved_embedding = (embedding_model or "").strip() or settings.embedding_model

    knowledge_base = KnowledgeBase(
        name=trimmed_name,
        slug=slug,
        collection_name=resolved_collection,
        embedding_model=resolved_embedding,
        is_default=False,
    )
    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)
    if is_object_storage_enabled():
        ensure_bucket_exists(build_knowledge_base_bucket_name(knowledge_base.slug))
    return knowledge_base


def delete_knowledge_base(db: Session, knowledge_base_id: str) -> KnowledgeBase:
    knowledge_base = get_knowledge_base(db, knowledge_base_id)
    if knowledge_base is None:
        raise ValueError("Knowledge base not found.")

    session_count = (
        db.query(ChatSession)
        .filter(ChatSession.knowledge_base_id == knowledge_base.id)
        .count()
    )
    if session_count > 0:
        raise ValueError("Knowledge base still has chat sessions. Please delete them first.")

    if collection_has_documents(knowledge_base.collection_name):
        raise ValueError("Knowledge base still has documents. Please delete them first.")

    drop_collection_if_exists(knowledge_base.collection_name)
    if is_object_storage_enabled():
        delete_bucket_if_empty(build_knowledge_base_bucket_name(knowledge_base.slug))
    db.delete(knowledge_base)
    db.commit()
    return knowledge_base


def resolve_knowledge_base(
    db: Session,
    knowledge_base_id: str | None,
) -> KnowledgeBase:
    if not knowledge_base_id:
        raise ValueError("Knowledge base id is required.")

    knowledge_base = get_knowledge_base(db, knowledge_base_id)
    if knowledge_base is None:
        raise ValueError("Knowledge base not found.")
    return knowledge_base


def resolve_knowledge_bases(
    db: Session,
    knowledge_base_ids: list[str] | None,
) -> list[KnowledgeBase]:
    available = list_knowledge_bases(db)
    if not knowledge_base_ids:
        return available

    available_map = {knowledge_base.id: knowledge_base for knowledge_base in available}
    resolved: list[KnowledgeBase] = []
    seen_ids: set[str] = set()

    for knowledge_base_id in knowledge_base_ids:
        if knowledge_base_id in seen_ids:
            continue
        knowledge_base = available_map.get(knowledge_base_id)
        if knowledge_base is None:
            raise ValueError(f"Knowledge base not found: {knowledge_base_id}")
        resolved.append(knowledge_base)
        seen_ids.add(knowledge_base_id)

    return resolved
