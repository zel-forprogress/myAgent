import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_admin
from app.models import KnowledgeBase, KnowledgeBaseDocument, User
from app.services.rag_service import get_milvus_client

router = APIRouter(prefix="/admin", tags=["admin-stats"])
logger = logging.getLogger(__name__)


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    kb_count = db.query(KnowledgeBase).count()
    user_count = db.query(User).count()

    docs = db.query(KnowledgeBaseDocument).all()
    total_chunks = sum(d.chunks or 0 for d in docs)
    total_files = len(docs)
    total_size = sum(d.file_size or 0 for d in docs)
    indexed_count = sum(1 for d in docs if d.status == "success")
    pending_count = sum(1 for d in docs if d.status == "pending")
    failed_count = sum(1 for d in docs if d.status == "failed")

    try:
        client = get_milvus_client()
        collections = client.list_collections()
        total_vectors = 0
        for col in collections:
            try:
                client.load_collection(col)
                stats = client.get_collection_stats(col)
                total_vectors += stats.get("row_count", 0)
            except Exception:
                pass
    except Exception:
        collections = []
        total_vectors = 0

    kbs = db.query(KnowledgeBase).all()
    kb_breakdown = []
    for kb in kbs:
        kb_docs = [d for d in docs if d.knowledge_base_id == kb.id]
        kb_breakdown.append({
            "name": kb.name,
            "collection": kb.collection_name,
            "documents": len(kb_docs),
            "chunks": sum(d.chunks or 0 for d in kb_docs),
            "size": sum(d.file_size or 0 for d in kb_docs),
        })

    return {
        "knowledge_bases": kb_count,
        "users": user_count,
        "documents": {
            "total": total_files, "chunks": total_chunks, "size": total_size,
            "indexed": indexed_count, "pending": pending_count, "failed": failed_count,
        },
        "milvus": {"collections": len(collections), "vectors": total_vectors},
        "kb_breakdown": kb_breakdown,
    }
