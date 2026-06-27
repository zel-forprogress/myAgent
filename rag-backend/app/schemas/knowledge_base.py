import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


COLLECTION_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Knowledge base name")
    collection_name: str = Field(..., min_length=1, description="Milvus collection name (lowercase letters, numbers, underscores)")
    embedding_model: str = Field(..., min_length=1, description="Embedding model name")

    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, v: str) -> str:
        v = v.strip()
        if not COLLECTION_NAME_RE.match(v):
            raise ValueError("Collection name must contain only lowercase letters, numbers, and underscores, starting with a letter or number")
        return v


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    slug: str
    collection_name: str
    embedding_model: Optional[str] = None
    is_default: bool
    created_at: str

    # Computed fields for list display
    document_count: int = 0


class DeleteKnowledgeBaseResponse(BaseModel):
    success: bool
    message: str
    knowledge_base_id: str
