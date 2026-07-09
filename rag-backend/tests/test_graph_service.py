from __future__ import annotations

import pytest

from app.schemas import SourceChunk
from app.services.graph_service import (
    append_step,
    complete_question_with_history,
    extract_stream_text,
    is_direct_question,
    keyword_route,
    keyword_task_intent,
    max_source_score,
    normalize_task_intent,
    normalize_route,
    plan_for_intent,
    route_from_task_intent,
    serialize_value_for_span,
    shorten_text,
    ChatState,
)


class TestAppendStep:
    def test_empty_state(self):
        state: ChatState = {"question": "test"}  # type: ignore[typeddict-item]
        assert append_step(state, "step1") == ["step1"]

    def test_add_to_existing(self):
        state: ChatState = {"steps": ["step1"]}  # type: ignore[typeddict-item]
        assert append_step(state, "step2") == ["step1", "step2"]

    def test_does_not_mutate_original(self):
        state: ChatState = {"steps": ["a"]}  # type: ignore[typeddict-item]
        result = append_step(state, "b")
        assert state.get("steps") == ["a"]
        assert result == ["a", "b"]


class TestCompleteQuestionWithHistory:
    def test_no_history_uses_original_question(self):
        state: ChatState = {
            "question": "那它怎么部署？",
            "chat_history": "",
            "standalone_question": "",
            "rewritten_question": "",
            "top_k": 4,
            "collection_names": [],
            "route": "",
            "retrieval_quality": "",
            "sources": [],
            "answer": "",
            "steps": [],
        }

        result = complete_question_with_history(state)

        assert result["standalone_question"] == "那它怎么部署？"
        assert result["steps"] == ["complete_question_with_history"]

    def test_direct_question_skips_completion(self):
        state: ChatState = {
            "question": "你好",
            "chat_history": "用户: 这个项目怎么部署？",
            "standalone_question": "",
            "rewritten_question": "",
            "top_k": 4,
            "collection_names": [],
            "route": "",
            "retrieval_quality": "",
            "sources": [],
            "answer": "",
            "steps": [],
        }

        result = complete_question_with_history(state)

        assert result["standalone_question"] == "你好"


class TestMaxSourceScore:
    def test_empty(self):
        assert max_source_score([]) == 0.0

    def test_single(self):
        sources = [SourceChunk(content="x", source="a.txt", score=0.8)]
        assert max_source_score(sources) == 0.8

    def test_multiple_returns_max(self):
        sources = [
            SourceChunk(content="a", source="a.txt", score=0.3),
            SourceChunk(content="b", source="b.txt", score=0.9),
            SourceChunk(content="c", source="c.txt", score=0.5),
        ]
        assert max_source_score(sources) == 0.9

    def test_none_score_treated_as_zero(self):
        sources = [
            SourceChunk(content="a", source="a.txt", score=None),
            SourceChunk(content="b", source="b.txt", score=0.6),
        ]
        assert max_source_score(sources) == 0.6


class TestShortenText:
    def test_short_text_unchanged(self):
        assert shorten_text("hello") == "hello"

    def test_long_text_truncated(self):
        long_text = "x" * 2000
        result = shorten_text(long_text, limit=1000)
        assert len(result) == 1003  # 1000 chars + "..."
        assert result.endswith("...")

    def test_exact_limit(self):
        text = "a" * 1000
        assert shorten_text(text, limit=1000) == text


class TestIsDirectQuestion:
    def test_greeting(self):
        assert is_direct_question("你好") is True
        assert is_direct_question("Hello") is True
        assert is_direct_question("嗨") is True

    def test_thanks(self):
        assert is_direct_question("谢谢") is True
        assert is_direct_question("感谢") is True

    def test_identity(self):
        assert is_direct_question("你是谁") is True

    def test_knowledge_question(self):
        assert is_direct_question("什么是RAG") is False
        assert is_direct_question("请解释Milvus的原理") is False
        assert is_direct_question("这个项目支持哪些文档类型") is False

    def test_empty_question(self):
        assert is_direct_question("") is True
        assert is_direct_question("   ") is True


class TestKeywordRoute:
    def test_greeting_routes_to_direct(self):
        assert keyword_route("你好") == "direct"
        assert keyword_route("Hello") == "direct"

    def test_question_routes_to_rag(self):
        assert keyword_route("什么是RAG") == "rag"
        assert keyword_route("如何部署") == "rag"


class TestTaskIntentRouting:
    def test_greeting_is_chat_intent(self):
        assert keyword_task_intent("你好") == "chat"
        assert route_from_task_intent("chat") == "direct"

    def test_summarize_intent(self):
        assert keyword_task_intent("总结一下这份文档") == "summarize"
        assert route_from_task_intent("summarize") == "rag"

    def test_compare_intent(self):
        assert keyword_task_intent("对比两个方案的差异") == "compare"

    def test_extract_intent(self):
        assert keyword_task_intent("提取里面的考试要求清单") == "extract"

    def test_write_intent(self):
        assert keyword_task_intent("根据资料写一份报告") == "write"

    def test_normalize_aliases(self):
        assert normalize_task_intent("direct", "你好") == "chat"
        assert normalize_task_intent("rag", "什么是RAG") == "knowledge_qa"
        assert normalize_task_intent("knowledge-qa", "什么是RAG") == "knowledge_qa"


class TestAgentPlan:
    def test_agent_plan_for_knowledge_qa(self):
        plan = plan_for_intent("knowledge_qa")

        assert "检索知识库" in plan
        assert "基于资料生成回答" in plan

    def test_agent_plan_for_extract(self):
        plan = plan_for_intent("extract")

        assert any("抽取" in item for item in plan)


class TestNormalizeRoute:
    def test_rag_route(self):
        assert normalize_route("rag", "test question") == "rag"
        assert normalize_route("RAG", "test question") == "rag"

    def test_direct_route(self):
        assert normalize_route("direct", "test question") == "direct"
        assert normalize_route("DIRECT", "test question") == "direct"

    def test_unknown_falls_back_to_keyword(self):
        assert normalize_route("unknown", "你好") == "direct"
        assert normalize_route("unknown", "什么是RAG") == "rag"


class TestExtractStreamText:
    def test_string_content(self):
        chunk = type("Chunk", (), {"content": "hello"})()
        assert extract_stream_text(chunk) == "hello"

    def test_list_content(self):
        chunk = type("Chunk", (), {"content": [{"text": "hello"}, {"text": " world"}]})()
        assert extract_stream_text(chunk) == "hello world"

    def test_empty(self):
        chunk = type("Chunk", (), {"content": ""})()
        assert extract_stream_text(chunk) == ""

    def test_no_content_attr(self):
        chunk = type("Chunk", (), {})()
        assert extract_stream_text(chunk) == ""


class TestSerializeValueForSpan:
    def test_source_chunk(self):
        chunk = SourceChunk(content="x" * 300, source="test.txt", score=0.9)
        result = serialize_value_for_span(chunk)
        assert result["source"] == "test.txt"
        assert result["score"] == 0.9
        assert len(result["content_preview"]) == 200

    def test_list(self):
        result = serialize_value_for_span([1, "hello"])
        assert result == [1, "hello"]

    def test_string_truncated(self):
        result = serialize_value_for_span("x" * 2000)
        assert len(result) <= 1003

    def test_dict(self):
        result = serialize_value_for_span({"key": "value"})
        assert result == {"key": "value"}
