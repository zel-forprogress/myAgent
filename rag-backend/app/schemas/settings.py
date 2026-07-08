from pydantic import BaseModel, Field


class RerankSettingsResponse(BaseModel):
    enabled: bool
    model: str
    endpoint: str
    source: str


class RerankSettingsUpdateRequest(BaseModel):
    enabled: bool


class RetrievalSettingsResponse(BaseModel):
    min_score: float
    default_min_score: float
    source: str


class RetrievalSettingsUpdateRequest(BaseModel):
    min_score: float = Field(..., ge=0.0, le=1.0)
