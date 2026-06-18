import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, require_admin
from app.models import User
from app.schemas import (
    DeleteKnowledgeBaseResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
)
from app.services.knowledge_base_service import (
    create_knowledge_base,
    delete_knowledge_base,
    list_knowledge_bases,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def serialize_knowledge_base(knowledge_base) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=knowledge_base.id,
        name=knowledge_base.name,
        slug=knowledge_base.slug,
        collection_name=knowledge_base.collection_name,
        is_default=knowledge_base.is_default,
        created_at=knowledge_base.created_at.isoformat(),
    )


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse])
def get_knowledge_bases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[KnowledgeBaseResponse]:
    try:
        _ = current_user
        items = list_knowledge_bases(db)
        return [serialize_knowledge_base(item) for item in items]
    except Exception as exc:
        logger.exception("List knowledge bases failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse)
def post_knowledge_base(
    request: KnowledgeBaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> KnowledgeBaseResponse:
    try:
        _ = current_user
        knowledge_base = create_knowledge_base(db, request.name)
        return serialize_knowledge_base(knowledge_base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Create knowledge base failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete(
    "/knowledge-bases/{knowledge_base_id}",
    response_model=DeleteKnowledgeBaseResponse,
)
def remove_knowledge_base(
    knowledge_base_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DeleteKnowledgeBaseResponse:
    try:
        _ = current_user
        knowledge_base = delete_knowledge_base(db, knowledge_base_id)
        return DeleteKnowledgeBaseResponse(
            success=True,
            message=f"Knowledge base '{knowledge_base.name}' deleted successfully.",
            knowledge_base_id=knowledge_base_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Delete knowledge base failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
