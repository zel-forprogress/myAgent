from typing import Optional

from pydantic import BaseModel, Field


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Knowledge base name")
    collection_name: Optional[str] = Field(default=None, description="Custom Milvus collection name (auto-generated if empty)")
    embedding_model: Optional[str] = Field(default=None, description="Embedding model (uses system default if empty)")


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    slug: str
    collection_name: str
    embedding_model: Optional[str] = None
    is_default: bool
    created_at: str


class DeleteKnowledgeBaseResponse(BaseModel):
    success: bool
    message: str
    knowledge_base_id: str
