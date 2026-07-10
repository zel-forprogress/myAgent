from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.config import settings
from app.schemas import SourceChunk
from app.services.rag_service import retrieve_sources_multi
from app.services.rerank_service import rerank_sources
from app.services.settings_service import get_rerank_enabled, get_retrieval_min_score


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    handler: Callable[..., "AgentToolExecution"]


@dataclass
class AgentToolExecution:
    name: str
    status: str = "success"
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def to_tool_call(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "input": self.input,
            "output": self.output,
        }


class AgentToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        handler: Callable[..., AgentToolExecution],
    ) -> None:
        self._tools[name] = AgentTool(name=name, description=description, handler=handler)

    def get(self, name: str) -> AgentTool:
        return self._tools[name]

    def list_tools(self) -> list[dict[str, str]]:
        return [
            {"name": tool.name, "description": tool.description}
            for tool in self._tools.values()
        ]

    def run(self, name: str, **kwargs: Any) -> AgentToolExecution:
        return self.get(name).handler(**kwargs)


def max_source_score(sources: list[SourceChunk]) -> float:
    return max((source.score or 0.0 for source in sources), default=0.0)


def summarize_sources(sources: list[SourceChunk]) -> dict[str, Any]:
    return {
        "source_count": len(sources),
        "max_score": max_source_score(sources),
        "rerank_applied": any(source.rerank_score is not None for source in sources),
        "retrieval_types": sorted(
            {
                source.retrieval_type
                for source in sources
                if getattr(source, "retrieval_type", None)
            }
        ),
        "top_sources": [
            {
                "source": source.source,
                "score": source.score,
                "vector_score": source.vector_score,
                "keyword_score": source.keyword_score,
                "rerank_score": source.rerank_score,
                "retrieval_type": source.retrieval_type,
                "preview": source.content[:160],
            }
            for source in sources[:3]
        ],
    }


def diagnose_retrieval_quality(
    sources: list[SourceChunk],
    *,
    min_required_score: float,
) -> dict[str, Any]:
    max_score = max_source_score(sources)
    quality = "good" if sources and max_score >= min_required_score else "poor"
    if not sources:
        reason = "no_sources"
        recommendation = "rewrite_query"
    elif max_score < min_required_score:
        reason = "score_below_threshold"
        recommendation = "rewrite_query"
    else:
        reason = "enough_context"
        recommendation = "generate_answer"

    return {
        "retrieval_quality": quality,
        "max_score": max_score,
        "min_required_score": min_required_score,
        "reason": reason,
        "recommendation": recommendation,
    }


def search_knowledge_base(
    *,
    collection_names: list[str],
    question: str,
    top_k: int,
) -> AgentToolExecution:
    candidate_top_k = top_k
    rerank_enabled = get_rerank_enabled()
    if rerank_enabled:
        candidate_top_k = min(
            max(top_k * max(1, settings.rerank_candidate_multiplier), top_k),
            50,
        )

    candidates = retrieve_sources_multi(
        collection_names=collection_names,
        question=question,
        top_k=candidate_top_k,
    )

    sources = candidates[:top_k]
    if rerank_enabled:
        rerank_result = rerank_sources(
            question=question,
            sources=candidates,
            top_k=top_k,
        )
        sources = rerank_result.sources

    output = summarize_sources(sources)
    output["candidate_count"] = len(candidates)
    output["rerank_enabled"] = rerank_enabled
    return AgentToolExecution(
        name="search_knowledge_base",
        input={
            "question": question,
            "top_k": top_k,
            "collections": collection_names,
        },
        output=output,
        artifacts={"sources": sources},
    )


def inspect_sources(
    *,
    sources: list[SourceChunk],
    rewritten: bool = False,
) -> AgentToolExecution:
    min_score = get_retrieval_min_score()
    diagnosis = diagnose_retrieval_quality(sources, min_required_score=min_score)
    return AgentToolExecution(
        name="inspect_sources",
        input={
            "source_count": len(sources),
            "rewritten": rewritten,
            "min_required_score": min_score,
        },
        output={
            **diagnosis,
            "summary": summarize_sources(sources),
        },
    )


def guard_no_context(
    *,
    retrieval_quality: str,
    sources: list[SourceChunk],
) -> AgentToolExecution:
    diagnosis = diagnose_retrieval_quality(
        sources,
        min_required_score=get_retrieval_min_score(),
    )
    return AgentToolExecution(
        name="guard_no_context",
        input={
            "retrieval_quality": retrieval_quality,
            "source_count": len(sources),
        },
        output={
            **diagnosis,
            "guarded": True,
        },
    )


agent_tool_registry = AgentToolRegistry()
agent_tool_registry.register(
    name="search_knowledge_base",
    description="Retrieve candidate chunks from selected knowledge bases and optionally rerank them.",
    handler=search_knowledge_base,
)
agent_tool_registry.register(
    name="inspect_sources",
    description="Diagnose whether retrieved chunks are strong enough for grounded answering.",
    handler=inspect_sources,
)
agent_tool_registry.register(
    name="guard_no_context",
    description="Stop grounded answering when retrieved evidence is too weak.",
    handler=guard_no_context,
)

