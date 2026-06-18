from pydantic import BaseModel, Field


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Knowledge base name")


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    slug: str
    collection_name: str
    is_default: bool
    created_at: str


class DeleteKnowledgeBaseResponse(BaseModel):
    success: bool
    message: str
    knowledge_base_id: str
