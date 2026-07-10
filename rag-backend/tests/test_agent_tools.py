from app.schemas import SourceChunk
from app.services.agent_tools import (
    agent_tool_registry,
    diagnose_retrieval_quality,
    inspect_sources,
    summarize_sources,
)


class TestAgentToolRegistry:
    def test_lists_registered_tools(self):
        tools = agent_tool_registry.list_tools()
        names = {tool["name"] for tool in tools}

        assert "search_knowledge_base" in names
        assert "inspect_sources" in names
        assert "guard_no_context" in names


class TestSourceDiagnostics:
    def test_summarize_sources_keeps_small_tool_output(self):
        sources = [
            SourceChunk(
                content="x" * 300,
                source="doc.txt",
                score=0.8,
                vector_score=0.7,
                keyword_score=0.4,
                rerank_score=0.9,
                retrieval_type="hybrid",
            )
        ]

        summary = summarize_sources(sources)

        assert summary["source_count"] == 1
        assert summary["max_score"] == 0.8
        assert summary["rerank_applied"] is True
        assert summary["retrieval_types"] == ["hybrid"]
        assert len(summary["top_sources"][0]["preview"]) == 160

    def test_diagnose_good_sources(self):
        sources = [SourceChunk(content="ok", source="doc.txt", score=0.7)]

        diagnosis = diagnose_retrieval_quality(sources, min_required_score=0.45)

        assert diagnosis["retrieval_quality"] == "good"
        assert diagnosis["reason"] == "enough_context"
        assert diagnosis["recommendation"] == "generate_answer"

    def test_diagnose_low_score_sources(self):
        sources = [SourceChunk(content="weak", source="doc.txt", score=0.2)]

        diagnosis = diagnose_retrieval_quality(sources, min_required_score=0.45)

        assert diagnosis["retrieval_quality"] == "poor"
        assert diagnosis["reason"] == "score_below_threshold"
        assert diagnosis["recommendation"] == "rewrite_query"

    def test_inspect_sources_returns_tool_call_shape(self):
        execution = inspect_sources(
            sources=[SourceChunk(content="ok", source="doc.txt", score=0.7)]
        )

        tool_call = execution.to_tool_call()

        assert tool_call["name"] == "inspect_sources"
        assert tool_call["status"] == "success"
        assert tool_call["output"]["retrieval_quality"] == "good"

