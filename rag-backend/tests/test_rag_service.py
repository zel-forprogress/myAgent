from __future__ import annotations

import io

import pytest

from app.schemas import SourceChunk
from app.services.rag_service import (
    build_context,
    escape_milvus_string,
    extract_text_from_bytes,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_txt_or_md,
    is_valid_collection_name,
    source_variants,
)


class TestIsValidCollectionName:
    def test_valid_names(self):
        assert is_valid_collection_name("my_collection") is True
        assert is_valid_collection_name("kb_123") is True
        assert is_valid_collection_name("ABC") is True
        assert is_valid_collection_name("a") is True

    def test_empty_invalid(self):
        assert is_valid_collection_name("") is False

    def test_special_chars_invalid(self):
        assert is_valid_collection_name("my-collection") is False
        assert is_valid_collection_name("my collection") is False
        assert is_valid_collection_name("col!") is False
        assert is_valid_collection_name("中文") is False


class TestEscapeMilvusString:
    def test_no_escape_needed(self):
        assert escape_milvus_string("hello") == "hello"

    def test_escape_backslash(self):
        assert escape_milvus_string("path\\to") == "path\\\\to"

    def test_escape_double_quote(self):
        assert escape_milvus_string('hello"world') == 'hello\\"world'

    def test_escape_both(self):
        assert escape_milvus_string('a\\b"c') == 'a\\\\b\\"c'


class TestSourceVariants:
    def test_returns_set_with_original_and_normalized(self):
        variants = source_variants("data\\docs\\file.txt")
        assert "data\\docs\\file.txt" in variants
        assert "data/docs/file.txt" in variants
        assert "data\\docs\\file.txt" in variants

    def test_already_normalized(self):
        variants = source_variants("data/docs/file.txt")
        assert "data/docs/file.txt" in variants


class TestBuildContext:
    def test_empty_sources(self):
        assert build_context([]) == ""

    def test_single_source(self):
        sources = [SourceChunk(content="Hello world", source="test.txt", score=0.9)]
        result = build_context(sources)
        assert "片段 1:" in result
        assert "Hello world" in result

    def test_multiple_sources(self):
        sources = [
            SourceChunk(content="First chunk", source="a.txt", score=0.9),
            SourceChunk(content="Second chunk", source="b.txt", score=0.8),
        ]
        result = build_context(sources)
        assert "片段 1:" in result
        assert "片段 2:" in result
        assert "First chunk" in result
        assert "Second chunk" in result


class TestExtractTextFromTxtOrMd:
    def test_utf8_text(self):
        content = "Hello, 世界!".encode("utf-8")
        assert extract_text_from_txt_or_md(content) == "Hello, 世界!"

    def test_non_utf8_raises(self):
        content = "Hello".encode("utf-16")
        with pytest.raises(ValueError, match="UTF-8"):
            extract_text_from_txt_or_md(content)


class TestExtractTextFromBytes:
    def test_txt_file(self):
        content = "Simple text".encode("utf-8")
        assert extract_text_from_bytes(content, "doc.txt") == "Simple text"

    def test_md_file(self):
        content = "# Markdown".encode("utf-8")
        assert extract_text_from_bytes(content, "readme.md") == "# Markdown"

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            extract_text_from_bytes(b"test", "image.png")
