from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., description="User question")
    top_k: int = Field(default=4, ge=1, le=20, description="Retrieved chunk count")
    knowledge_base_id: str | None = Field(default=None, description="Knowledge base id")
    knowledge_base_ids: list[str] | None = Field(
        default=None,
        description="Knowledge base ids; empty means search all knowledge bases",
    )


class SourceChunk(BaseModel):
    content: str
    source: Optional[str] = None
    score: Optional[float] = None
    vector_score: Optional[float] = None
    keyword_score: Optional[float] = None
    rerank_score: Optional[float] = None
    retrieval_type: Literal["vector", "keyword", "hybrid"] = "vector"


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    route: str = ""
    task_intent: str = ""
    task_confidence: float = 0.0
    agent_plan: List[str] = []
    tool_calls: List[dict[str, Any]] = []
    steps: List[str] = []
    retrieval_quality: str = ""
    rewritten_question: str = ""
    standalone_question: str = ""


class RetrievalTestRequest(BaseModel):
    question: str = Field(..., description="Question or query to retrieve against")
    knowledge_base_ids: list[str] = Field(..., min_length=1, description="Knowledge base ids")
    top_k: int = Field(default=6, ge=1, le=20, description="Retrieved chunk count")
    use_rerank: bool = Field(default=False, description="Whether to apply rerank to candidates")


class RetrievalTestResponse(BaseModel):
    question: str
    top_k: int
    knowledge_base_ids: list[str]
    knowledge_base_names: list[str]
    collection_names: list[str]
    duration_ms: int
    source_count: int
    candidate_count: int = 0
    rerank_enabled: bool = False
    rerank_applied: bool = False
    rerank_model: str = ""
    rerank_endpoint: str = ""
    rerank_error: str = ""
    sources: List[SourceChunk]


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    route: str = ""
    task_intent: str = ""
    task_confidence: float = 0.0
    agent_plan: List[str] = []
    tool_calls: List[dict[str, Any]] = []
    retrieval_quality: str = ""
    rewritten_question: str = ""
    standalone_question: str = ""
    source_count: int = 0
    sources: List[SourceChunk] = []
    steps: List[str] = []
    created_at: str
