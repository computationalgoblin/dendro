"""Candidate and Issue — domain models.

Provides ``Issue`` (detected problem: contradiction, inconsistency,
error, warning) and ``Candidate`` (proposed content from IA or import,
pending acceptance).  Bloque 5 — complementary to Source and HistoryEntry.
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


class IssueType(str, Enum):
    CONTRADICCION = "contradiccion"
    INCONSISTENCIA = "inconsistencia"
    ERROR = "error"
    ADVERTENCIA = "advertencia"


class IssueSeverity(str, Enum):
    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class IssueState(str, Enum):
    ABIERTA = "abierta"
    EN_PROGRESO = "en_progreso"
    RESUELTA = "resuelta"
    DESCARTADA = "descartada"


class CandidateType(str, Enum):
    ENTIDAD = "entidad"
    RELACION = "relacion"
    ANILLO = "anillo"
    FUENTE = "fuente"
    CAMBIO = "cambio"
    FUSION = "fusion"
    CORRECCION = "correccion"
    INCIDENCIA = "incidencia"
    FRAGMENTO_IMPORTADO = "fragmento_importado"
    SUGERENCIA_IA = "sugerencia_ia"
    PROPUESTA_POST_SESION = "propuesta_post_sesion"


class CandidateState(str, Enum):
    PENDIENTE = "pendiente"
    ACEPTADO = "aceptado"
    RECHAZADO = "rechazado"
    EDITADO_ACEPTADO = "editado_aceptado"
    FUSIONADO = "fusionado"
    POSPUESTO = "pospuesto"
    ARCHIVADO = "archivado"
    REQUIERE_REVISION = "requiere_revision"
    PARCIALMENTE_ACEPTADO = "parcialmente_aceptado"


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            pass
    return _now()


def _parse_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


_EnumType = type[Enum]


def _parse_enum(enum_cls: _EnumType, value: Any, default: Any) -> Any:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    return default


# ═══════════════════════════════════════════════════════════════════════
# Issue
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class Issue:
    """Detected problem in the narrative corpus.

    13 fields.  Created by consistency checks, manual review,
    or automated detection.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issue_type: IssueType = IssueType.ADVERTENCIA
    severity: IssueSeverity = IssueSeverity.MEDIA
    state: IssueState = IssueState.ABIERTA
    title: str = ""
    description: str = ""
    affected_entity_id: str | None = None
    affected_relation_id: str | None = None
    affected_source_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    resolved_at: datetime | None = None
    resolution: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "state": self.state.value,
            "title": self.title,
            "description": self.description,
            "affected_entity_id": self.affected_entity_id,
            "affected_relation_id": self.affected_relation_id,
            "affected_source_id": self.affected_source_id,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution": self.resolution,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Issue:
        raw_resolved = data.get("resolved_at")
        resolved = _parse_datetime(raw_resolved) if raw_resolved else None
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            issue_type=_parse_enum(
                IssueType, data.get("issue_type"), IssueType.ADVERTENCIA,
            ),
            severity=_parse_enum(
                IssueSeverity, data.get("severity"), IssueSeverity.MEDIA,
            ),
            state=_parse_enum(
                IssueState, data.get("state"), IssueState.ABIERTA,
            ),
            title=data.get("title", ""),
            description=data.get("description", ""),
            affected_entity_id=data.get("affected_entity_id"),
            affected_relation_id=data.get("affected_relation_id"),
            affected_source_id=data.get("affected_source_id"),
            created_at=_parse_datetime(data.get("created_at")),
            resolved_at=resolved,
            resolution=data.get("resolution", ""),
            metadata=_parse_dict(data.get("metadata")),
        )


# ═══════════════════════════════════════════════════════════════════════
# Candidate
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class Candidate:
    """Proposed content pending acceptance.

    11 fields.  Created by IA suggestions, import pipelines,
    or user proposals.  ``proposed_data`` is a free-form dict.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    candidate_type: CandidateType = CandidateType.ENTIDAD
    state: CandidateState = CandidateState.PENDIENTE
    title: str = ""
    proposed_data: dict[str, Any] = field(default_factory=dict)
    affected_entity_ids: list[str] = field(default_factory=list)
    affected_relation_ids: list[str] = field(default_factory=list)
    source: str = ""
    source_id: str | None = None
    confidence: float = 0.5
    justification: str = ""
    expected_impact: str = ""
    possible_contradictions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)
    reviewed_at: datetime | None = None
    resolution_note: str = ""
    final_action: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "candidate_type": self.candidate_type.value,
            "state": self.state.value,
            "title": self.title,
            "proposed_data": dict(self.proposed_data),
            "affected_entity_ids": list(self.affected_entity_ids),
            "affected_relation_ids": list(self.affected_relation_ids),
            "source": self.source,
            "source_id": self.source_id,
            "confidence": self.confidence,
            "justification": self.justification,
            "expected_impact": self.expected_impact,
            "possible_contradictions": list(self.possible_contradictions),
            "created_at": self.created_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "resolution_note": self.resolution_note,
            "final_action": self.final_action,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Candidate:
        raw_reviewed = data.get("reviewed_at")
        reviewed = _parse_datetime(raw_reviewed) if raw_reviewed else None
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            candidate_type=_parse_enum(
                CandidateType, data.get("candidate_type"), CandidateType.ENTIDAD,
            ),
            state=_parse_enum(
                CandidateState, data.get("state"), CandidateState.PENDIENTE,
            ),
            title=data.get("title", ""),
            proposed_data=_parse_dict(data.get("proposed_data")),
            affected_entity_ids=_parse_list(data.get("affected_entity_ids")),
            affected_relation_ids=_parse_list(data.get("affected_relation_ids")),
            source=data.get("source", ""),
            source_id=data.get("source_id"),
            confidence=float(data.get("confidence", 0.5)),
            justification=data.get("justification", ""),
            expected_impact=data.get("expected_impact", ""),
            possible_contradictions=_parse_list(data.get("possible_contradictions")),
            created_at=_parse_datetime(data.get("created_at")),
            reviewed_at=reviewed,
            resolution_note=data.get("resolution_note", ""),
            final_action=data.get("final_action", ""),
            metadata=_parse_dict(data.get("metadata")),
        )


# ═══════════════════════════════════════════════════════════════════════
# StructuredIssue — Bloque 12 (15 fields, 8 states, 15 issue types)
# ═══════════════════════════════════════════════════════════════════════


class StructuredIssueType(str, Enum):
    """§12.2 / §12.3 — 15 issue types for deterministic validators."""
    BROKEN_RELATION = "broken_relation"
    DUPLICATE_ENTITY = "duplicate_entity"
    INVALID_ENTITY_TYPE = "invalid_entity_type"
    INVALID_RELATION_TYPE = "invalid_relation_type"
    CIRCULAR_RELATION = "circular_relation"
    ORPHAN_ENTITY = "orphan_entity"
    NO_DESCRIPTION = "no_description"
    CANON_LOW_CERTAINTY = "canon_low_certainty"
    EXPORTABLE_PRIVATE = "exportable_private"
    SECRET_VISIBILITY = "secret_visibility"
    CLUE_WITHOUT_SECRET = "clue_without_secret"
    SECRET_WITHOUT_CLUE = "secret_without_clue"
    EVENT_NO_TEMPORALITY = "event_no_temporality"
    PENDING_IMPORT = "pending_import"
    CONTRADICTORY_RELATION = "contradictory_relation"


class StructuredIssueSeverity(str, Enum):
    """§12.2 — 4 severity levels."""
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class StructuredIssueState(str, Enum):
    """§12.2 — 8 states for issue lifecycle."""
    ABIERTA = "abierta"
    REVISADA = "revisada"
    ACEPTADA = "aceptada"
    DESCARTADA = "descartada"
    RESUELTA = "resuelta"
    INTENCIONAL = "intencional"
    PENDIENTE_INFO = "pendiente_info"
    POSPUESTA = "pospuesta"


# ── Transition matrix ───────────────────────────────────────────────


_TRANSITIONS: dict[StructuredIssueState, set[StructuredIssueState]] = {
    StructuredIssueState.ABIERTA: {
        StructuredIssueState.REVISADA,
        StructuredIssueState.DESCARTADA,
        StructuredIssueState.INTENCIONAL,
    },
    StructuredIssueState.REVISADA: {
        StructuredIssueState.ACEPTADA,
        StructuredIssueState.DESCARTADA,
        StructuredIssueState.PENDIENTE_INFO,
        StructuredIssueState.POSPUESTA,
    },
    StructuredIssueState.ACEPTADA: {
        StructuredIssueState.RESUELTA,
        StructuredIssueState.POSPUESTA,
    },
    StructuredIssueState.PENDIENTE_INFO: {
        StructuredIssueState.REVISADA,
        StructuredIssueState.DESCARTADA,
    },
    StructuredIssueState.POSPUESTA: {
        StructuredIssueState.ABIERTA,
        StructuredIssueState.REVISADA,
    },
    StructuredIssueState.DESCARTADA: {
        StructuredIssueState.ABIERTA,
    },
    StructuredIssueState.INTENCIONAL: {
        StructuredIssueState.ABIERTA,
    },
    StructuredIssueState.RESUELTA: set(),
}


def is_valid_transition(
    from_state: StructuredIssueState,
    to_state: StructuredIssueState,
) -> bool:
    """Check if *to_state* is reachable from *from_state*."""
    allowed = _TRANSITIONS.get(from_state, set())
    return to_state in allowed


# ── Dataclass ────────────────────────────────────────────────────────


def _parse_list(value: Any) -> list:
    if isinstance(value, list):
        return list(value)
    return []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StructuredIssue:
    """§12.2 — Full structured incidence with 15 fields and 8 states."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: StructuredIssueType = StructuredIssueType.BROKEN_RELATION
    severity: StructuredIssueSeverity = StructuredIssueSeverity.MEDIA
    state: StructuredIssueState = StructuredIssueState.ABIERTA
    affected_entity_ids: list[str] = field(default_factory=list)
    affected_relation_ids: list[str] = field(default_factory=list)
    affected_source_ids: list[str] = field(default_factory=list)
    description: str = ""
    evidence: str = ""
    possible_solutions: list[str] = field(default_factory=list)
    detected_at: str = field(default_factory=_now_iso)
    reviewed_at: str | None = None
    resolution: str = ""
    is_intentional: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "state": self.state.value,
            "affected_entity_ids": list(self.affected_entity_ids),
            "affected_relation_ids": list(self.affected_relation_ids),
            "affected_source_ids": list(self.affected_source_ids),
            "description": self.description,
            "evidence": self.evidence,
            "possible_solutions": list(self.possible_solutions),
            "detected_at": self.detected_at,
            "reviewed_at": self.reviewed_at,
            "resolution": self.resolution,
            "is_intentional": self.is_intentional,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuredIssue:
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            type=_parse_enum(
                StructuredIssueType, data.get("type"),
                StructuredIssueType.BROKEN_RELATION,
            ),
            severity=_parse_enum(
                StructuredIssueSeverity, data.get("severity"),
                StructuredIssueSeverity.MEDIA,
            ),
            state=_parse_enum(
                StructuredIssueState, data.get("state"),
                StructuredIssueState.ABIERTA,
            ),
            affected_entity_ids=_parse_list(data.get("affected_entity_ids")),
            affected_relation_ids=_parse_list(data.get("affected_relation_ids")),
            affected_source_ids=_parse_list(data.get("affected_source_ids")),
            description=data.get("description", ""),
            evidence=data.get("evidence", ""),
            possible_solutions=_parse_list(data.get("possible_solutions")),
            detected_at=data.get("detected_at", "") or _now_iso(),
            reviewed_at=data.get("reviewed_at"),
            resolution=data.get("resolution", ""),
            is_intentional=data.get("is_intentional", False),
            metadata=_parse_dict(data.get("metadata")),
        )


__all__ = [
    "Issue",
    "IssueType",
    "IssueSeverity",
    "IssueState",
    "StructuredIssue",
    "StructuredIssueType",
    "StructuredIssueSeverity",
    "StructuredIssueState",
    "is_valid_transition",
    "Candidate",
    "CandidateType",
    "CandidateState",
]
