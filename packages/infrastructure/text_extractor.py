"""Text extractors for document import pipeline (B17-T02).

Provides:
  - TextExtractor: ABC for text extraction
  - PlainTextExtractor: extracts .txt files, segments by paragraphs
  - PDFExtractor: extracts .pdf files via pymupdf/pdfplumber (lazy import)
  - create_extractor: factory by ImportFormat
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from packages.domain.import_models import DocumentSegment, ImportFormat
from packages.domain.result import Result, Ok, Error as Err


# ═══════════════════════════════════════════════════════════════════════
# TextExtractor (ABC)
# ═══════════════════════════════════════════════════════════════════════


class TextExtractor(ABC):
    """Abstract base for text extractors."""

    @abstractmethod
    def extract(self, file_path: Path, source_id: str) -> Result[list[DocumentSegment], str]:
        """Extract text from a file and return segments.

        Args:
            file_path: Path to the document file.
            source_id: Source UUID to assign to every segment.

        Returns:
            Ok(list[DocumentSegment]) on success, Err(str) on failure.
        """
        ...

    @property
    @abstractmethod
    def supported_format(self) -> ImportFormat:
        """The ImportFormat this extractor handles."""
        ...


# ═══════════════════════════════════════════════════════════════════════
# PlainTextExtractor
# ═══════════════════════════════════════════════════════════════════════


class PlainTextExtractor(TextExtractor):
    """Extracts text from plain-text (.txt) files.

    Segments by blank lines (paragraphs/sections). Confidence = 1.0.
    """

    supported_format = ImportFormat.TEXT_PLAIN

    def extract(self, file_path: Path, source_id: str) -> Result[list[DocumentSegment], str]:
        # Validate file
        path = Path(file_path)
        if not path.exists():
            return Err(f"File not found: {path}")
        if not path.is_file():
            return Err(f"Not a file: {path}")

        try:
            raw = path.read_text(encoding="utf-8")
        except Exception as e:
            return Err(f"Failed to read file: {e}")

        if not raw.strip():
            return Ok([])

        # Segment by blank lines
        sections = _split_sections(raw)
        segments: list[DocumentSegment] = []
        offset = 0

        for section_title, section_text in sections:
            seg = DocumentSegment(
                source_id=source_id,
                section=section_title or "",
                raw_text=section_text.strip(),
                start_offset=offset,
                end_offset=offset + len(section_text),
                confidence=1.0,
                metadata={"format": "text_plain", "encoding": "utf-8"},
            )
            segments.append(seg)
            offset += len(section_text) + 1

        return Ok(segments)


# ═══════════════════════════════════════════════════════════════════════
# PDFExtractor
# ═══════════════════════════════════════════════════════════════════════


class PDFExtractor(TextExtractor):
    """Extracts text from PDF files via pymupdf (fitz) or pdfplumber.

    Uses lazy import — does NOT import fitz/pdfplumber at module level
    to avoid breaking imports when the library is not installed.

    Confidence = 0.9 (possible formatting loss).
    """

    supported_format = ImportFormat.PDF

    def extract(self, file_path: Path, source_id: str) -> Result[list[DocumentSegment], str]:
        path = Path(file_path)
        if not path.exists():
            return Err(f"File not found: {path}")
        if not path.is_file():
            return Err(f"Not a file: {path}")

        # Try pymupdf first, then pdfplumber
        fitz = self._try_import_fitz()
        if fitz is not None:
            return self._extract_with_fitz(path, source_id, fitz)

        pdfplumber = self._try_import_pdfplumber()
        if pdfplumber is not None:
            return self._extract_with_pdfplumber(path, source_id, pdfplumber)

        return Err(
            "PDF library not installed. "
            "Run: pip install pymupdf  (recommended)  or  pip install pdfplumber"
        )

    @staticmethod
    def _try_import_fitz():
        """Lazy import of fitz (pymupdf). Returns module or None."""
        try:
            return __import__("fitz")
        except ImportError:
            return None

    @staticmethod
    def _try_import_pdfplumber():
        """Lazy import of pdfplumber. Returns module or None."""
        try:
            return __import__("pdfplumber")
        except ImportError:
            return None

    def _extract_with_fitz(
        self, path: Path, source_id: str, fitz
    ) -> Result[list[DocumentSegment], str]:
        try:
            doc = fitz.open(str(path))
            segments: list[DocumentSegment] = []
            offset = 0
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
                if text.strip():
                    seg = DocumentSegment(
                        source_id=source_id,
                        section=f"Page {page_num}",
                        raw_text=text.strip(),
                        start_offset=offset,
                        end_offset=offset + len(text),
                        confidence=0.9,
                        metadata={"page": page_num, "extractor": "pymupdf"},
                    )
                    segments.append(seg)
                    offset += len(text) + 1
            doc.close()
            return Ok(segments)
        except Exception as e:
            return Err(f"PDF extraction failed (fitz): {e}")

    def _extract_with_pdfplumber(
        self, path: Path, source_id: str, pdfplumber
    ) -> Result[list[DocumentSegment], str]:
        try:
            segments: list[DocumentSegment] = []
            offset = 0
            with pdfplumber.open(str(path)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    if text.strip():
                        seg = DocumentSegment(
                            source_id=source_id,
                            section=f"Page {page_num}",
                            raw_text=text.strip(),
                            start_offset=offset,
                            end_offset=offset + len(text),
                            confidence=0.9,
                            metadata={"page": page_num, "extractor": "pdfplumber"},
                        )
                        segments.append(seg)
                        offset += len(text) + 1
            return Ok(segments)
        except Exception as e:
            return Err(f"PDF extraction failed (pdfplumber): {e}")


# ═══════════════════════════════════════════════════════════════════════
# ExtractorFactory
# ═══════════════════════════════════════════════════════════════════════


_EXTRACTOR_REGISTRY = {
    ImportFormat.TEXT_PLAIN: PlainTextExtractor,
    ImportFormat.PDF: PDFExtractor,
}


def create_extractor(format: ImportFormat) -> TextExtractor:
    """Create the appropriate TextExtractor for a given ImportFormat.

    Args:
        format: The import format enum member.

    Returns:
        A TextExtractor instance.

    Raises:
        ValueError: If the format is not supported.
    """
    cls = _EXTRACTOR_REGISTRY.get(format)
    if cls is None:
        raise ValueError(f"Unsupported import format: {format}")
    return cls()


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split text by blank lines into sections.

    Returns list of (section_title, section_body) tuples.
    The title is the first non-empty line of each block.
    """
    blocks = text.split("\n\n")
    sections: list[tuple[str, str]] = []
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        lines = stripped.split("\n")
        if len(lines) == 1:
            sections.append((lines[0], lines[0]))
        else:
            # First line is title candidate, rest is body
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else title
            sections.append((title, body))
    return sections
