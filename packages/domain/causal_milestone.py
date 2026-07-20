"""Causal milestone domain model — Bloque 41.

Hitos are diegetic historical/causal events that explain how a world reached
its status quo. They are not NarrativeEntity, NarrativeRelation or HistoryEntry.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from packages.domain.temporal_models import EventTemporality
from packages.domain.temporal_span import TemporalSpan


class CausalMilestoneType(str, Enum):
    ORIGEN = "origen"
    FUNDACION = "fundacion"
    RUPTURA = "ruptura"
    GUERRA = "guerra"
    PACTO = "pacto"
    TRAICION = "traicion"
    DESCUBRIMIENTO = "descubrimiento"
    CATASTROFE = "catastrofe"
    MIGRACION = "migracion"
    REFORMA = "reforma"
    ASCENSO = "ascenso"
    CAIDA = "caida"
    REVELACION = "revelacion"
    CONSECUENCIA = "consecuencia"
    OTRO = "otro"


class CausalMilestoneStatus(str, Enum):
    CANDIDATE = "candidate"
    CANON = "canon"
    HYPOTHESIS = "hypothesis"
    REJECTED = "rejected"
    ARCHIVED = "archived"


@dataclass
class CausalMilestone:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    milestone_type: CausalMilestoneType = CausalMilestoneType.ORIGEN
    status: CausalMilestoneStatus = CausalMilestoneStatus.CANDIDATE
    temporality: EventTemporality = field(default_factory=EventTemporality)
    layer_ids: list[str] = field(default_factory=list)
    affected_entity_ids: list[str] = field(default_factory=list)
    affected_branch_ids: list[str] = field(default_factory=list)
    affected_layer_ids: list[str] = field(default_factory=list)
    caused_relation_ids: list[str] = field(default_factory=list)
    causal_parent_hito_ids: list[str] = field(default_factory=list)
    causal_child_hito_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    candidate_id: str | None = None
    confidence: float | None = None
    rationale: str = ""
    tags: list[str] = field(default_factory=list)
    visibility_state: str = "visible_usuario"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    # BETA1-G02: año diegético del hito (None solo transitorio pre-migración)
    year: int | None = None
    # BETA2-SUB-01: contención TEMPORAL de 1 nivel — el id del hito-marco que
    # contiene a este subhito (p. ej. una guerra que contiene batallas). Es
    # distinto de causal_parent/child_hito_ids (causa→consecuencia): aquí es
    # pertenencia al intervalo del marco. None = hito de primer nivel.
    parent_milestone_id: str | None = None

    @property
    def is_subhito(self) -> bool:
        """BETA2-SUB-01: True si este hito está contenido en un hito-marco."""
        return bool(self.parent_milestone_id)

    def as_temporal_span(self) -> TemporalSpan:
        """BETA1-J01: vista de lapso unificada sobre ``temporality`` + ``year``.

        El hito ya persiste un ``EventTemporality`` rico y su ``year`` entero;
        no se añade campo nuevo (se respeta el contrato de 22 campos). El
        ``year`` sigue siendo el espejo entero autoritativo del inicio.
        """
        start = EventTemporality.from_dict(self.temporality.to_dict())
        if start.year is None and self.year is not None:
            start.year = self.year
        end: EventTemporality | None = None
        # Proceso con duración en años (p.ej. guerra) → fin derivado.
        if (
            start.is_duration
            and start.year is not None
            and isinstance(start.duration_value, int)
            and (start.duration_unit or "").lower() in ("year", "years", "año", "años", "")
        ):
            end = EventTemporality(year=start.year + start.duration_value)
        return TemporalSpan(start=start, end=end, ongoing=end is None)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the B41-T01 contract (+ ``year`` y ``parent_milestone_id``)."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "milestone_type": self.milestone_type.value,
            "status": self.status.value,
            "temporality": self.temporality.to_dict(),
            "layer_ids": list(self.layer_ids),
            "affected_entity_ids": list(self.affected_entity_ids),
            "affected_branch_ids": list(self.affected_branch_ids),
            "affected_layer_ids": list(self.affected_layer_ids),
            "caused_relation_ids": list(self.caused_relation_ids),
            "causal_parent_hito_ids": list(self.causal_parent_hito_ids),
            "causal_child_hito_ids": list(self.causal_child_hito_ids),
            "source_ids": list(self.source_ids),
            "candidate_id": self.candidate_id,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "tags": list(self.tags),
            "visibility_state": self.visibility_state,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "year": self.year,
            "parent_milestone_id": self.parent_milestone_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CausalMilestone:
        raw_id = data.get("id")
        return cls(
            id=raw_id if isinstance(raw_id, str) and raw_id.strip() else str(uuid.uuid4()),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            milestone_type=_parse_enum(
                CausalMilestoneType,
                data.get("milestone_type"),
                CausalMilestoneType.ORIGEN,
            ),
            status=_parse_enum(
                CausalMilestoneStatus,
                data.get("status"),
                CausalMilestoneStatus.CANDIDATE,
            ),
            temporality=EventTemporality.from_dict(_parse_dict(data.get("temporality"))),
            layer_ids=_parse_str_list(data.get("layer_ids")),
            affected_entity_ids=_parse_str_list(data.get("affected_entity_ids")),
            affected_branch_ids=_parse_str_list(data.get("affected_branch_ids")),
            affected_layer_ids=_parse_str_list(data.get("affected_layer_ids")),
            caused_relation_ids=_parse_str_list(data.get("caused_relation_ids")),
            causal_parent_hito_ids=_parse_str_list(data.get("causal_parent_hito_ids")),
            causal_child_hito_ids=_parse_str_list(data.get("causal_child_hito_ids")),
            source_ids=_parse_str_list(data.get("source_ids")),
            candidate_id=data.get("candidate_id") if isinstance(data.get("candidate_id"), str) else None,
            confidence=_parse_optional_float(data.get("confidence")),
            rationale=str(data.get("rationale", "")),
            tags=_parse_str_list(data.get("tags")),
            visibility_state=str(data.get("visibility_state", "visible_usuario")),
            metadata=_parse_dict(data.get("metadata")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            year=_parse_optional_year(data.get("year")),
            parent_milestone_id=_parse_optional_str(data.get("parent_milestone_id")),
        )


def _parse_enum(enum_cls, value, default):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    return default


def _parse_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _parse_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _parse_optional_str(value: Any) -> str | None:
    """BETA2-SUB-01: id de hito-marco (str no vacío) o None."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def _parse_optional_year(value: Any) -> int | None:
    """BETA1-G02: año entero (negativos permitidos) o None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


__all__ = [
    "CausalMilestone",
    "CausalMilestoneStatus",
    "CausalMilestoneType",
]
