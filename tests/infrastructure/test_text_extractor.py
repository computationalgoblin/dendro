"""Tests for text extractors (B17-T02)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from packages.domain.import_models import ImportFormat
from packages.domain.result import is_ok, is_error, unwrap
from packages.infrastructure.text_extractor import (
    PlainTextExtractor,
    PDFExtractor,
    create_extractor,
)


# ═══════════════════════════════════════════════════════════════════════
# PlainTextExtractor
# ═══════════════════════════════════════════════════════════════════════


class TestPlainTextExtractor:
    def test_extract_segments_by_paragraphs(self):
        extractor = PlainTextExtractor()
        content = (
            "Section One\n"
            "This is the first section.\n"
            "It has multiple lines.\n"
            "\n"
            "Section Two\n"
            "This is section two.\n"
            "\n"
            "Section Three\n"
            "Only one line here."
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            path = Path(f.name)

        try:
            result = extractor.extract(path, "src_test")
            assert is_ok(result)
            segments = unwrap(result)
            assert len(segments) == 3
            assert segments[0].section == "Section One"
            assert segments[0].confidence == 1.0
            assert segments[0].source_id == "src_test"
            assert segments[0].metadata["format"] == "text_plain"
            assert "first section" in segments[0].raw_text
            assert segments[1].section == "Section Two"
            assert segments[2].section == "Section Three"
        finally:
            path.unlink(missing_ok=True)

    def test_extract_empty_file_returns_ok_empty(self):
        extractor = PlainTextExtractor()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            path = Path(f.name)

        try:
            result = extractor.extract(path, "src_test")
            assert is_ok(result)
            segments = unwrap(result)
            assert segments == []
        finally:
            path.unlink(missing_ok=True)

    def test_extract_whitespace_only_returns_empty(self):
        extractor = PlainTextExtractor()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("   \n\n  \n")
            path = Path(f.name)

        try:
            result = extractor.extract(path, "src_test")
            assert is_ok(result)
            segments = unwrap(result)
            assert segments == []
        finally:
            path.unlink(missing_ok=True)

    def test_extract_nonexistent_file_returns_error(self):
        extractor = PlainTextExtractor()
        result = extractor.extract(Path("/tmp/does_not_exist_12345.txt"), "src_test")
        assert is_error(result)

    def test_extract_not_a_file_returns_error(self):
        extractor = PlainTextExtractor()
        result = extractor.extract(Path("/tmp"), "src_test")  # directory
        assert is_error(result)

    def test_supported_format(self):
        assert PlainTextExtractor().supported_format == ImportFormat.TEXT_PLAIN

    def test_single_line_file(self):
        extractor = PlainTextExtractor()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Just one line")
            path = Path(f.name)

        try:
            result = extractor.extract(path, "src_test")
            assert is_ok(result)
            segments = unwrap(result)
            assert len(segments) == 1
            assert segments[0].raw_text == "Just one line"
        finally:
            path.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# PDFExtractor
# ═══════════════════════════════════════════════════════════════════════


class TestPDFExtractor:
    def test_supported_format(self):
        assert PDFExtractor().supported_format == ImportFormat.PDF

    def test_nonexistent_file_returns_error(self):
        extractor = PDFExtractor()
        result = extractor.extract(Path("/tmp/does_not_exist_12345.pdf"), "src_test")
        assert is_error(result)

    def test_module_imports_without_pdf_library(self):
        """PDFExtractor should not break on import when fitz/pdfplumber are missing."""
        extractor = PDFExtractor()
        # Just instantiating should work
        assert extractor.supported_format == ImportFormat.PDF
        # Calling extract on nonexistent file returns error before trying to import
        result = extractor.extract(Path("/tmp/nonexistent.pdf"), "src_test")
        assert is_error(result)

    def test_error_when_no_pdf_library(self):
        """When no PDF library is installed, extraction should give error."""
        extractor = PDFExtractor()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"not a real pdf but exists as file")
            path = Path(f.name)

        try:
            result = extractor.extract(path, "src_test")
            # Should error because content isn't parseable OR no library
            assert is_error(result)
        finally:
            path.unlink(missing_ok=True)


try:
    import fitz
    _FITZ_AVAILABLE = True
except ImportError:
    _FITZ_AVAILABLE = False


@pytest.mark.skipif(not _FITZ_AVAILABLE, reason="pymupdf not installed")
class TestPDFExtractorWithFitz:
    def test_extract_with_fitz(self):
        """Test extraction with pymupdf (only runs if installed)."""
        import fitz

        # Create a minimal valid PDF
        pdf_path = Path(tempfile.mktemp(suffix=".pdf"))
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello PDF world!", fontsize=12)
        doc.save(str(pdf_path))
        doc.close()

        try:
            extractor = PDFExtractor()
            result = extractor.extract(pdf_path, "src_test")
            assert is_ok(result)
            segments = unwrap(result)
            assert len(segments) >= 1
            assert segments[0].source_id == "src_test"
            assert segments[0].confidence == 0.9
            assert "Hello PDF world" in segments[0].raw_text
            assert segments[0].metadata["extractor"] == "pymupdf"
        finally:
            pdf_path.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# ExtractorFactory
# ═══════════════════════════════════════════════════════════════════════


class TestExtractorFactory:
    def test_creates_plain_text_extractor(self):
        extractor = create_extractor(ImportFormat.TEXT_PLAIN)
        assert isinstance(extractor, PlainTextExtractor)

    def test_creates_pdf_extractor(self):
        extractor = create_extractor(ImportFormat.PDF)
        assert isinstance(extractor, PDFExtractor)

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unsupported import format"):
            create_extractor("unknown")  # type: ignore
