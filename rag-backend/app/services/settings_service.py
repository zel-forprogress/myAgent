from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import AppSetting

RERANK_ENABLED_KEY = "rerank.enabled"
RETRIEVAL_MIN_SCORE_DEFAULT = 0.45
RETRIEVAL_MIN_SCORE_KEY = "retrieval.min_score"


def _bool_to_value(value: bool) -> str:
    return "true" if value else "false"


def _value_to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _value_to_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def get_setting_value(db: Session, key: str) -> str | None:
    row = db.get(AppSetting, key)
    return row.value if row else None


def set_setting_value(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()


def get_rerank_enabled(db: Session | None = None) -> bool:
    if db is not None:
        return _value_to_bool(get_setting_value(db, RERANK_ENABLED_KEY), settings.rerank_enabled)

    try:
        with SessionLocal() as session:
            return get_rerank_enabled(session)
    except Exception:
        return settings.rerank_enabled


def set_rerank_enabled(db: Session, enabled: bool) -> None:
    set_setting_value(db, RERANK_ENABLED_KEY, _bool_to_value(enabled))


def get_rerank_settings_source(db: Session) -> str:
    return "database" if get_setting_value(db, RERANK_ENABLED_KEY) is not None else "environment"


def get_retrieval_min_score(db: Session | None = None) -> float:
    if db is not None:
        value = _value_to_float(
            get_setting_value(db, RETRIEVAL_MIN_SCORE_KEY),
            RETRIEVAL_MIN_SCORE_DEFAULT,
        )
        return _clamp_score(value)

    try:
        with SessionLocal() as session:
            return get_retrieval_min_score(session)
    except Exception:
        return RETRIEVAL_MIN_SCORE_DEFAULT


def set_retrieval_min_score(db: Session, min_score: float) -> None:
    set_setting_value(db, RETRIEVAL_MIN_SCORE_KEY, f"{_clamp_score(min_score):.4f}")


def get_retrieval_settings_source(db: Session) -> str:
    return (
        "database"
        if get_setting_value(db, RETRIEVAL_MIN_SCORE_KEY) is not None
        else "default"
    )
