from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    collection_name: Mapped[str] = mapped_column(String(120), unique=True)
    embedding_model: Mapped[str] = mapped_column(String(200), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="knowledge_base")
    documents: Mapped[list["KnowledgeBaseDocument"]] = relationship(
        back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
