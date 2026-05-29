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
    FUENTE = "fuente"


class CandidateState(str, Enum):
    PENDIENTE = "pendiente"
    ACEPTADO = "aceptado"
    RECHAZADO = "rechazado"


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
    source: str = ""
    source_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    resolved_at: datetime | None = None
    resolution_note: str = ""
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
            "source": self.source,
            "source_id": self.source_id,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_note": self.resolution_note,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Candidate:
        raw_resolved = data.get("resolved_at")
        resolved = _parse_datetime(raw_resolved) if raw_resolved else None
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
            source=data.get("source", ""),
            source_id=data.get("source_id"),
            created_at=_parse_datetime(data.get("created_at")),
            resolved_at=resolved,
            resolution_note=data.get("resolution_note", ""),
            metadata=_parse_dict(data.get("metadata")),
        )


__all__ = [
    "Issue",
    "IssueType",
    "IssueSeverity",
    "IssueState",
    "Candidate",
    "CandidateType",
    "CandidateState",
]
