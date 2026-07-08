import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def _ensure_column(
    connection,
    inspector,
    *,
    table_name: str,
    column_name: str,
    column_sql: str,
) -> None:
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


def _run_schema_migrations() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    with engine.begin() as connection:
        if "knowledge_bases" in table_names:
            _ensure_column(
                connection,
                inspector,
                table_name="knowledge_bases",
                column_name="embedding_model",
                column_sql="embedding_model VARCHAR(200)",
            )
        if "chat_sessions" in table_names:
            _ensure_column(
                connection,
                inspector,
                table_name="chat_sessions",
                column_name="user_id",
                column_sql="user_id VARCHAR(36)",
            )
            _ensure_column(
                connection,
                inspector,
                table_name="chat_sessions",
                column_name="knowledge_base_id",
                column_sql="knowledge_base_id VARCHAR(36)",
            )
            _ensure_column(
                connection,
                inspector,
                table_name="chat_sessions",
                column_name="memory_summary",
                column_sql="memory_summary TEXT",
            )
            _ensure_column(
                connection,
                inspector,
                table_name="chat_sessions",
                column_name="memory_summary_last_message_id",
                column_sql="memory_summary_last_message_id INTEGER",
            )
        if "knowledge_base_documents" in table_names:
            _ensure_column(
                connection,
                inspector,
                table_name="knowledge_base_documents",
                column_name="storage_provider",
                column_sql="storage_provider VARCHAR(50) DEFAULT 'local'",
            )
            _ensure_column(
                connection,
                inspector,
                table_name="knowledge_base_documents",
                column_name="storage_bucket",
                column_sql="storage_bucket VARCHAR(255)",
            )
            _ensure_column(
                connection,
                inspector,
                table_name="knowledge_base_documents",
                column_name="storage_object_key",
                column_sql="storage_object_key VARCHAR(1024)",
            )
            _ensure_column(
                connection,
                inspector,
                table_name="knowledge_base_documents",
                column_name="content_type",
                column_sql="content_type VARCHAR(255)",
            )
            _ensure_column(
                connection,
                inspector,
                table_name="knowledge_base_documents",
                column_name="file_size",
                column_sql="file_size BIGINT DEFAULT 0",
            )
        if "chat_messages" in table_names:
            _ensure_column(
                connection,
                inspector,
                table_name="chat_messages",
                column_name="standalone_question",
                column_sql="standalone_question TEXT",
            )
        if "ingestion_tasks" in table_names:
            _ensure_column(
                connection,
                inspector,
                table_name="ingestion_tasks",
                column_name="queue_job_id",
                column_sql="queue_job_id VARCHAR(255)",
            )
            _ensure_column(
                connection,
                inspector,
                table_name="ingestion_tasks",
                column_name="retry_count",
                column_sql="retry_count INTEGER DEFAULT 0",
            )
            _ensure_column(
                connection,
                inspector,
                table_name="ingestion_tasks",
                column_name="max_retries",
                column_sql="max_retries INTEGER DEFAULT 3",
            )


def _bootstrap_metadata() -> None:
    from app.models import ChatSession, KnowledgeBase
    from app.services.auth_service import ensure_seed_users

    with SessionLocal() as db:
        admin_user, _ = ensure_seed_users(db)

        db.query(ChatSession).filter(ChatSession.user_id.is_(None)).update(
            {ChatSession.user_id: admin_user.id},
            synchronize_session=False,
        )
        db.query(KnowledgeBase).filter(KnowledgeBase.is_default.is_(True)).update(
            {KnowledgeBase.is_default: False},
            synchronize_session=False,
        )
        db.commit()


def init_db(retries: int = 10, delay_seconds: int = 3) -> None:
    from app.models import app_setting, chat, document, knowledge_base, user

    last_error: Exception | None = None

    for _ in range(retries):
        try:
            Base.metadata.create_all(bind=engine)
            _run_schema_migrations()
            _bootstrap_metadata()
            return
        except (SQLAlchemyError, UnicodeDecodeError) as exc:
            last_error = exc
            time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error
