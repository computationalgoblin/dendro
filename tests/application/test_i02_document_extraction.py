from __future__ import annotations

from pathlib import Path

import pytest

from packages.application.import_service import ImportService
from packages.domain.import_models import ImportFormat
from packages.domain.project import Project
from packages.domain.result import is_ok, unwrap
from packages.infrastructure.text_extractor import MarkdownExtractor, PDFExtractor, PlainTextExtractor


class FakeProjectService:
    def __init__(self, project=None, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i02-project.json")


def test_i02_txt_simple_extraction_preserves_text_and_chunk_metadata(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text(
        "Primer bloque\n"
        "Linea narrativa completa.\n\n"
        "Segundo bloque\n"
        "Otra linea.",
        encoding="utf-8",
    )

    result = PlainTextExtractor().extract(path, "src-i02")

    assert is_ok(result)
    segments = unwrap(result)
    # I11: dos bloques cortos se fusionan en un chunk de tamaño objetivo.
    assert len(segments) == 1
    assert "Primer bloque" in segments[0].raw_text
    assert "Linea narrativa completa." in segments[0].raw_text
    assert "Segundo bloque" in segments[0].raw_text
    assert [s.metadata["chunk_order"] for s in segments] == [1]
    assert all(s.id == s.metadata["chunk_id"] for s in segments)
    assert all(s.metadata["file_name"] == "notes.txt" for s in segments)
    assert all("page_start" in s.metadata for s in segments)


def test_i02_markdown_import_creates_review_basket_with_document_metadata(tmp_path):
    path = tmp_path / "world.md"
    path.write_text(
        "# Reino de Lume\n"
        "El reino aparece en los mapas antiguos.\n\n"
        "## Casas\n"
        "- Casa Sol\n"
        "- Casa Mar\n",
        encoding="utf-8",
    )
    project = Project(name="I02")
    service = ImportService(project_service=FakeProjectService(project, tmp_path / "project.json"))

    result = service.import_document(path, ImportFormat.MARKDOWN)

    assert is_ok(result)
    basket = unwrap(result)
    assert basket in project.import_baskets
    assert basket.metadata["document_id"] == basket.source_id
    assert basket.metadata["file_name"] == "world.md"
    assert basket.metadata["import_format"] == ImportFormat.MARKDOWN.value
    assert basket.metadata["extraction_warnings"] == []
    assert len(basket.segments) >= 4
    assert {s.metadata["format"] for s in basket.segments} == {ImportFormat.MARKDOWN.value}
    assert any(s.raw_text == "# Reino de Lume" for s in basket.segments)
    assert any(s.metadata["block_type"] == "list" and "Casa Sol" in s.raw_text for s in basket.segments)


def test_i02_empty_markdown_does_not_crash(tmp_path):
    path = tmp_path / "empty.md"
    path.write_text("  \n\n", encoding="utf-8")

    result = MarkdownExtractor().extract(path, "src-i02")

    assert is_ok(result)
    assert unwrap(result) == []


def test_i02_pdf_textual_extraction_preserves_page_metadata(tmp_path):
    fitz = pytest.importorskip("fitz", reason="pymupdf not installed")

    path = tmp_path / "pages.pdf"
    doc = fitz.open()
    first = doc.new_page()
    first.insert_text((72, 72), "Primera pagina PDF", fontsize=12)
    second = doc.new_page()
    second.insert_text((72, 72), "Segunda pagina PDF", fontsize=12)
    doc.save(str(path))
    doc.close()

    result = PDFExtractor().extract(path, "src-i02")

    assert is_ok(result)
    segments = unwrap(result)
    pages = [segment.metadata["page_start"] for segment in segments]
    assert 1 in pages
    assert 2 in pages
    assert [segment.metadata["chunk_order"] for segment in segments] == list(range(1, len(segments) + 1))
    assert all(segment.metadata["extractor"] == "pymupdf" for segment in segments)
