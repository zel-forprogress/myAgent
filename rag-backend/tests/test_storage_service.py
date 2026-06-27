from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.services.storage_service import (
    detect_file_type,
    extract_filename,
    is_object_storage_source,
    is_managed_upload_source,
    normalize_source,
    parse_object_source,
    build_object_source,
    build_knowledge_base_bucket_name,
)


class TestNormalizeSource:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows backslash separator")
    def test_windows_path(self):
        assert normalize_source("data\\docs\\file.txt") == "data/docs/file.txt"

    def test_already_posix(self):
        assert normalize_source("data/docs/file.txt") == "data/docs/file.txt"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows backslash separator")
    def test_absolute_windows_path(self):
        result = normalize_source("C:\\Users\\test.txt")
        assert "\\" not in result


class TestDetectFileType:
    def test_txt(self):
        assert detect_file_type("doc.txt") == "txt"

    def test_pdf(self):
        assert detect_file_type("report.PDF") == "pdf"

    def test_docx(self):
        assert detect_file_type("notes.docx") == "docx"

    def test_markdown(self):
        assert detect_file_type("README.md") == "md"

    def test_unknown(self):
        assert detect_file_type("image.png") == "png"


class TestExtractFilename:
    def test_simple(self):
        assert extract_filename("data/docs/report.pdf") == "report.pdf"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows backslash separator")
    def test_windows_path(self):
        assert extract_filename("C:\\Users\\zlx15\\Desktop\\file.txt") == "file.txt"

    def test_no_directory(self):
        assert extract_filename("readme.md") == "readme.md"


class TestIsObjectStorageSource:
    def test_s3_prefix(self):
        assert is_object_storage_source("s3://bucket/key.txt") is True

    def test_local_path(self):
        assert is_object_storage_source("data/docs/file.txt") is False

    def test_filesystem_path(self):
        assert is_object_storage_source("/var/data/file.pdf") is False


class TestIsManagedUploadSource:
    def test_managed_path(self):
        assert is_managed_upload_source("data/docs/uploads/kb/doc.txt") is True

    def test_non_managed_path(self):
        assert is_managed_upload_source("data/docs/other.txt") is False

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows backslash separator")
    def test_windows_managed_path(self):
        assert is_managed_upload_source("data\\docs\\uploads\\kb\\file.pdf") is True


class TestParseObjectSource:
    def test_valid_s3_url(self):
        bucket, key = parse_object_source("s3://my-bucket/path/to/file.txt")
        assert bucket == "my-bucket"
        assert key == "path/to/file.txt"

    def test_invalid_scheme_raises(self):
        with pytest.raises(ValueError, match="Invalid object storage source"):
            parse_object_source("http://example.com/file.txt")

    def test_no_bucket_raises(self):
        with pytest.raises(ValueError, match="Invalid object storage source"):
            parse_object_source("s3:///file.txt")


class TestBuildObjectSource:
    def test_basic(self):
        source = build_object_source("bucket", "key/file.txt")
        assert source == "s3://bucket/key/file.txt"


class TestBuildKnowledgeBaseBucketName:
    def test_basic(self):
        name = build_knowledge_base_bucket_name("my-kb")
        assert name.startswith("myagent-docs-")
        assert "my-kb" in name

    def test_long_name_truncated(self):
        very_long = "a" * 80
        name = build_knowledge_base_bucket_name(very_long)
        assert len(name) <= 63
