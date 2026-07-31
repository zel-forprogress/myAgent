import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models import ChatMessage, KnowledgeBase, KnowledgeBaseDocument, User
from app.services.rag_service import get_milvus_client
from app.services.settings_service import get_retrieval_min_score

router = APIRouter(prefix="/admin", tags=["admin-stats"])
logger = logging.getLogger(__name__)


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    rag_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.role == "assistant", ChatMessage.route == "rag")
        .all()
    )
    retrieval_min_score = get_retrieval_min_score(db)
    rag_total = len(rag_messages)
    hit_qualities = {"good", "rewritten_good"}
    retrieval_hits = sum(
        1
        for message in rag_messages
        if (message.source_count or 0) > 0
        and (message.retrieval_quality or "") in hit_qualities
    )
    no_context_count = sum(
        1
        for message in rag_messages
        if (message.retrieval_quality or "") in {"poor", "rewritten_poor"}
        or (message.source_count or 0) == 0
    )
    source_scores = []
    for message in rag_messages:
        source_scores.extend(
            float(source.get("score"))
            for source in message.sources or []
            if isinstance(source, dict)
            and isinstance(source.get("score"), (int, float))
            and float(source.get("score")) >= retrieval_min_score
        )

    recall_rate = retrieval_hits / rag_total if rag_total else 0.0
    average_score = sum(source_scores) / len(source_scores) if source_scores else 0.0

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
        "retrieval": {
            "chat_rag_total": rag_total,
            "recall_hits": retrieval_hits,
            "recall_rate": recall_rate,
            "no_context_count": no_context_count,
            "average_score": average_score,
            "min_score": retrieval_min_score,
        },
        "kb_breakdown": kb_breakdown,
    }
