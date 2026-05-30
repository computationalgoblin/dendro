"""Import models — domain models for document import pipeline.

Provides ``ImportFormat``, ``ImportReviewState``, ``DocumentSegment``,
``ImportCandidate``, and ``ImportBasket`` for the Bloque 17 import
pipeline (§17.2, §17.3, §17.4).

stdlib-only — no dependencies on extraction, IA, or external libs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class ImportFormat(str, Enum):
    """Supported document formats for import (§17.2)."""
    TEXT_PLAIN = "text_plain"
    PDF = "pdf"


class ImportReviewState(str, Enum):
    """Controlled review states for ImportCandidate (§17.4)."""
    PENDIENTE = "pendiente"
    ACEPTADO = "aceptado"
    EDITADO = "editado"
    RECHAZADO = "rechazado"
    FUSIONADO = "fusionado"
    PARCIAL = "parcial"


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _parse_review_state(value: Any) -> ImportReviewState:
    """Parse review_state from string or enum member, default PENDIENTE."""
    if isinstance(value, ImportReviewState):
        return value
    if isinstance(value, str):
        try:
            return ImportReviewState(value)
        except ValueError:
            pass
    return ImportReviewState.PENDIENTE


def _parse_float(value: Any, default: float = 1.0) -> float:
    """Parse confidence/float, default on failure."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_str_list(value: Any) -> list[str]:
    """Parse list of strings, return [] on failure."""
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return []


def _parse_dict_list(value: Any) -> list[dict]:
    """Parse list of dicts, return [] on failure."""
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    return []


def _parse_proposed_data(value: Any) -> dict[str, Any]:
    """Parse proposed_data, return {} on non-dict."""
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    return {}


def _parse_metadata(value: Any) -> dict[str, Any]:
    """Parse metadata dict, return {} on failure."""
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items()}
    return {}


def _parse_iso_datetime(value: Any) -> str:
    """Parse ISO-8601 string, fallback to now."""
    if isinstance(value, str):
        return value
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════
# DocumentSegment
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class DocumentSegment:
    """Fragment of a processed document.

    Fields (8):
      - id: UUID
      - source_id: associated Source
      - section: detected section/title
      - raw_text: text content
      - start_offset, end_offset: position in document
      - confidence: extraction confidence (0.0–1.0)
      - metadata: dict with page, block, extractor, warnings, etc.
    """

    id: str = ""
    source_id: str = ""
    section: str = ""
    raw_text: str = ""
    start_offset: int = 0
    end_offset: int = 0
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "section": self.section,
            "raw_text": self.raw_text,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentSegment:
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            source_id=data.get("source_id", ""),
            section=data.get("section", ""),
            raw_text=data.get("raw_text", ""),
            start_offset=int(data.get("start_offset", 0)),
            end_offset=int(data.get("end_offset", 0)),
            confidence=_parse_float(data.get("confidence"), 1.0),
            metadata=_parse_metadata(data.get("metadata")),
        )


# ═══════════════════════════════════════════════════════════════════════
# ImportCandidate
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ImportCandidate:
    """Candidate generated from a document segment.

    ``candidate_type`` uses ``CandidateType`` values from B14
    (ENTIDAD, RELACION, FUENTE, CAMBIO, …) with ``str`` fallback.

    Fields (9):
      - id: UUID
      - segment_id: source DocumentSegment
      - candidate_type: CandidateType.value when applicable
      - proposed_data: proposed entity/relation/… data
      - proposed_relations: detected relations
      - confidence: extraction confidence (0.0–1.0)
      - possible_duplicates: IDs of similar entities
      - possible_contradictions: IDs with possible conflict
      - review_state: controlled ImportReviewState
    """

    id: str = ""
    segment_id: str = ""
    candidate_type: str = "entidad"
    proposed_data: dict[str, Any] = field(default_factory=dict)
    proposed_relations: list[dict] = field(default_factory=list)
    confidence: float = 0.5
    possible_duplicates: list[str] = field(default_factory=list)
    possible_contradictions: list[str] = field(default_factory=list)
    review_state: ImportReviewState = ImportReviewState.PENDIENTE

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "segment_id": self.segment_id,
            "candidate_type": self.candidate_type,
            "proposed_data": self.proposed_data,
            "proposed_relations": self.proposed_relations,
            "confidence": self.confidence,
            "possible_duplicates": self.possible_duplicates,
            "possible_contradictions": self.possible_contradictions,
            "review_state": self.review_state.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportCandidate:
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            segment_id=data.get("segment_id", ""),
            candidate_type=data.get("candidate_type", "entidad"),
            proposed_data=_parse_proposed_data(data.get("proposed_data")),
            proposed_relations=_parse_dict_list(data.get("proposed_relations")),
            confidence=_parse_float(data.get("confidence"), 0.5),
            possible_duplicates=_parse_str_list(data.get("possible_duplicates")),
            possible_contradictions=_parse_str_list(data.get("possible_contradictions")),
            review_state=_parse_review_state(data.get("review_state")),
        )


# ═══════════════════════════════════════════════════════════════════════
# ImportBasket
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ImportBasket:
    """Review basket for an imported document (§17.4).

    Fields (8):
      - id: UUID
      - source_id: the Source this basket is linked to
      - segments: extracted DocumentSegments
      - import_candidates: generated ImportCandidates
      - review_state: overall basket review state
      - created_at: ISO-8601 timestamp
      - updated_at: ISO-8601 timestamp
      - metadata: dict with source_id, file_path, format, timestamps
    """

    id: str = ""
    source_id: str = ""
    segments: list[DocumentSegment] = field(default_factory=list)
    import_candidates: list[ImportCandidate] = field(default_factory=list)
    review_state: str = "pendiente"
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "segments": [s.to_dict() for s in self.segments],
            "import_candidates": [c.to_dict() for c in self.import_candidates],
            "review_state": self.review_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportBasket:
        segments_data = data.get("segments", [])
        segments = [
            DocumentSegment.from_dict(s) if isinstance(s, dict) else s
            for s in (segments_data if isinstance(segments_data, list) else [])
        ]
        candidates_data = data.get("import_candidates", [])
        candidates = [
            ImportCandidate.from_dict(c) if isinstance(c, dict) else c
            for c in (candidates_data if isinstance(candidates_data, list) else [])
        ]
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            source_id=data.get("source_id", ""),
            segments=segments,
            import_candidates=candidates,
            review_state=data.get("review_state", "pendiente"),
            created_at=data.get("created_at") or now,
            updated_at=data.get("updated_at") or now,
            metadata=_parse_metadata(data.get("metadata")),
        )
