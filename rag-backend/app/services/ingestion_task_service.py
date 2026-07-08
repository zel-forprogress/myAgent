from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from time import perf_counter
from typing import Iterator

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import IngestionTask, IngestionTaskLog, KnowledgeBase
from app.schemas import IngestionTaskLogResponse, IngestionTaskResponse


def create_ingestion_task(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    task_type: str,
    filename: str = "",
    source: str = "",
    message: str = "",
) -> IngestionTask:
    task = IngestionTask(
        knowledge_base_id=knowledge_base.id,
        knowledge_base_name=knowledge_base.name,
        filename=filename,
        source=source,
        task_type=task_type,
        status="pending",
        message=message,
        max_retries=settings.ingestion_task_max_retries,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_ingestion_task(
    db: Session,
    task: IngestionTask,
    *,
    status: str | None = None,
    current_node: str | None = None,
    message: str | None = None,
    filename: str | None = None,
    source: str | None = None,
    chunks: int | None = None,
    skipped: int | None = None,
    queue_job_id: str | None = None,
    retry_count: int | None = None,
    max_retries: int | None = None,
    error: str | None = None,
) -> IngestionTask:
    now = datetime.utcnow()
    if status is not None:
        task.status = status
        if status == "running" and task.started_at is None:
            task.started_at = now
        if status in {"success", "failed"}:
            task.finished_at = now
    if current_node is not None:
        task.current_node = current_node
    if message is not None:
        task.message = message
    if filename is not None:
        task.filename = filename
    if source is not None:
        task.source = source
    if chunks is not None:
        task.chunks = chunks
    if skipped is not None:
        task.skipped = skipped
    if queue_job_id is not None:
        task.queue_job_id = queue_job_id
    if retry_count is not None:
        task.retry_count = retry_count
    if max_retries is not None:
        task.max_retries = max_retries
    if error is not None:
        task.error = error
    task.updated_at = now
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def add_task_log(
    db: Session,
    task: IngestionTask,
    *,
    node_name: str,
    status: str,
    message: str = "",
    details: dict | None = None,
    error: str | None = None,
    duration_ms: int = 0,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> IngestionTaskLog:
    log = IngestionTaskLog(
        task_id=task.id,
        node_name=node_name,
        status=status,
        message=message,
        details=details,
        error=error,
        duration_ms=duration_ms,
        started_at=started_at or datetime.utcnow(),
        finished_at=finished_at,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@contextmanager
def task_node(
    db: Session,
    task: IngestionTask,
    node_name: str,
    start_message: str,
) -> Iterator[dict]:
    started_at = datetime.utcnow()
    started = perf_counter()
    update_ingestion_task(
        db,
        task,
        status="running",
        current_node=node_name,
        message=start_message,
    )
    add_task_log(
        db,
        task,
        node_name=node_name,
        status="running",
        message=start_message,
        started_at=started_at,
    )
    details: dict = {}
    try:
        yield details
    except Exception as exc:
        finished_at = datetime.utcnow()
        duration_ms = int((perf_counter() - started) * 1000)
        add_task_log(
            db,
            task,
            node_name=node_name,
            status="failed",
            message=f"{node_name} failed",
            details=details or None,
            error=str(exc),
            duration_ms=duration_ms,
            started_at=started_at,
            finished_at=finished_at,
        )
        update_ingestion_task(
            db,
            task,
            status="failed",
            message=f"{node_name} failed",
            error=str(exc),
        )
        raise

    finished_at = datetime.utcnow()
    duration_ms = int((perf_counter() - started) * 1000)
    add_task_log(
        db,
        task,
        node_name=node_name,
        status="success",
        message=f"{node_name} completed",
        details=details or None,
        duration_ms=duration_ms,
        started_at=started_at,
        finished_at=finished_at,
    )


def list_ingestion_tasks(
    db: Session,
    *,
    knowledge_base_id: str | None = None,
    source: str | None = None,
    limit: int = 20,
) -> tuple[list[IngestionTask], int]:
    query = db.query(IngestionTask)
    if knowledge_base_id:
        query = query.filter(IngestionTask.knowledge_base_id == knowledge_base_id)
    if source:
        query = query.filter(IngestionTask.source == source)
    total = query.count()
    tasks = (
        query.order_by(IngestionTask.created_at.desc(), IngestionTask.id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return tasks, total


def get_ingestion_task(db: Session, task_id: str) -> IngestionTask | None:
    return db.query(IngestionTask).filter(IngestionTask.id == task_id).first()


def serialize_task_log(log: IngestionTaskLog) -> IngestionTaskLogResponse:
    return IngestionTaskLogResponse(
        id=log.id,
        task_id=log.task_id,
        node_name=log.node_name,
        status=log.status,
        message=log.message,
        details=log.details,
        error=log.error,
        duration_ms=log.duration_ms,
        started_at=log.started_at.isoformat(),
        finished_at=log.finished_at.isoformat() if log.finished_at else None,
    )


def serialize_ingestion_task(
    task: IngestionTask,
    *,
    include_logs: bool = False,
) -> IngestionTaskResponse:
    return IngestionTaskResponse(
        id=task.id,
        knowledge_base_id=task.knowledge_base_id,
        knowledge_base_name=task.knowledge_base_name,
        filename=task.filename,
        source=task.source,
        task_type=task.task_type,
        status=task.status,
        queue_job_id=task.queue_job_id,
        current_node=task.current_node,
        message=task.message or "",
        chunks=task.chunks or 0,
        skipped=task.skipped or 0,
        retry_count=task.retry_count or 0,
        max_retries=task.max_retries or 0,
        error=task.error,
        created_at=task.created_at.isoformat(),
        started_at=task.started_at.isoformat() if task.started_at else None,
        finished_at=task.finished_at.isoformat() if task.finished_at else None,
        updated_at=task.updated_at.isoformat(),
        logs=[serialize_task_log(log) for log in task.logs] if include_logs else [],
    )
