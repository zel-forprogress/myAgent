from pydantic import BaseModel


class RerankSettingsResponse(BaseModel):
    enabled: bool
    model: str
    endpoint: str
    source: str


class RerankSettingsUpdateRequest(BaseModel):
    enabled: bool
