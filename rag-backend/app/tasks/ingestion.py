from __future__ import annotations

from celery import Task

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.models import IngestionTask
from app.services.ingestion_pipeline import run_ingestion_pipeline
from app.services.ingestion_task_service import update_ingestion_task


@celery_app.task(
    bind=True,
    name="app.tasks.ingestion.process_ingestion_task",
    max_retries=settings.ingestion_task_max_retries,
)
def process_ingestion_task(self: Task, task_id: str) -> str:
    init_db()
    db = SessionLocal()
    try:
        task = db.query(IngestionTask).filter(IngestionTask.id == task_id).first()
        if task is None:
            return f"ingestion task {task_id} not found"
        if task.status in {"success", "cancelled"}:
            return f"ingestion task {task_id} already {task.status}"

        try:
            run_ingestion_pipeline(db, task)
        except Exception as exc:
            current_retries = int(getattr(self.request, "retries", 0) or 0)
            max_retries = task.max_retries or settings.ingestion_task_max_retries
            if current_retries < max_retries:
                update_ingestion_task(
                    db,
                    task,
                    status="retrying",
                    current_node=task.current_node or "retry",
                    message=f"Retrying ingestion task after failure: {exc}",
                    retry_count=current_retries + 1,
                    error=str(exc),
                )
                raise self.retry(
                    exc=exc,
                    countdown=settings.ingestion_task_retry_delay_seconds,
                    max_retries=max_retries,
                )
            raise

        return f"ingestion task {task_id} completed"
    finally:
        db.close()
