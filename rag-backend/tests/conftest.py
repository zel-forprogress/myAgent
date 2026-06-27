from __future__ import annotations

import os

# Set required env vars BEFORE any import that might load settings.
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")
os.environ.setdefault("CHAT_MODEL", "test-chat-model")
os.environ.setdefault("EMBEDDING_MODEL", "test-embedding-model")
os.environ.setdefault("MILVUS_URI", "http://127.0.0.1:9999")
os.environ.setdefault("MILVUS_COLLECTION", "test_collection")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("OBJECT_STORAGE_ENABLED", "false")
os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "")
os.environ.setdefault("LANGFUSE_SECRET_KEY", "")
os.environ.setdefault("LANGFUSE_BASE_URL", "")

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure test isolation by resetting key settings for each test."""
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret-key-for-tests-only-32chars")
    monkeypatch.setattr(settings, "auth_access_token_expire_minutes", 60)
    monkeypatch.setattr(settings, "object_storage_enabled", False)
