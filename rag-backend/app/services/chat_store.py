from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatSession, KnowledgeBase, User
from app.schemas import SourceChunk


def build_session_title(question: str) -> str:
    title = question.strip().replace("\n", " ")
    if not title:
        return "新会话"
    if len(title) <= 40:
        return title
    return f"{title[:40]}..."


def create_chat_session(
    db: Session,
    user: User,
    knowledge_base: KnowledgeBase | None,
    question: str | None = None,
) -> ChatSession:
    session = ChatSession(
        user_id=user.id,
        knowledge_base_id=knowledge_base.id if knowledge_base else None,
        title=build_session_title(question or ""),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_chat_sessions(
    db: Session,
    current_user: User,
    offset: int = 0,
    limit: int | None = None,
) -> list[ChatSession]:
    query = db.query(ChatSession)
    if current_user.role != "admin":
        query = query.filter(ChatSession.user_id == current_user.id)
    query = query.order_by(ChatSession.updated_at.desc())
    if limit is not None:
        query = query.offset(offset).limit(limit)
    return query.all()


def count_chat_sessions(db: Session, current_user: User) -> int:
    query = db.query(ChatSession)
    if current_user.role != "admin":
        query = query.filter(ChatSession.user_id == current_user.id)
    return query.count()


def get_chat_session(
    db: Session,
    session_id: str,
    current_user: User | None = None,
) -> ChatSession | None:
    query = db.query(ChatSession).filter(ChatSession.id == session_id)
    if current_user is not None and current_user.role != "admin":
        query = query.filter(ChatSession.user_id == current_user.id)
    return query.first()


def rename_chat_session(db: Session, session: ChatSession, title: str) -> ChatSession:
    session.title = build_session_title(title)
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def delete_chat_session(db: Session, session: ChatSession) -> None:
    db.delete(session)
    db.commit()


def add_user_message(db: Session, session: ChatSession, content: str) -> ChatMessage:
    existing_message_count = (
        db.query(ChatMessage).filter(ChatMessage.session_id == session.id).count()
    )
    if existing_message_count == 0 and session.title == "新会话":
        session.title = build_session_title(content)

    message = ChatMessage(
        session_id=session.id,
        role="user",
        content=content,
    )
    db.add(message)
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(message)
    return message


def add_assistant_message(
    db: Session,
    session: ChatSession,
    *,
    content: str,
    route: str,
    retrieval_quality: str,
    rewritten_question: str,
    sources: list[SourceChunk],
    steps: list[str],
) -> ChatMessage:
    message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=content,
        route=route,
        retrieval_quality=retrieval_quality,
        rewritten_question=rewritten_question,
        source_count=len(sources),
        sources=[source.model_dump() for source in sources],
        steps=steps,
    )
    db.add(message)
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(message)
    return message


def list_session_messages(db: Session, session_id: str) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
