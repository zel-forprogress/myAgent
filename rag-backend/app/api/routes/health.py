from time import perf_counter
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pymilvus import MilvusClient
from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine

router = APIRouter()


@router.get("/health")
def health_check() -> JSONResponse:
    checks = {
        "api": _ok("FastAPI service is running."),
        "postgres": _check_postgres(),
        "milvus": _check_milvus(),
        "object_storage": _check_object_storage(),
    }
    is_healthy = all(item["status"] in {"ok", "skipped"} for item in checks.values())

    return JSONResponse(
        status_code=200 if is_healthy else 503,
        content={
            "status": "ok" if is_healthy else "degraded",
            "services": checks,
        },
    )


def _ok(message: str, **extra: Any) -> dict[str, Any]:
    return {"status": "ok", "message": message, **extra}


def _fail(exc: Exception) -> dict[str, str]:
    return {
        "status": "error",
        "message": exc.__class__.__name__,
    }


def _check_postgres() -> dict[str, Any]:
    start = perf_counter()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        return _fail(exc)
    return _ok(
        "PostgreSQL is reachable.",
        latency_ms=round((perf_counter() - start) * 1000, 2),
    )


def _check_milvus() -> dict[str, Any]:
    start = perf_counter()
    client: MilvusClient | None = None
    try:
        client = MilvusClient(uri=settings.milvus_uri)
        collections = client.list_collections(timeout=3)
    except Exception as exc:
        return _fail(exc)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    return _ok(
        "Milvus is reachable.",
        collections_count=len(collections),
        latency_ms=round((perf_counter() - start) * 1000, 2),
    )


def _check_object_storage() -> dict[str, Any]:
    if not settings.object_storage_enabled:
        return {
            "status": "skipped",
            "message": "Object storage is disabled.",
        }

    start = perf_counter()
    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
            config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 1}),
        )
        response = client.list_buckets()
    except (BotoCoreError, ClientError) as exc:
        return _fail(exc)

    return _ok(
        "Object storage is reachable.",
        buckets_count=len(response.get("Buckets", [])),
        latency_ms=round((perf_counter() - start) * 1000, 2),
    )
