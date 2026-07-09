from pydantic import BaseModel, Field

from app.schemas.chat import SourceChunk


class EvaluationCaseCreateRequest(BaseModel):
    knowledge_base_id: str = Field(..., description="Knowledge base id")
    question: str = Field(..., min_length=1, description="Evaluation question")
    expected_sources: list[str] = Field(default_factory=list)
    expected_keywords: list[str] = Field(default_factory=list)
    top_k: int = Field(default=6, ge=1, le=20)
    use_rerank: bool = True
    note: str = ""


class EvaluationCaseResponse(BaseModel):
    id: str
    knowledge_base_id: str
    knowledge_base_name: str
    question: str
    expected_sources: list[str]
    expected_keywords: list[str]
    top_k: int
    use_rerank: bool
    note: str
    last_status: str | None = None
    last_score: float | None = None
    last_hit: bool | None = None
    last_ran_at: str | None = None
    created_at: str
    updated_at: str


class EvaluationRunRequest(BaseModel):
    case_ids: list[str] | None = None
    use_rerank: bool | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class EvaluationCaseResult(BaseModel):
    case: EvaluationCaseResponse
    status: str
    duration_ms: int
    source_count: int
    candidate_count: int
    max_score: float
    min_required_score: float
    quality_passed: bool
    source_hit: bool
    keyword_hit_rate: float
    matched_sources: list[str]
    matched_keywords: list[str]
    rerank_enabled: bool
    rerank_applied: bool
    rerank_error: str = ""
    sources: list[SourceChunk]


class EvaluationRunSummary(BaseModel):
    total: int
    passed: int
    failed: int
    source_hit_rate: float
    quality_pass_rate: float
    average_score: float
    average_keyword_hit_rate: float
    rerank_applied_rate: float


class EvaluationRunResponse(BaseModel):
    summary: EvaluationRunSummary
    results: list[EvaluationCaseResult]
