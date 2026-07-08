import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models import ChatMessage, ChatSession, User
from app.schemas import (
    DeleteSessionResponse,
    MessageResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionMessagesResponse,
    SessionResponse,
    SessionUpdateRequest,
    SourceChunk,
)
from app.services.chat_store import (
    count_chat_sessions,
    create_chat_session,
    delete_chat_session,
    get_chat_session,
    list_chat_sessions,
    list_session_messages,
    rename_chat_session,
)
from app.services.knowledge_base_service import resolve_knowledge_base

router = APIRouter()
logger = logging.getLogger(__name__)


def serialize_session(session: ChatSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        title=session.title,
        user_id=session.user_id,
        owner_username=session.user.username if session.user else None,
        knowledge_base_id=session.knowledge_base_id,
        knowledge_base_name=session.knowledge_base.name if session.knowledge_base else None,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        message_count=len(session.messages),
    )


def serialize_message(message: ChatMessage) -> MessageResponse:
    raw_sources = message.sources or []
    return MessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        route=message.route or "",
        task_intent=message.task_intent or "",
        task_confidence=message.task_confidence or 0.0,
        retrieval_quality=message.retrieval_quality or "",
        rewritten_question=message.rewritten_question or "",
        standalone_question=message.standalone_question or "",
        source_count=message.source_count or 0,
        sources=[SourceChunk(**item) for item in raw_sources],
        steps=list(message.steps or []),
        created_at=message.created_at.isoformat(),
    )


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    request: SessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    try:
        title = request.title.strip() if request.title else None
        knowledge_base = (
            resolve_knowledge_base(db, request.knowledge_base_id)
            if request.knowledge_base_id
            else None
        )
        session = create_chat_session(db, current_user, knowledge_base, title)
        return serialize_session(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Create session failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions", response_model=SessionListResponse)
def get_sessions(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionListResponse:
    try:
        total = count_chat_sessions(db, current_user)
        offset = (max(page, 1) - 1) * max(page_size, 1)
        sessions = list_chat_sessions(db, current_user, offset=offset, limit=page_size)
        return SessionListResponse(
            sessions=[serialize_session(item) for item in sessions],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.exception("List sessions failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionMessagesResponse:
    try:
        session = get_chat_session(db, session_id, current_user)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = list_session_messages(db, session_id)
        return SessionMessagesResponse(
            session=serialize_session(session),
            messages=[serialize_message(item) for item in messages],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("List session messages failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionResponse:
    try:
        session = get_chat_session(db, session_id, current_user)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        updated = rename_chat_session(db, session, request.title)
        return serialize_session(updated)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Update session failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeleteSessionResponse:
    try:
        session = get_chat_session(db, session_id, current_user)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        delete_chat_session(db, session)
        return DeleteSessionResponse(
            success=True,
            message="Session deleted successfully",
            session_id=session_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Delete session failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
