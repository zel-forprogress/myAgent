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

    langfuse_secret_key: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_base_url: Optional[str] = None
    langfuse_timeout: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
