from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import re
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".xlsx",
    ".xls",
    ".pptx",
    ".html",
    ".htm",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tiff",
    ".tif",
    ".heif",
}
VALID_BUCKET_TOKEN_RE = re.compile(r"[^a-z0-9-]+")


@dataclass
class StoredFileMetadata:
    source: str
    provider: str
    bucket: str | None
    object_key: str | None
    content_type: str | None
    file_size: int
    uploaded_at: str


def normalize_source(path: str) -> str:
    if path.startswith("s3://"):
        return path
    return Path(path).as_posix()


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_document_path(path: str) -> Path:
    raw_path = Path(path)
    if raw_path.is_absolute():
        return raw_path
    return get_project_root() / raw_path


def is_object_storage_enabled() -> bool:
    return settings.object_storage_enabled and settings.object_storage_provider.lower() == "s3"


def is_object_storage_source(source: str) -> bool:
    return source.startswith("s3://")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
    )


def ensure_bucket_exists(bucket_name: str) -> None:
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=bucket_name)
        return
    except ClientError:
        pass

    create_kwargs = {"Bucket": bucket_name}
    if settings.s3_region and settings.s3_region != "us-east-1":
        create_kwargs["CreateBucketConfiguration"] = {
            "LocationConstraint": settings.s3_region,
        }
    client.create_bucket(**create_kwargs)


def build_knowledge_base_bucket_name(knowledge_base_slug: str) -> str:
    prefix = settings.object_storage_bucket.strip().lower() or "myagent-docs"
    prefix = VALID_BUCKET_TOKEN_RE.sub("-", prefix).strip("-") or "myagent-docs"
    slug = VALID_BUCKET_TOKEN_RE.sub("-", knowledge_base_slug.strip().lower()).strip("-") or "default"
    bucket_name = f"{prefix}-{slug}"

    if len(bucket_name) > 63:
        digest = hashlib.md5(bucket_name.encode("utf-8")).hexdigest()[:8]
        keep = max(1, 63 - len(digest) - 1)
        bucket_name = f"{bucket_name[:keep].rstrip('-')}-{digest}"

    return bucket_name.strip("-")


def parse_object_source(source: str) -> tuple[str, str]:
    parsed = urlparse(source)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Invalid object storage source: {source}")
    return parsed.netloc, parsed.path.lstrip("/")


def build_object_source(bucket: str, object_key: str) -> str:
    return f"s3://{bucket}/{object_key}"


def detect_file_type(path: str) -> str:
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix or "unknown"


def extract_filename(path: str) -> str:
    return Path(path).name


def build_uploaded_local_relative_path(filename: str, knowledge_base_slug: str) -> str:
    safe_name = Path(filename).name
    if not safe_name:
        raise ValueError("Uploaded file must have a valid filename.")

    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise ValueError(
            "Only .txt, .md, .pdf, .docx, Office, HTML, and common image files are supported right now."
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(safe_name).stem or "document"
    stored_name = f"{stem}_{timestamp}{suffix}"
    return normalize_source(
        str(Path("data") / "docs" / "uploads" / knowledge_base_slug / stored_name)
    )


def build_uploaded_object_key(filename: str, knowledge_base_slug: str) -> str:
    safe_name = Path(filename).name
    if not safe_name:
        raise ValueError("Uploaded file must have a valid filename.")

    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise ValueError(
            "Only .txt, .md, .pdf, .docx, Office, HTML, and common image files are supported right now."
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(safe_name).stem or "document"
    stored_name = f"{stem}_{timestamp}{suffix}"
    return stored_name


def guess_content_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def save_uploaded_file(
    filename: str,
    content: bytes,
    *,
    knowledge_base_slug: str,
) -> StoredFileMetadata:
    uploaded_at = datetime.utcnow().isoformat()
    content_type = guess_content_type(filename)
    file_size = len(content)

    if is_object_storage_enabled():
        bucket = build_knowledge_base_bucket_name(knowledge_base_slug)
        object_key = build_uploaded_object_key(filename, knowledge_base_slug)
        ensure_bucket_exists(bucket)
        client = get_s3_client()
        client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=content,
            ContentType=content_type,
        )
        return StoredFileMetadata(
            source=build_object_source(bucket, object_key),
            provider="s3",
            bucket=bucket,
            object_key=object_key,
            content_type=content_type,
            file_size=file_size,
            uploaded_at=uploaded_at,
        )

    relative_path = build_uploaded_local_relative_path(filename, knowledge_base_slug)
    target_path = resolve_document_path(relative_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)
    return StoredFileMetadata(
        source=normalize_source(relative_path),
        provider="local",
        bucket=None,
        object_key=None,
        content_type=content_type,
        file_size=file_size,
        uploaded_at=uploaded_at,
    )


def read_file_bytes(source: str) -> bytes:
    if is_object_storage_source(source):
        bucket, object_key = parse_object_source(source)
        response = get_s3_client().get_object(Bucket=bucket, Key=object_key)
        return response["Body"].read()

    file_path = resolve_document_path(source)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {source}")
    return file_path.read_bytes()


def get_stored_file_metadata(source: str) -> StoredFileMetadata:
    if is_object_storage_source(source):
        bucket, object_key = parse_object_source(source)
        response = get_s3_client().head_object(Bucket=bucket, Key=object_key)
        uploaded_at = response["LastModified"].replace(tzinfo=None).isoformat()
        return StoredFileMetadata(
            source=source,
            provider="s3",
            bucket=bucket,
            object_key=object_key,
            content_type=response.get("ContentType"),
            file_size=int(response.get("ContentLength", 0)),
            uploaded_at=uploaded_at,
        )

    file_path = resolve_document_path(source)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {source}")

    return StoredFileMetadata(
        source=normalize_source(source),
        provider="local",
        bucket=None,
        object_key=None,
        content_type=guess_content_type(file_path.name),
        file_size=file_path.stat().st_size,
        uploaded_at=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
    )


def delete_stored_file(source: str) -> None:
    if is_object_storage_source(source):
        bucket, object_key = parse_object_source(source)
        get_s3_client().delete_object(Bucket=bucket, Key=object_key)
        return

    file_path = resolve_document_path(source)
    if file_path.exists():
        file_path.unlink()


def delete_bucket_if_empty(bucket_name: str) -> None:
    client = get_s3_client()
    try:
        response = client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
    except ClientError:
        return

    if response.get("KeyCount", 0) > 0:
        return

    try:
        client.delete_bucket(Bucket=bucket_name)
    except ClientError:
        return


def is_managed_upload_source(source: str) -> bool:
    normalized = normalize_source(source)
    return normalized.startswith("data/docs/uploads/")


# ---------------------------------------------------------------------------
# S3 Multipart Upload helpers
# ---------------------------------------------------------------------------


@dataclass
class MultipartUploadContext:
    """Holds the state of an in-progress multipart upload."""

    upload_id: str
    bucket: str
    object_key: str


def init_multipart_upload(
    filename: str,
    knowledge_base_slug: str,
) -> MultipartUploadContext:
    """Create a new multipart upload and return its context."""
    bucket = build_knowledge_base_bucket_name(knowledge_base_slug)
    object_key = build_uploaded_object_key(filename, knowledge_base_slug)
    ensure_bucket_exists(bucket)
    client = get_s3_client()
    response = client.create_multipart_upload(Bucket=bucket, Key=object_key)
    return MultipartUploadContext(
        upload_id=response["UploadId"],
        bucket=bucket,
        object_key=object_key,
    )


def upload_part(
    ctx: MultipartUploadContext,
    part_number: int,
    data: bytes,
) -> dict:
    """Upload a single part and return ``{PartNumber, ETag}``."""
    client = get_s3_client()
    response = client.upload_part(
        Bucket=ctx.bucket,
        Key=ctx.object_key,
        UploadId=ctx.upload_id,
        PartNumber=part_number,
        Body=data,
    )
    return {"PartNumber": part_number, "ETag": response["ETag"]}


def complete_multipart_upload(
    ctx: MultipartUploadContext,
    parts: list[dict],
) -> None:
    """Complete the multipart upload by assembling the given parts."""
    client = get_s3_client()
    sorted_parts = sorted(parts, key=lambda p: p["PartNumber"])
    client.complete_multipart_upload(
        Bucket=ctx.bucket,
        Key=ctx.object_key,
        UploadId=ctx.upload_id,
        MultipartUpload={"Parts": sorted_parts},
    )


def list_uploaded_parts(
    ctx: MultipartUploadContext,
) -> list[dict]:
    """Return every part that has been uploaded so far."""
    client = get_s3_client()
    response = client.list_parts(
        Bucket=ctx.bucket,
        Key=ctx.object_key,
        UploadId=ctx.upload_id,
    )
    return [
        {
            "PartNumber": p["PartNumber"],
            "ETag": p["ETag"],
            "Size": p["Size"],
        }
        for p in response.get("Parts", [])
    ]


def abort_multipart_upload(
    ctx: MultipartUploadContext,
) -> None:
    """Abort the multipart upload and discard all uploaded parts."""
    client = get_s3_client()
    client.abort_multipart_upload(
        Bucket=ctx.bucket,
        Key=ctx.object_key,
        UploadId=ctx.upload_id,
    )


def build_stored_file_from_multipart(
    ctx: MultipartUploadContext,
) -> StoredFileMetadata:
    """Build a StoredFileMetadata for a completed multipart upload."""
    uploaded_at = datetime.utcnow().isoformat()
    return StoredFileMetadata(
        source=build_object_source(ctx.bucket, ctx.object_key),
        provider="s3",
        bucket=ctx.bucket,
        object_key=ctx.object_key,
        content_type=guess_content_type(ctx.object_key),
        file_size=0,  # Will be updated after completion
        uploaded_at=uploaded_at,
    )
