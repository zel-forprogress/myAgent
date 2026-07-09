from datetime import datetime
from time import perf_counter

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import EvaluationCase, KnowledgeBase
from app.schemas import (
    EvaluationCaseCreateRequest,
    EvaluationCaseResponse,
    EvaluationCaseResult,
    EvaluationRunSummary,
    SourceChunk,
)
from app.services.knowledge_base_service import resolve_knowledge_base
from app.services.rag_service import retrieve_sources_multi
from app.services.rerank_service import rerank_sources
from app.services.settings_service import get_retrieval_min_score


def _split_terms(values: list[str]) -> list[str]:
    terms: list[str] = []
    for value in values:
        for item in value.replace("，", ",").split(","):
            term = item.strip()
            if term:
                terms.append(term)
    return terms


def serialize_evaluation_case(case: EvaluationCase) -> EvaluationCaseResponse:
    knowledge_base_name = case.knowledge_base.name if case.knowledge_base else ""
    return EvaluationCaseResponse(
        id=case.id,
        knowledge_base_id=case.knowledge_base_id,
        knowledge_base_name=knowledge_base_name,
        question=case.question,
        expected_sources=case.expected_sources or [],
        expected_keywords=case.expected_keywords or [],
        top_k=case.top_k,
        use_rerank=case.use_rerank,
        note=case.note or "",
        last_status=case.last_status,
        last_score=case.last_score,
        last_hit=case.last_hit,
        last_ran_at=case.last_ran_at.isoformat() if case.last_ran_at else None,
        created_at=case.created_at.isoformat(),
        updated_at=case.updated_at.isoformat(),
    )


def list_evaluation_cases(db: Session) -> list[EvaluationCase]:
    return (
        db.query(EvaluationCase)
        .join(KnowledgeBase, EvaluationCase.knowledge_base_id == KnowledgeBase.id)
        .order_by(EvaluationCase.created_at.desc())
        .all()
    )


def create_evaluation_case(db: Session, request: EvaluationCaseCreateRequest) -> EvaluationCase:
    knowledge_base = resolve_knowledge_base(db, request.knowledge_base_id)
    case = EvaluationCase(
        knowledge_base_id=knowledge_base.id,
        question=request.question.strip(),
        expected_sources=_split_terms(request.expected_sources),
        expected_keywords=_split_terms(request.expected_keywords),
        top_k=request.top_k,
        use_rerank=request.use_rerank,
        note=request.note.strip(),
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def delete_evaluation_case(db: Session, case_id: str) -> bool:
    case = db.get(EvaluationCase, case_id)
    if case is None:
        return False
    db.delete(case)
    db.commit()
    return True


def _max_score(sources: list[SourceChunk]) -> float:
    scores = [source.score for source in sources if isinstance(source.score, (int, float))]
    return float(max(scores)) if scores else 0.0


def _match_sources(expected_sources: list[str], sources: list[SourceChunk]) -> list[str]:
    if not expected_sources:
        return []
    source_text = "\n".join(source.source or "" for source in sources).lower()
    return [item for item in expected_sources if item.lower() in source_text]


def _match_keywords(expected_keywords: list[str], sources: list[SourceChunk]) -> list[str]:
    if not expected_keywords:
        return []
    content = "\n".join(source.content for source in sources).lower()
    return [item for item in expected_keywords if item.lower() in content]


def run_evaluation_case(
    db: Session,
    case: EvaluationCase,
    *,
    override_use_rerank: bool | None = None,
    override_top_k: int | None = None,
) -> EvaluationCaseResult:
    knowledge_base = resolve_knowledge_base(db, case.knowledge_base_id)
    top_k = override_top_k or case.top_k
    use_rerank = case.use_rerank if override_use_rerank is None else override_use_rerank
    candidate_top_k = top_k
    if use_rerank:
        candidate_top_k = min(max(top_k * max(1, settings.rerank_candidate_multiplier), top_k), 50)

    started = perf_counter()
    candidate_sources = retrieve_sources_multi(
        collection_names=[knowledge_base.collection_name],
        question=case.question,
        top_k=candidate_top_k,
    )

    rerank_applied = False
    rerank_error = ""
    sources = candidate_sources[:top_k]
    if use_rerank:
        rerank_result = rerank_sources(
            question=case.question,
            sources=candidate_sources,
            top_k=top_k,
        )
        sources = rerank_result.sources
        rerank_applied = rerank_result.applied
        rerank_error = rerank_result.error

    duration_ms = int((perf_counter() - started) * 1000)
    min_required_score = get_retrieval_min_score(db)
    max_score = _max_score(sources)
    matched_sources = _match_sources(case.expected_sources or [], sources)
    matched_keywords = _match_keywords(case.expected_keywords or [], sources)
    source_hit = bool(matched_sources) if case.expected_sources else bool(sources)
    keyword_hit_rate = (
        len(matched_keywords) / len(case.expected_keywords)
        if case.expected_keywords
        else (1.0 if sources else 0.0)
    )
    quality_passed = bool(sources) and max_score >= min_required_score
    status = "passed" if quality_passed and source_hit else "failed"

    case.last_status = status
    case.last_score = max_score
    case.last_hit = source_hit
    case.last_ran_at = datetime.utcnow()
    db.add(case)
    db.commit()
    db.refresh(case)

    return EvaluationCaseResult(
        case=serialize_evaluation_case(case),
        status=status,
        duration_ms=duration_ms,
        source_count=len(sources),
        candidate_count=len(candidate_sources),
        max_score=max_score,
        min_required_score=min_required_score,
        quality_passed=quality_passed,
        source_hit=source_hit,
        keyword_hit_rate=keyword_hit_rate,
        matched_sources=matched_sources,
        matched_keywords=matched_keywords,
        rerank_enabled=use_rerank,
        rerank_applied=rerank_applied,
        rerank_error=rerank_error,
        sources=sources,
    )


def build_evaluation_summary(results: list[EvaluationCaseResult]) -> EvaluationRunSummary:
    total = len(results)
    if total == 0:
        return EvaluationRunSummary(
            total=0,
            passed=0,
            failed=0,
            source_hit_rate=0.0,
            quality_pass_rate=0.0,
            average_score=0.0,
            average_keyword_hit_rate=0.0,
            rerank_applied_rate=0.0,
        )

    passed = len([item for item in results if item.status == "passed"])
    return EvaluationRunSummary(
        total=total,
        passed=passed,
        failed=total - passed,
        source_hit_rate=len([item for item in results if item.source_hit]) / total,
        quality_pass_rate=len([item for item in results if item.quality_passed]) / total,
        average_score=sum(item.max_score for item in results) / total,
        average_keyword_hit_rate=sum(item.keyword_hit_rate for item in results) / total,
        rerank_applied_rate=len([item for item in results if item.rerank_applied]) / total,
    )
