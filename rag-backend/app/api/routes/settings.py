from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, require_admin
from app.core.config import settings
from app.models import User
from app.schemas.settings import RerankSettingsResponse, RerankSettingsUpdateRequest
from app.services.rerank_service import get_rerank_endpoint
from app.services.settings_service import (
    get_rerank_enabled,
    get_rerank_settings_source,
    set_rerank_enabled,
)

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


def _rerank_settings_response(db: Session) -> RerankSettingsResponse:
    return RerankSettingsResponse(
        enabled=get_rerank_enabled(db),
        model=settings.rerank_model,
        endpoint=get_rerank_endpoint(),
        source=get_rerank_settings_source(db),
    )


@router.get("/rerank", response_model=RerankSettingsResponse)
def get_admin_rerank_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> RerankSettingsResponse:
    _ = admin
    return _rerank_settings_response(db)


@router.put("/rerank", response_model=RerankSettingsResponse)
def update_admin_rerank_settings(
    request: RerankSettingsUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> RerankSettingsResponse:
    _ = admin
    set_rerank_enabled(db, request.enabled)
    return _rerank_settings_response(db)
