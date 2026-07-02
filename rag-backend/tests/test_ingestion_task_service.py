from __future__ import annotations

from datetime import datetime

from app.models import IngestionTask, IngestionTaskLog
from app.services.ingestion_task_service import (
    serialize_ingestion_task,
    update_ingestion_task,
)


class FakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1

    def refresh(self, item):
        return item


class TestUpdateIngestionTask:
    def test_sets_running_start_time_once(self):
        db = FakeDb()
        task = IngestionTask(
            id="task-1",
            knowledge_base_id="kb-1",
            knowledge_base_name="KB",
            filename="demo.txt",
            source="demo.txt",
            task_type="chunk",
            status="pending",
        )

        update_ingestion_task(
            db,  # type: ignore[arg-type]
            task,
            status="running",
            current_node="chunk_embed_index",
            message="Indexing",
        )

        assert task.status == "running"
        assert task.current_node == "chunk_embed_index"
        assert task.started_at is not None
        assert db.commits == 1

    def test_success_sets_finished_at_and_counts(self):
        db = FakeDb()
        task = IngestionTask(
            id="task-1",
            knowledge_base_id="kb-1",
            knowledge_base_name="KB",
            filename="demo.txt",
            source="demo.txt",
            task_type="chunk",
            status="running",
        )

        update_ingestion_task(
            db,  # type: ignore[arg-type]
            task,
            status="success",
            chunks=3,
            skipped=1,
        )

        assert task.status == "success"
        assert task.finished_at is not None
        assert task.chunks == 3
        assert task.skipped == 1


class TestSerializeIngestionTask:
    def test_includes_logs_when_requested(self):
        now = datetime.utcnow()
        task = IngestionTask(
            id="task-1",
            knowledge_base_id="kb-1",
            knowledge_base_name="KB",
            filename="demo.txt",
            source="demo.txt",
            task_type="upload",
            status="success",
            created_at=now,
            updated_at=now,
        )
        task.logs = [
            IngestionTaskLog(
                id=1,
                task_id="task-1",
                node_name="store_file",
                status="success",
                message="saved",
                details={"bytes": 12},
                duration_ms=5,
                started_at=now,
                finished_at=now,
            )
        ]

        result = serialize_ingestion_task(task, include_logs=True)

        assert result.id == "task-1"
        assert result.logs[0].node_name == "store_file"
        assert result.logs[0].details == {"bytes": 12}
