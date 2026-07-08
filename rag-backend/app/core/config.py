from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str
    openai_base_url: str

    chat_model: str
    embedding_model: str

    milvus_uri: str
    milvus_collection: str
    database_url: str

    object_storage_enabled: bool = True
    object_storage_provider: str = "s3"
    object_storage_bucket: str = "myagent-docs"
    s3_endpoint_url: str = "http://127.0.0.1:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = False

    auth_secret_key: str = "dev-secret-key-change-me-please-use-32chars"
    auth_access_token_expire_minutes: int = 60 * 24
    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin123456"
    seed_user_username: str = "demo"
    seed_user_password: str = "demo123456"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    langfuse_secret_key: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_base_url: Optional[str] = None
    langfuse_timeout: int = 30

    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    ingestion_task_max_retries: int = 3
    ingestion_task_retry_delay_seconds: int = 30

    rerank_enabled: bool = False
    rerank_model: str = "qwen3-rerank"
    rerank_base_url: Optional[str] = None
    rerank_timeout_seconds: int = 30
    rerank_candidate_multiplier: int = 4

    chat_history_recent_messages: int = 8
    chat_memory_summary_enabled: bool = True
    chat_memory_summary_start_messages: int = 16
    chat_memory_summary_keep_messages: int = 8
    chat_memory_summary_max_chars: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
