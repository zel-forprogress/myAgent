from typing import List, Optional

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    path: str = Field(..., description="Local document path")
    knowledge_base_id: str | None = Field(default=None, description="Knowledge base id")


class IngestResponse(BaseModel):
    success: bool
    message: str
    chunks: int
    skipped: int = 0
    knowledge_base_id: str
    knowledge_base_name: str
    collection: str
    stored_path: str = ""
    filename: str = ""
    file_type: str = ""
    status: str = "indexed"
    character_count: int = 0
    uploaded_at: str = ""
    storage_provider: str = "local"
    storage_bucket: str | None = None
    storage_object_key: str | None = None
    content_type: str | None = None
    file_size: int = 0
    task_id: str | None = None


class DocumentInfo(BaseModel):
    filename: str
    file_type: str
    source: str
    chunks: int
    status: str = "indexed"
    character_count: int = 0
    uploaded_at: str = ""
    storage_provider: str = "local"
    storage_bucket: str | None = None
    storage_object_key: str | None = None
    content_type: str | None = None
    file_size: int = 0


class DocumentsResponse(BaseModel):
    knowledge_base_id: str
    knowledge_base_name: str
    collection: str
    documents: List[DocumentInfo]
    total: int = 0
    page: int = 1
    page_size: int = 20


class DeleteDocumentRequest(BaseModel):
    source: str = Field(..., description="Source to delete")
    knowledge_base_id: str | None = Field(default=None, description="Knowledge base id")


class DeleteDocumentResponse(BaseModel):
    success: bool
    message: str
    source: str
    deleted: int
    knowledge_base_id: str
    knowledge_base_name: str
    collection: str


class IngestionTaskLogResponse(BaseModel):
    id: int
    task_id: str
    node_name: str
    status: str
    message: str = ""
    details: dict | None = None
    error: str | None = None
    duration_ms: int = 0
    started_at: str
    finished_at: str | None = None


class IngestionTaskResponse(BaseModel):
    id: str
    knowledge_base_id: str
    knowledge_base_name: str
    filename: str
    source: str
    task_type: str
    status: str
    queue_job_id: str | None = None
    current_node: str | None = None
    message: str = ""
    chunks: int = 0
    skipped: int = 0
    retry_count: int = 0
    max_retries: int = 0
    error: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    updated_at: str
    logs: list[IngestionTaskLogResponse] = []


class IngestionTaskListResponse(BaseModel):
    tasks: list[IngestionTaskResponse]
    total: int = 0
