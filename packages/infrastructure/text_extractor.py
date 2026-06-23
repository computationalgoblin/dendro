"""Text extractors for document import pipeline (B17-T02, I02).

Provides:
  - TextExtractor: ABC for text extraction
  - PlainTextExtractor: extracts .txt files, segments by paragraphs
  - MarkdownExtractor: extracts .md files, preserves headings/lists
  - PDFExtractor: extracts .pdf files via pymupdf/pdfplumber (lazy import)
  - create_extractor: factory by ImportFormat
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.domain.import_models import DocumentSegment, ImportFormat
from packages.domain.result import Error as Err
from packages.domain.result import Ok, Result

# ═══════════════════════════════════════════════════════════════════════
# Chunking con tamaño objetivo (I11)
# ═══════════════════════════════════════════════════════════════════════
#
# El troceado estructural produce un chunk por párrafo: en documentos grandes,
# miles de segmentos diminutos que son malas unidades de recuperación para el
# RAG (y antes, una llamada IA por cada uno). `_pack_chunks` fusiona párrafos
# adyacentes hasta un tamaño objetivo y parte los gigantes, conservando las
# fronteras de encabezado/lista. Versión de troceado sellada en metadata para
# permitir migración aditiva (proyectos viejos quedan en la versión 1).
CHUNK_TARGET_CHARS = 1200  # objetivo de fusión de párrafos cortos
CHUNK_MAX_CHARS = 2000  # tope duro: por encima, se parte por frase
CHUNK_OVERLAP_CHARS = 0  # solapamiento entre chunks (reservado; sin aplicar aún)
CHUNKING_VERSION = 2  # versión del troceado de los segmentos nuevos

_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+")


def _resolve_chunk_target() -> int:
    """Tamaño objetivo de chunk, configurable por ``NARRATIVE_CHUNK_TARGET_CHARS``.

    ``0`` desactiva el empaquetado (comportamiento histórico: un chunk por
    párrafo) — útil para comparar retrieval antes/después.
    """
    raw = os.environ.get("NARRATIVE_CHUNK_TARGET_CHARS", "")
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return CHUNK_TARGET_CHARS


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
        path = Path(file_path)
        raw_result = _read_utf8_file(path)
        if isinstance(raw_result, Err):
            return raw_result
        raw = raw_result.value

        if not raw.strip():
            return Ok([])

        return Ok(_segments_from_text_chunks(
            chunks=_pack_chunks(
                _plain_text_chunks(raw),
                target_chars=_resolve_chunk_target(),
                max_chars=CHUNK_MAX_CHARS,
                overlap_chars=CHUNK_OVERLAP_CHARS,
            ),
            source_id=source_id,
            file_path=path,
            format_name=ImportFormat.TEXT_PLAIN.value,
            extraction_method="plain_text",
            confidence=1.0,
        ))


# ═══════════════════════════════════════════════════════════════════════
# MarkdownExtractor
# ═══════════════════════════════════════════════════════════════════════


class MarkdownExtractor(TextExtractor):
    """Extracts Markdown files while preserving heading/list structure."""

    supported_format = ImportFormat.MARKDOWN

    def extract(self, file_path: Path, source_id: str) -> Result[list[DocumentSegment], str]:
        path = Path(file_path)
        raw_result = _read_utf8_file(path)
        if isinstance(raw_result, Err):
            return raw_result
        raw = raw_result.value

        if not raw.strip():
            return Ok([])

        return Ok(_segments_from_text_chunks(
            chunks=_pack_chunks(
                _markdown_chunks(raw),
                target_chars=_resolve_chunk_target(),
                max_chars=CHUNK_MAX_CHARS,
                overlap_chars=CHUNK_OVERLAP_CHARS,
            ),
            source_id=source_id,
            file_path=path,
            format_name=ImportFormat.MARKDOWN.value,
            extraction_method="markdown",
            confidence=1.0,
        ))


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
                    segments.extend(_pdf_page_segments(
                        source_id=source_id,
                        file_path=path,
                        text=text,
                        page_num=page_num,
                        base_offset=offset,
                        base_order=len(segments),
                        extraction_method="pymupdf",
                    ))
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
                        segments.extend(_pdf_page_segments(
                            source_id=source_id,
                            file_path=path,
                            text=text,
                            page_num=page_num,
                            base_offset=offset,
                            base_order=len(segments),
                            extraction_method="pdfplumber",
                        ))
                        offset += len(text) + 1
            return Ok(segments)
        except Exception as e:
            return Err(f"PDF extraction failed (pdfplumber): {e}")


# ═══════════════════════════════════════════════════════════════════════
# ExtractorFactory
# ═══════════════════════════════════════════════════════════════════════


_EXTRACTOR_REGISTRY = {
    ImportFormat.TEXT_PLAIN: PlainTextExtractor,
    ImportFormat.MARKDOWN: MarkdownExtractor,
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
    try:
        parsed_format = format if isinstance(format, ImportFormat) else ImportFormat(format)
    except ValueError:
        parsed_format = format
    cls = _EXTRACTOR_REGISTRY.get(parsed_format)
    if cls is None:
        raise ValueError(f"Unsupported import format: {format}")
    return cls()


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class _TextChunk:
    text: str
    section: str
    start_offset: int
    end_offset: int
    section_path: str = ""
    block_type: str = "paragraph"
    heading_level: int | None = None


def _read_utf8_file(path: Path) -> Result[str, str]:
    if not path.exists():
        return Err(f"File not found: {path}")
    if not path.is_file():
        return Err(f"Not a file: {path}")
    try:
        return Ok(path.read_text(encoding="utf-8"))
    except Exception as e:
        return Err(f"Failed to read file: {e}")


def _line_offsets(text: str) -> list[tuple[str, int, int]]:
    offset = 0
    rows: list[tuple[str, int, int]] = []
    for line in text.splitlines(keepends=True):
        end = offset + len(line)
        rows.append((line, offset, end))
        offset = end
    return rows


def _first_content_line(text: str, fallback: str = "") -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.lstrip("#").strip() or fallback
    return fallback


def _plain_text_chunks(text: str) -> list[_TextChunk]:
    chunks: list[_TextChunk] = []
    buffer: list[str] = []
    start_offset: int | None = None
    end_offset = 0

    def flush() -> None:
        nonlocal buffer, start_offset, end_offset
        if start_offset is None:
            return
        raw = "".join(buffer).strip()
        if raw:
            section = _first_content_line(raw, "Sin seccion")
            chunks.append(_TextChunk(
                text=raw,
                section=section,
                section_path=section,
                start_offset=start_offset,
                end_offset=end_offset,
            ))
        buffer = []
        start_offset = None

    for line, line_start, line_end in _line_offsets(text):
        if not line.strip():
            flush()
            continue
        if start_offset is None:
            start_offset = line_start
        buffer.append(line)
        end_offset = line_end
    flush()
    return chunks


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")


def _markdown_chunks(text: str) -> list[_TextChunk]:
    chunks: list[_TextChunk] = []
    heading_stack: list[tuple[int, str]] = []
    buffer: list[str] = []
    start_offset: int | None = None
    end_offset = 0

    def section_path() -> str:
        return " > ".join(title for _, title in heading_stack)

    def current_section(fallback: str = "Sin seccion") -> str:
        return heading_stack[-1][1] if heading_stack else fallback

    def block_type(raw: str) -> str:
        lines = [line for line in raw.splitlines() if line.strip()]
        if lines and all(_LIST_RE.match(line) for line in lines):
            return "list"
        return "paragraph"

    def flush() -> None:
        nonlocal buffer, start_offset, end_offset
        if start_offset is None:
            return
        raw = "".join(buffer).strip()
        if raw:
            fallback = _first_content_line(raw, "Sin seccion")
            chunks.append(_TextChunk(
                text=raw,
                section=current_section(fallback),
                section_path=section_path() or fallback,
                start_offset=start_offset,
                end_offset=end_offset,
                block_type=block_type(raw),
            ))
        buffer = []
        start_offset = None

    for line, line_start, line_end in _line_offsets(text):
        stripped = line.strip()
        heading = _HEADING_RE.match(stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            chunks.append(_TextChunk(
                text=stripped,
                section=title,
                section_path=section_path(),
                start_offset=line_start,
                end_offset=line_end,
                block_type="heading",
                heading_level=level,
            ))
            continue
        if not stripped:
            flush()
            continue
        if start_offset is None:
            start_offset = line_start
        buffer.append(line)
        end_offset = line_end
    flush()
    return chunks


def _make_chunk_id(source_id: str, order: int) -> str:
    prefix = re.sub(r"[^A-Za-z0-9_-]+", "-", source_id or "source").strip("-") or "source"
    return f"{prefix}-chunk-{order:04d}"


def _normalized_text(text: str) -> str:
    return " ".join(text.split())


def _split_spans(text: str, max_chars: int) -> list[tuple[int, int]]:
    """Particiona ``text`` en spans (start, end) cada uno de ≤ ``max_chars``.

    Corta preferentemente en frontera de frase; si no hay, en el último espacio;
    en último término, corte duro. Los spans son posiciones exactas dentro de
    ``text`` (offsets monótonos, sin pérdida).
    """
    spans: list[tuple[int, int]] = []
    n = len(text)
    pos = 0
    while pos < n:
        end = min(pos + max_chars, n)
        if end < n:
            window = text[pos:end]
            matches = list(_SENTENCE_END_RE.finditer(window))
            if matches:
                end = pos + matches[-1].end()
            else:
                ws = window.rfind(" ")
                if ws > 0:
                    end = pos + ws + 1
        spans.append((pos, end))
        pos = end
    return spans or [(0, n)]


def _split_oversized_chunk(chunk: _TextChunk, max_chars: int) -> list[_TextChunk]:
    """Parte un chunk mayor que ``max_chars`` en sub-chunks por frase."""
    if max_chars <= 0 or len(chunk.text) <= max_chars:
        return [chunk]
    pieces: list[_TextChunk] = []
    for start, end in _split_spans(chunk.text, max_chars):
        pieces.append(_TextChunk(
            text=chunk.text[start:end].rstrip(),
            section=chunk.section,
            start_offset=chunk.start_offset + start,
            end_offset=chunk.start_offset + end,
            section_path=chunk.section_path,
            block_type=chunk.block_type,
            heading_level=chunk.heading_level,
        ))
    return pieces


def _merge_paragraph_group(group: list[_TextChunk]) -> _TextChunk:
    """Funde un grupo de chunks de párrafo adyacentes en uno solo (sin pérdida)."""
    if len(group) == 1:
        return group[0]
    first, last = group[0], group[-1]
    return _TextChunk(
        text="\n\n".join(c.text for c in group),
        section=first.section,
        start_offset=first.start_offset,
        end_offset=last.end_offset,
        section_path=first.section_path,
        block_type="paragraph",
        heading_level=None,
    )


def _pack_chunks(
    chunks: list[_TextChunk],
    *,
    target_chars: int,
    max_chars: int,
    overlap_chars: int = 0,
) -> list[_TextChunk]:
    """Agrupa párrafos adyacentes hasta ``target_chars`` y parte los gigantes.

    Solo se fusionan chunks ``paragraph`` consecutivos; ``heading``/``list`` (y
    cualquier no-párrafo) pasan intactos y actúan de frontera, preservando la
    estructura del documento. ``target_chars <= 0`` desactiva el empaquetado
    (devuelve los chunks tal cual: troceado histórico por párrafo).
    """
    if target_chars <= 0 or not chunks:
        return list(chunks)
    out: list[_TextChunk] = []
    group: list[_TextChunk] = []
    group_len = 0

    def flush() -> None:
        nonlocal group, group_len
        if not group:
            return
        out.extend(_split_oversized_chunk(_merge_paragraph_group(group), max_chars))
        group = []
        group_len = 0

    for chunk in chunks:
        if chunk.block_type != "paragraph":
            flush()
            out.extend(_split_oversized_chunk(chunk, max_chars))
            continue
        chunk_len = len(chunk.text)
        if group and group_len + chunk_len > target_chars:
            flush()
        group.append(chunk)
        group_len += chunk_len + 2  # separador "\n\n"
    flush()
    return out


def _segments_from_text_chunks(
    chunks: list[_TextChunk],
    source_id: str,
    file_path: Path,
    format_name: str,
    extraction_method: str,
    confidence: float,
    *,
    page_start: int | None = None,
    page_end: int | None = None,
    base_order: int = 0,
    base_offset: int = 0,
) -> list[DocumentSegment]:
    segments: list[DocumentSegment] = []
    for index, chunk in enumerate(chunks, start=1):
        order = base_order + index
        chunk_id = _make_chunk_id(source_id, order)
        metadata: dict[str, Any] = {
            "format": format_name,
            "file_name": file_path.name,
            "file_path": str(file_path),
            "source_id": source_id,
            "chunk_id": chunk_id,
            "chunk_order": order,
            "order": order,
            "chunking_version": CHUNKING_VERSION,
            "section": chunk.section,
            "section_path": chunk.section_path or chunk.section,
            "block_type": chunk.block_type,
            "page": page_start,
            "page_start": page_start,
            "page_end": page_end,
            "char_start": base_offset + chunk.start_offset,
            "char_end": base_offset + chunk.end_offset,
            "normalized_text": _normalized_text(chunk.text),
            "extraction_method": extraction_method,
            "encoding": "utf-8" if format_name != ImportFormat.PDF.value else None,
        }
        if chunk.heading_level is not None:
            metadata["heading_level"] = chunk.heading_level
        if format_name == ImportFormat.PDF.value:
            metadata["extractor"] = extraction_method

        segments.append(DocumentSegment(
            id=chunk_id,
            source_id=source_id,
            section=chunk.section,
            raw_text=chunk.text,
            start_offset=base_offset + chunk.start_offset,
            end_offset=base_offset + chunk.end_offset,
            confidence=confidence,
            metadata=metadata,
        ))
    return segments


def _pdf_page_segments(
    source_id: str,
    file_path: Path,
    text: str,
    page_num: int,
    base_offset: int,
    base_order: int,
    extraction_method: str,
) -> list[DocumentSegment]:
    chunks = _plain_text_chunks(text)
    if not chunks:
        return []
    for idx, chunk in enumerate(chunks):
        chunks[idx] = _TextChunk(
            text=chunk.text,
            section=chunk.section or f"Page {page_num}",
            section_path=f"Page {page_num}",
            start_offset=chunk.start_offset,
            end_offset=chunk.end_offset,
            block_type=chunk.block_type,
            heading_level=chunk.heading_level,
        )
    return _segments_from_text_chunks(
        chunks=_pack_chunks(
            chunks,
            target_chars=_resolve_chunk_target(),
            max_chars=CHUNK_MAX_CHARS,
            overlap_chars=CHUNK_OVERLAP_CHARS,
        ),
        source_id=source_id,
        file_path=file_path,
        format_name=ImportFormat.PDF.value,
        extraction_method=extraction_method,
        confidence=0.9,
        page_start=page_num,
        page_end=page_num,
        base_order=base_order,
        base_offset=base_offset,
    )


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split text by blank lines into sections.

    Returns list of (section_title, section_body) tuples.
    The title is the first non-empty line of each block.

    Kept for B17 compatibility; I02 extractors use _plain_text_chunks.
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
