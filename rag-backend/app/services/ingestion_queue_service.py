from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import IngestionTask
from app.services.ingestion_task_service import add_task_log, update_ingestion_task


def enqueue_ingestion_task(db: Session, task: IngestionTask) -> IngestionTask:
    try:
        from app.tasks.ingestion import process_ingestion_task

        async_result = process_ingestion_task.delay(task.id)
    except Exception as exc:
        add_task_log(
            db,
            task,
            node_name="enqueue",
            status="failed",
            message="Failed to enqueue ingestion task",
            error=str(exc),
        )
        update_ingestion_task(
            db,
            task,
            status="pending",
            current_node="enqueue",
            message="Queue is unavailable; task is waiting to be enqueued",
            error=str(exc),
        )
        return task

    add_task_log(
        db,
        task,
        node_name="enqueue",
        status="success",
        message="Ingestion task enqueued",
        details={"queue_job_id": async_result.id},
    )
    return update_ingestion_task(
        db,
        task,
        status="queued",
        current_node="enqueue",
        message="Ingestion task queued",
        queue_job_id=async_result.id,
        error="",
    )
