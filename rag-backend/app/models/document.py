from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class KnowledgeBaseDocument(Base):
    __tablename__ = "knowledge_base_documents"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id",
            "source",
            name="uq_kb_documents_kb_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20), default="txt")
    source: Mapped[str] = mapped_column(String(1024))
    storage_provider: Mapped[str] = mapped_column(String(50), default="local")
    storage_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="indexed")
    character_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship(back_populates="documents")


class KnowledgeBaseDocumentChunk(Base):
    __tablename__ = "knowledge_base_document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id",
            "source",
            "content_hash",
            name="uq_kb_document_chunks_kb_source_hash",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(1024), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IngestionTask(Base):
    __tablename__ = "ingestion_tasks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    knowledge_base_name: Mapped[str] = mapped_column(String(120), default="")
    filename: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(1024), index=True, default="")
    task_type: Mapped[str] = mapped_column(String(50), default="upload")
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    queue_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_node: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    logs: Mapped[list["IngestionTaskLog"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="IngestionTaskLog.id",
    )


class IngestionTaskLog(Base):
    __tablename__ = "ingestion_task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ingestion_tasks.id", ondelete="CASCADE"),
        index=True,
    )
    node_name: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(50), default="running")
    message: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    task: Mapped[IngestionTask] = relationship(back_populates="logs")
