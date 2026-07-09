from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.orm import Session

from app.core.config import settings
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
    route: str = "",
    task_intent: str = "",
    task_confidence: float = 0.0,
    agent_plan: list[str] | None = None,
    tool_calls: list[dict] | None = None,
    retrieval_quality: str = "",
    rewritten_question: str = "",
    sources: list[SourceChunk] | None = None,
    steps: list[str] | None = None,
    standalone_question: str = "",
) -> ChatMessage:
    message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=content,
        route=route,
        task_intent=task_intent,
        task_confidence=task_confidence,
        agent_plan=agent_plan or [],
        tool_calls=tool_calls or [],
        retrieval_quality=retrieval_quality,
        rewritten_question=rewritten_question,
        standalone_question=standalone_question,
        source_count=len(sources or []),
        sources=[source.model_dump() for source in sources or []],
        steps=steps or [],
    )
    db.add(message)
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(message)
    compress_session_memory_if_needed(db, session)
    return message


def list_session_messages(db: Session, session_id: str) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )


def list_recent_session_messages(
    db: Session,
    session_id: str,
    limit: int | None = None,
) -> list[ChatMessage]:
    message_limit = limit or settings.chat_history_recent_messages
    if message_limit <= 0:
        return []

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(message_limit)
        .all()
    )
    return list(reversed(messages))


def count_session_messages(db: Session, session_id: str) -> int:
    return db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()


def format_messages_for_memory(messages: list[ChatMessage]) -> str:
    lines: list[str] = []
    for message in messages:
        content = (message.content or "").strip()
        if not content:
            continue
        role = "用户" if message.role == "user" else "助手"
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def build_chat_history_context(
    session: ChatSession,
    recent_messages: list[ChatMessage],
) -> str:
    parts: list[str] = []
    if session.memory_summary:
        parts.append(f"历史摘要:\n{session.memory_summary.strip()}")

    recent_history = format_messages_for_memory(recent_messages)
    if recent_history:
        parts.append(f"最近对话:\n{recent_history}")

    return "\n\n".join(parts).strip()


def build_session_memory_context(db: Session, session: ChatSession) -> str:
    total_messages = count_session_messages(db, session.id)
    if total_messages <= settings.chat_memory_summary_start_messages:
        messages = list_session_messages(db, session.id)
        full_history = format_messages_for_memory(messages)
        return f"完整历史对话:\n{full_history}" if full_history else ""

    recent_messages = list_recent_session_messages(
        db,
        session.id,
        limit=settings.chat_memory_summary_keep_messages,
    )
    return build_chat_history_context(session, recent_messages)


def _messages_to_summarize(db: Session, session: ChatSession) -> list[ChatMessage]:
    keep_messages = max(settings.chat_memory_summary_keep_messages, 0)
    total_messages = (
        db.query(ChatMessage).filter(ChatMessage.session_id == session.id).count()
    )
    if total_messages <= settings.chat_memory_summary_start_messages:
        return []
    if total_messages <= keep_messages:
        return []

    recent_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(keep_messages)
        .all()
    )
    cutoff_id = min(message.id for message in recent_messages) if recent_messages else None
    if cutoff_id is None:
        return []

    query = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id,
        ChatMessage.id < cutoff_id,
    )
    if session.memory_summary_last_message_id is not None:
        query = query.filter(ChatMessage.id > session.memory_summary_last_message_id)

    return query.order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()


def summarize_conversation_messages(
    messages: list[ChatMessage],
    existing_summary: str | None,
) -> str:
    if not messages:
        return existing_summary or ""

    from app.services.rag_service import get_llm

    history_text = format_messages_for_memory(messages)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是会话记忆摘要器，负责把历史对话压缩成给问答助手使用的上下文摘要。"
                "只记录用户讨论过的话题、处理状态和明确约束，不要记录具体答案、长流程或详细规则。"
                "摘要用于后续 RAG 检索和回答理解，不替代知识库事实。"
                f"输出不超过 {settings.chat_memory_summary_max_chars} 个中文字符，只输出摘要本身。",
            ),
            (
                "human",
                "已有摘要:\n{existing_summary}\n\n"
                "本次新增历史对话:\n{history_text}\n\n"
                "请合并已有摘要和新增对话，去重后输出更新摘要。",
            ),
        ]
    )
    chain = prompt | get_llm()
    response = chain.invoke(
        {
            "existing_summary": existing_summary or "无",
            "history_text": history_text,
        }
    )
    summary = str(response.content).strip()
    if len(summary) > settings.chat_memory_summary_max_chars:
        summary = summary[: settings.chat_memory_summary_max_chars].rstrip()
    return summary


def compress_session_memory_if_needed(db: Session, session: ChatSession) -> None:
    if not settings.chat_memory_summary_enabled:
        return

    messages = _messages_to_summarize(db, session)
    if not messages:
        return

    try:
        summary = summarize_conversation_messages(messages, session.memory_summary)
    except Exception:
        return

    if not summary:
        return

    session.memory_summary = summary
    session.memory_summary_last_message_id = messages[-1].id
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
