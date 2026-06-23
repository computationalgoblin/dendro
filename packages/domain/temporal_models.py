"""Temporal domain models — Bloque 18.
stdlib-only, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import uuid


class TemporalPrecision(str, Enum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"
    CONTRADICTORY = "contradictory"
    MYTHICAL = "mythical"


class TemporalRelation(str, Enum):
    BEFORE = "antes_de"
    AFTER = "despues_de"
    DURING = "durante"
    SIMULTANEOUS = "simultaneo_a"


class TemporalNature(str, Enum):
    """BETA1-J07: cómo se relaciona un ser con el tiempo.

    Gobierna la datación coherente: un ETERNO/ATEMPORAL no recibe un nacimiento
    mortal; un INMORTAL no muere.
    """

    MORTAL = "mortal"           # nace y muere (default)
    INMORTAL = "inmortal"       # nace en un momento, no muere
    ETERNO = "eterno"           # ni nace ni muere; origen primordial, sin año
    ATEMPORAL = "atemporal"     # concepto/ley fuera del tiempo
    CICLICO = "ciclico"         # muere y renace


@dataclass
class EventTemporality:
    # BETA1-J01: año entero diegético — eje canónico ordenable del punto temporal.
    year: int | None = None
    absolute_date: str | None = None
    world_date: str | None = None
    relative_date: str | None = None
    period: str | None = None
    era: str | None = None
    partial_order: list[str] = field(default_factory=list)
    temporal_relation: TemporalRelation | None = None
    precision: TemporalPrecision = TemporalPrecision.UNKNOWN
    is_duration: bool = False
    duration_value: int | None = None
    duration_unit: str | None = None
    anchor_event_id: str | None = None
    contradictory_sources: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "absolute_date": self.absolute_date,
            "world_date": self.world_date,
            "relative_date": self.relative_date,
            "period": self.period,
            "era": self.era,
            "partial_order": list(self.partial_order),
            "temporal_relation": self.temporal_relation.value if self.temporal_relation else None,
            "precision": self.precision.value,
            "is_duration": self.is_duration,
            "duration_value": self.duration_value,
            "duration_unit": self.duration_unit,
            "anchor_event_id": self.anchor_event_id,
            "contradictory_sources": list(self.contradictory_sources),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventTemporality:
        return cls(
            year=_py(data.get("year")),
            absolute_date=data.get("absolute_date"),
            world_date=data.get("world_date"),
            relative_date=data.get("relative_date"),
            period=data.get("period"),
            era=data.get("era"),
            partial_order=_pl(data.get("partial_order")),
            temporal_relation=_pe(TemporalRelation, data.get("temporal_relation"), None) if data.get("temporal_relation") else None,
            precision=_pe(TemporalPrecision, data.get("precision"), TemporalPrecision.UNKNOWN),
            is_duration=bool(data.get("is_duration", False)),
            duration_value=data.get("duration_value"),
            duration_unit=data.get("duration_unit"),
            anchor_event_id=data.get("anchor_event_id"),
            contradictory_sources=_pl(data.get("contradictory_sources")),
            notes=data.get("notes", ""),
        )


@dataclass
class TimelineEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    entity_id: str | None = None
    temporality: EventTemporality = field(default_factory=EventTemporality)
    domain_ids: list[str] = field(default_factory=list)
    layer_ids: list[str] = field(default_factory=list)
    participant_ids: list[str] = field(default_factory=list)
    location_id: str | None = None
    cause_ids: list[str] = field(default_factory=list)
    consequence_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    canon_state: str = "borrador"
    visibility_state: str = "visible_usuario"
    session_ids: list[str] = field(default_factory=list)
    faction_ids: list[str] = field(default_factory=list)
    secret_ids: list[str] = field(default_factory=list)
    clue_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "entity_id": self.entity_id,
            "temporality": self.temporality.to_dict(),
            "domain_ids": list(self.domain_ids), "layer_ids": list(self.layer_ids),
            "participant_ids": list(self.participant_ids),
            "location_id": self.location_id,
            "cause_ids": list(self.cause_ids), "consequence_ids": list(self.consequence_ids),
            "source_ids": list(self.source_ids),
            "canon_state": self.canon_state, "visibility_state": self.visibility_state,
            "session_ids": list(self.session_ids), "faction_ids": list(self.faction_ids),
            "secret_ids": list(self.secret_ids), "clue_ids": list(self.clue_ids),
            "metadata": dict(self.metadata),
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TimelineEvent:
        return cls(
            id=data.get("id", str(uuid.uuid4())), name=data.get("name", ""),
            description=data.get("description", ""), entity_id=data.get("entity_id"),
            temporality=EventTemporality.from_dict(data.get("temporality", {})),
            domain_ids=_pl(data.get("domain_ids")), layer_ids=_pl(data.get("layer_ids")),
            participant_ids=_pl(data.get("participant_ids")),
            location_id=data.get("location_id"),
            cause_ids=_pl(data.get("cause_ids")), consequence_ids=_pl(data.get("consequence_ids")),
            source_ids=_pl(data.get("source_ids")),
            canon_state=data.get("canon_state", "borrador"),
            visibility_state=data.get("visibility_state", "visible_usuario"),
            session_ids=_pl(data.get("session_ids")), faction_ids=_pl(data.get("faction_ids")),
            secret_ids=_pl(data.get("secret_ids")), clue_ids=_pl(data.get("clue_ids")),
            metadata=_pd(data.get("metadata")),
            created_at=data.get("created_at", ""), updated_at=data.get("updated_at", ""),
        )


def _pe(ec, v, d):
    if isinstance(v, ec): return v
    if isinstance(v, str):
        try: return ec(v)
        except ValueError: pass
    return d

def _pl(v): return list(v) if isinstance(v, list) else []
def _pd(v): return dict(v) if isinstance(v, dict) else {}


def _py(v):
    """Parse año entero (negativos permitidos) o None — BETA1-J01."""
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


__all__ = ["TemporalPrecision", "TemporalRelation", "EventTemporality", "TimelineEvent"]
