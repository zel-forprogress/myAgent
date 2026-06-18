from typing import List

from pydantic import BaseModel, Field

from app.schemas.chat import MessageResponse


class SessionCreateRequest(BaseModel):
    title: str = ""
    knowledge_base_id: str | None = None


class SessionUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Session title")


class SessionResponse(BaseModel):
    id: str
    title: str
    user_id: str | None = None
    owner_username: str | None = None
    knowledge_base_id: str | None = None
    knowledge_base_name: str | None = None
    created_at: str
    updated_at: str
    message_count: int = 0


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]


class SessionMessagesResponse(BaseModel):
    session: SessionResponse
    messages: List[MessageResponse]


class DeleteSessionResponse(BaseModel):
    success: bool
    message: str
    session_id: str
