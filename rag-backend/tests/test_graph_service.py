from __future__ import annotations

import pytest

from app.schemas import SourceChunk
from app.services.graph_service import (
    append_step,
    extract_stream_text,
    is_direct_question,
    keyword_route,
    max_source_score,
    normalize_route,
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
