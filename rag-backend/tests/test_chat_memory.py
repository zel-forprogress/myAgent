from __future__ import annotations

from app.models import ChatMessage, ChatSession
from app.services.chat_store import build_chat_history_context, format_messages_for_memory


class TestFormatMessagesForMemory:
    def test_formats_user_and_assistant_messages(self):
        messages = [
            ChatMessage(role="user", content="这个项目是什么？"),
            ChatMessage(role="assistant", content="这是一个 RAG Agent 项目。"),
        ]

        result = format_messages_for_memory(messages)

        assert "用户: 这个项目是什么？" in result
        assert "助手: 这是一个 RAG Agent 项目。" in result

    def test_skips_empty_messages(self):
        messages = [
            ChatMessage(role="user", content=""),
            ChatMessage(role="assistant", content="有效回答"),
        ]

        assert format_messages_for_memory(messages) == "助手: 有效回答"


class TestBuildChatHistoryContext:
    def test_combines_summary_and_recent_messages(self):
        session = ChatSession(
            id="session-1",
            title="test",
            memory_summary="用户咨询了项目架构。",
        )
        messages = [ChatMessage(role="user", content="那它怎么部署？")]

        result = build_chat_history_context(session, messages)

        assert "历史摘要:" in result
        assert "用户咨询了项目架构。" in result
        assert "最近对话:" in result
        assert "用户: 那它怎么部署？" in result

    def test_returns_recent_messages_without_summary(self):
        session = ChatSession(id="session-1", title="test")
        messages = [ChatMessage(role="user", content="继续说")]

        result = build_chat_history_context(session, messages)

        assert "历史摘要:" not in result
        assert result == "最近对话:\n用户: 继续说"
