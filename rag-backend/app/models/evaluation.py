from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"

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
    question: Mapped[str] = mapped_column(Text)
    expected_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    expected_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    top_k: Mapped[int] = mapped_column(Integer, default=6)
    use_rerank: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_ran_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    knowledge_base: Mapped["KnowledgeBase"] = relationship()
