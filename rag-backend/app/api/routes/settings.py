from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.models import User
from app.schemas.settings import (
    RerankSettingsResponse,
    RerankSettingsUpdateRequest,
    RetrievalSettingsResponse,
    RetrievalSettingsUpdateRequest,
)
from app.services.rerank_service import get_rerank_endpoint
from app.services.settings_service import (
    RETRIEVAL_MIN_SCORE_DEFAULT,
    get_rerank_enabled,
    get_rerank_settings_source,
    get_retrieval_min_score,
    get_retrieval_settings_source,
    set_rerank_enabled,
    set_retrieval_min_score,
)

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


def _rerank_settings_response(db: Session) -> RerankSettingsResponse:
    return RerankSettingsResponse(
        enabled=get_rerank_enabled(db),
        model=settings.rerank_model,
        endpoint=get_rerank_endpoint(),
        source=get_rerank_settings_source(db),
    )


def _retrieval_settings_response(db: Session) -> RetrievalSettingsResponse:
    return RetrievalSettingsResponse(
        min_score=get_retrieval_min_score(db),
        default_min_score=RETRIEVAL_MIN_SCORE_DEFAULT,
        source=get_retrieval_settings_source(db),
    )


@router.get("/rerank", response_model=RerankSettingsResponse)
def get_admin_rerank_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RerankSettingsResponse:
    _ = current_user
    return _rerank_settings_response(db)


@router.put("/rerank", response_model=RerankSettingsResponse)
def update_admin_rerank_settings(
    request: RerankSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RerankSettingsResponse:
    _ = current_user
    set_rerank_enabled(db, request.enabled)
    return _rerank_settings_response(db)


@router.get("/retrieval", response_model=RetrievalSettingsResponse)
def get_admin_retrieval_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetrievalSettingsResponse:
    _ = current_user
    return _retrieval_settings_response(db)


@router.put("/retrieval", response_model=RetrievalSettingsResponse)
def update_admin_retrieval_settings(
    request: RetrievalSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RetrievalSettingsResponse:
    _ = current_user
    set_retrieval_min_score(db, request.min_score)
    return _retrieval_settings_response(db)
