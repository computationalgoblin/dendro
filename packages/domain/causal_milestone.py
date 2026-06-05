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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the 22-field B41-T01 contract."""
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
