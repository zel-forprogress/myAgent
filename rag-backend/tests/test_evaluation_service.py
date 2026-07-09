from datetime import datetime

import pytest

from app.schemas import EvaluationRunSummary
from app.services.evaluation_service import build_evaluation_summary, serialize_evaluation_case


class FakeKnowledgeBase:
    name = "产品文档库"


class FakeEvaluationCase:
    id = "case-1"
    knowledge_base_id = "kb-1"
    knowledge_base = FakeKnowledgeBase()
    question = "鸿蒙开发的要求"
    expected_sources = ["HarmonyOS"]
    expected_keywords = ["实名认证"]
    top_k = 6
    use_rerank = True
    note = "core case"
    last_status = "passed"
    last_score = 0.78
    last_hit = True
    last_ran_at = datetime(2026, 7, 9, 1, 2, 3)
    created_at = datetime(2026, 7, 9, 1, 0, 0)
    updated_at = datetime(2026, 7, 9, 1, 1, 0)


class FakeResult:
    def __init__(
        self,
        *,
        status: str,
        source_hit: bool,
        quality_passed: bool,
        max_score: float,
        keyword_hit_rate: float,
        rerank_applied: bool,
    ) -> None:
        self.status = status
        self.source_hit = source_hit
        self.quality_passed = quality_passed
        self.max_score = max_score
        self.keyword_hit_rate = keyword_hit_rate
        self.rerank_applied = rerank_applied


def test_serialize_evaluation_case() -> None:
    response = serialize_evaluation_case(FakeEvaluationCase())  # type: ignore[arg-type]

    assert response.id == "case-1"
    assert response.knowledge_base_name == "产品文档库"
    assert response.expected_sources == ["HarmonyOS"]
    assert response.last_ran_at == "2026-07-09T01:02:03"


def test_build_evaluation_summary_empty() -> None:
    summary = build_evaluation_summary([])

    assert summary == EvaluationRunSummary(
        total=0,
        passed=0,
        failed=0,
        source_hit_rate=0.0,
        quality_pass_rate=0.0,
        average_score=0.0,
        average_keyword_hit_rate=0.0,
        rerank_applied_rate=0.0,
    )


def test_build_evaluation_summary() -> None:
    summary = build_evaluation_summary(
        [
            FakeResult(
                status="passed",
                source_hit=True,
                quality_passed=True,
                max_score=0.8,
                keyword_hit_rate=1.0,
                rerank_applied=True,
            ),
            FakeResult(
                status="failed",
                source_hit=False,
                quality_passed=True,
                max_score=0.4,
                keyword_hit_rate=0.5,
                rerank_applied=False,
            ),
        ]  # type: ignore[arg-type]
    )

    assert summary.total == 2
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.source_hit_rate == 0.5
    assert summary.quality_pass_rate == 1.0
    assert summary.average_score == pytest.approx(0.6)
    assert summary.average_keyword_hit_rate == 0.75
    assert summary.rerank_applied_rate == 0.5
