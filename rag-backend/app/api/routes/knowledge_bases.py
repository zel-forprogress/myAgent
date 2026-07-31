import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models import User
from app.schemas import (
    DeleteKnowledgeBaseResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseRenameRequest,
    KnowledgeBaseResponse,
)
from app.services.knowledge_base_service import (
    count_documents_in_knowledge_base,
    create_knowledge_base,
    delete_knowledge_base,
    list_knowledge_bases,
    rename_knowledge_base,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def serialize_knowledge_base(knowledge_base) -> KnowledgeBaseResponse:
    doc_count = count_documents_in_knowledge_base(knowledge_base.collection_name)
    return KnowledgeBaseResponse(
        id=knowledge_base.id,
        name=knowledge_base.name,
        slug=knowledge_base.slug,
        collection_name=knowledge_base.collection_name,
        embedding_model=knowledge_base.embedding_model,
        is_default=knowledge_base.is_default,
        created_at=knowledge_base.created_at.isoformat(),
        document_count=doc_count,
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
    current_user: User = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    try:
        _ = current_user
        knowledge_base = create_knowledge_base(
            db,
            request.name,
            collection_name=request.collection_name,
            embedding_model=request.embedding_model,
        )
        return serialize_knowledge_base(knowledge_base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        detail = "该 Collection 名称已被使用，请换一个名称。"
        if "collection_name" in str(exc):
            detail = f"Collection 名称 '{request.collection_name}' 已被使用，请换一个名称。"
        raise HTTPException(status_code=409, detail=detail) from exc
    except Exception as exc:
        logger.exception("Create knowledge base failed")
        raise HTTPException(status_code=500, detail="创建知识库失败，请稍后重试。") from exc


@router.patch(
    "/knowledge-bases/{knowledge_base_id}",
    response_model=KnowledgeBaseResponse,
)
def rename_knowledge_base_route(
    knowledge_base_id: str,
    request: KnowledgeBaseRenameRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    try:
        _ = current_user
        knowledge_base = rename_knowledge_base(
            db,
            knowledge_base_id,
            request.name,
            embedding_model=request.embedding_model,
        )
        return serialize_knowledge_base(knowledge_base)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Rename knowledge base failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete(
    "/knowledge-bases/{knowledge_base_id}",
    response_model=DeleteKnowledgeBaseResponse,
)
def remove_knowledge_base(
    knowledge_base_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
