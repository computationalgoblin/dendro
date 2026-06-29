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
    MARKDOWN = "markdown"
    PDF = "pdf"


class ImportMode(str, Enum):
    """Tratamiento del documento importado (elegido por documento).

    - CANON: la pipeline extrae entidades/ramas/relaciones/anillos para
      revisión y eventual paso a canon (flujo histórico).
    - CONTEXTO: el documento enriquece el contexto de la IA como material de
      referencia permanente en el RAG; nunca propone candidatos de canon.
    """
    CANON = "canon"
    CONTEXTO = "contexto"


class ImportReviewState(str, Enum):
    """Controlled review states for ImportCandidate (§17.4)."""
    PENDIENTE = "pendiente"
    ACEPTADO = "aceptado"
    EDITADO = "editado"
    RECHAZADO = "rechazado"
    FUSIONADO = "fusionado"
    PARCIAL = "parcial"


class RelevanceTier(str, Enum):
    """Nivel de relevancia de un candidato consolidado (I30).

    - FUERTE: candidato destacado, presentado en primer plano.
    - MARGINAL: candidato plegado en sección secundaria; nunca se descarta.
    """
    FUERTE = "fuerte"
    MARGINAL = "marginal"


class DatingStatus(str, Enum):
    """Estado de datación temporal de una entidad consolidada (I29).

    - DATADO: fecha propuesta y válida dentro del rango de eras.
    - SIN_DATAR: el texto no permite datar (fecha nula).
    - FUERA_DE_RANGO: fecha propuesta fuera del rango de eras / incoherente.
    """
    DATADO = "datado"
    SIN_DATAR = "sin_datar"
    FUERA_DE_RANGO = "fuera_de_rango"


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


def _parse_int_opt(value: Any) -> int | None:
    """Parse optional integer (e.g. birth_year), None on missing/invalid."""
    if value is None:
        return None
    if isinstance(value, bool):  # bool es subclase de int; no lo queremos
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_relevance_tier(value: Any) -> RelevanceTier:
    """Parse RelevanceTier, default MARGINAL (conservador: no destaca de más)."""
    if isinstance(value, RelevanceTier):
        return value
    if isinstance(value, str):
        try:
            return RelevanceTier(value)
        except ValueError:
            pass
    return RelevanceTier.MARGINAL


def _parse_dating_status(value: Any) -> DatingStatus:
    """Parse DatingStatus, default SIN_DATAR."""
    if isinstance(value, DatingStatus):
        return value
    if isinstance(value, str):
        try:
            return DatingStatus(value)
        except ValueError:
            pass
    return DatingStatus.SIN_DATAR


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
# Grafo de candidatos consolidado (rediseño I25 — map→reduce)
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ConsolidatedEntity:
    """Entidad o rama única tras la reconciliación global (fase REDUCE).

    Sustituye, en el flujo CANON, a la fusión por nombre de ``ImportCandidate``.
    La identidad es estable dentro de un grafo vía ``provisional_id`` (p.ej.
    ``imp_e_0001`` para hojas, ``imp_b_0001`` para ramas); las relaciones y la
    pertenencia a ramas referencian ESE id, nunca el nombre.

    ``kind`` es ``"entity"`` (hoja) o ``"branch"`` (contenedor). Para ramas,
    ``member_ids`` lleva los ``provisional_id`` de sus miembros (I28).
    """

    provisional_id: str = ""
    kind: str = "entity"  # "entity" | "branch"
    name: str = ""
    aliases: list[str] = field(default_factory=list)
    entity_type: str = ""  # personaje, localizacion, … (hojas)
    branch_type: str = ""  # faccion, cultura, contenedor, … (ramas)
    summary: str = ""
    body: str = ""
    evidence: str = ""
    source_references: list[dict] = field(default_factory=list)
    birth_year: int | None = None
    death_year: int | None = None
    temporal_nature: str = ""
    layer_ids: list[str] = field(default_factory=list)
    member_ids: list[str] = field(default_factory=list)  # solo ramas
    mention_ids: list[str] = field(default_factory=list)  # trazas del MAP
    relevance: float = 0.5
    relevance_tier: RelevanceTier = RelevanceTier.MARGINAL
    confidence: float = 0.5
    dating_status: DatingStatus = DatingStatus.SIN_DATAR

    def to_dict(self) -> dict[str, Any]:
        return {
            "provisional_id": self.provisional_id,
            "kind": self.kind,
            "name": self.name,
            "aliases": self.aliases,
            "entity_type": self.entity_type,
            "branch_type": self.branch_type,
            "summary": self.summary,
            "body": self.body,
            "evidence": self.evidence,
            "source_references": self.source_references,
            "birth_year": self.birth_year,
            "death_year": self.death_year,
            "temporal_nature": self.temporal_nature,
            "layer_ids": self.layer_ids,
            "member_ids": self.member_ids,
            "mention_ids": self.mention_ids,
            "relevance": self.relevance,
            "relevance_tier": self.relevance_tier.value,
            "confidence": self.confidence,
            "dating_status": self.dating_status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsolidatedEntity:
        return cls(
            provisional_id=data.get("provisional_id", ""),
            kind=data.get("kind", "entity"),
            name=data.get("name", ""),
            aliases=_parse_str_list(data.get("aliases")),
            entity_type=data.get("entity_type", ""),
            branch_type=data.get("branch_type", ""),
            summary=data.get("summary", ""),
            body=data.get("body", ""),
            evidence=data.get("evidence", ""),
            source_references=_parse_dict_list(data.get("source_references")),
            birth_year=_parse_int_opt(data.get("birth_year")),
            death_year=_parse_int_opt(data.get("death_year")),
            temporal_nature=data.get("temporal_nature", ""),
            layer_ids=_parse_str_list(data.get("layer_ids")),
            member_ids=_parse_str_list(data.get("member_ids")),
            mention_ids=_parse_str_list(data.get("mention_ids")),
            relevance=_parse_float(data.get("relevance"), 0.5),
            relevance_tier=_parse_relevance_tier(data.get("relevance_tier")),
            confidence=_parse_float(data.get("confidence"), 0.5),
            dating_status=_parse_dating_status(data.get("dating_status")),
        )

    @property
    def is_branch(self) -> bool:
        return self.kind == "branch"


@dataclass
class ConsolidatedRelation:
    """Relación única tras la reconciliación (fase REDUCE).

    Los extremos referencian ``provisional_id`` de ``ConsolidatedEntity`` del
    mismo grafo — adiós a la resolución frágil por nombre. ``relation_type`` es
    un valor curado (``RelationType``) o ``"otro"``.
    """

    provisional_id: str = ""
    source_provisional_id: str = ""
    target_provisional_id: str = ""
    relation_type: str = "otro"
    summary: str = ""
    evidence: str = ""
    mention_ids: list[str] = field(default_factory=list)
    relevance: float = 0.5
    relevance_tier: RelevanceTier = RelevanceTier.MARGINAL
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "provisional_id": self.provisional_id,
            "source_provisional_id": self.source_provisional_id,
            "target_provisional_id": self.target_provisional_id,
            "relation_type": self.relation_type,
            "summary": self.summary,
            "evidence": self.evidence,
            "mention_ids": self.mention_ids,
            "relevance": self.relevance,
            "relevance_tier": self.relevance_tier.value,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConsolidatedRelation:
        return cls(
            provisional_id=data.get("provisional_id", ""),
            source_provisional_id=data.get("source_provisional_id", ""),
            target_provisional_id=data.get("target_provisional_id", ""),
            relation_type=data.get("relation_type", "otro"),
            summary=data.get("summary", ""),
            evidence=data.get("evidence", ""),
            mention_ids=_parse_str_list(data.get("mention_ids")),
            relevance=_parse_float(data.get("relevance"), 0.5),
            relevance_tier=_parse_relevance_tier(data.get("relevance_tier")),
            confidence=_parse_float(data.get("confidence"), 0.5),
        )


@dataclass
class ImportGraph:
    """Grafo de candidatos consolidado de un documento (fase REDUCE).

    Es el producto único que presenta el asistente de revisión (I31) y que se
    materializa atómicamente a canon al confirmar (I28). ``raw_mentions``
    conserva las menciones crudas del MAP para trazabilidad/auditoría.
    """

    entities: list[ConsolidatedEntity] = field(default_factory=list)
    relations: list[ConsolidatedRelation] = field(default_factory=list)
    raw_mentions: list[dict] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "raw_mentions": self.raw_mentions,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImportGraph:
        entities_data = data.get("entities", [])
        relations_data = data.get("relations", [])
        return cls(
            entities=[
                ConsolidatedEntity.from_dict(e)
                for e in (entities_data if isinstance(entities_data, list) else [])
                if isinstance(e, dict)
            ],
            relations=[
                ConsolidatedRelation.from_dict(r)
                for r in (relations_data if isinstance(relations_data, list) else [])
                if isinstance(r, dict)
            ],
            raw_mentions=_parse_dict_list(data.get("raw_mentions")),
            metadata=_parse_metadata(data.get("metadata")),
        )

    def entity_by_provisional_id(self, provisional_id: str) -> ConsolidatedEntity | None:
        """Localiza una entidad/rama por su id provisional (None si no existe)."""
        for entity in self.entities:
            if entity.provisional_id == provisional_id:
                return entity
        return None


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
    import_mode: str = "canon"  # ImportMode.value — baskets viejos = canon
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # Grafo consolidado del rediseño map→reduce (I25); None hasta correr REDUCE.
    graph: ImportGraph | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "segments": [s.to_dict() for s in self.segments],
            "import_candidates": [c.to_dict() for c in self.import_candidates],
            "review_state": self.review_state,
            "import_mode": self.import_mode,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "graph": self.graph.to_dict() if self.graph is not None else None,
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
        graph_data = data.get("graph")
        graph = ImportGraph.from_dict(graph_data) if isinstance(graph_data, dict) else None
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            source_id=data.get("source_id", ""),
            segments=segments,
            import_candidates=candidates,
            review_state=data.get("review_state", "pendiente"),
            import_mode=data.get("import_mode", "canon"),
            created_at=data.get("created_at") or now,
            updated_at=data.get("updated_at") or now,
            metadata=_parse_metadata(data.get("metadata")),
            graph=graph,
        )
