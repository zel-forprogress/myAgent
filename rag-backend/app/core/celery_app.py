from celery import Celery

from app.core.config import settings


def _broker_url() -> str:
    return settings.celery_broker_url or settings.redis_url


def _result_backend() -> str:
    return settings.celery_result_backend or settings.redis_url


celery_app = Celery(
    "myagent",
    broker=_broker_url(),
    backend=_result_backend(),
    include=["app.tasks.ingestion"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_default_queue="ingestion",
    task_routes={
        "app.tasks.ingestion.process_ingestion_task": {"queue": "ingestion"},
    },
)
