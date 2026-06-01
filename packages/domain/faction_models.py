"""Faction and Front domain models — B22-T01.

Faction (26 campos) extends NarrativeEntity(FACCION) — entity_id is MANDATORY.
Front (19 campos) is a dynamic process with stages.
CampaignClock is extended with optional faction/front fields (B20 compat).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Helpers ────────────────────────────────────────────────────────────

def _parse_enum(enum_cls, value, default):
    if isinstance(value, enum_cls): return value
    if isinstance(value, str):
        try: return enum_cls(value)
        except ValueError: pass
    return default

def _parse_list(value): return list(value) if isinstance(value, list) else []
def _parse_str(value, default=""): return value if isinstance(value, str) else default
def _parse_int(value, default=0):
    if isinstance(value, int) and not isinstance(value, bool): return value
    if isinstance(value, (str, float)):
        try: return int(value)
        except (ValueError, TypeError): pass
    return default
def _parse_dict(value): return value if isinstance(value, dict) else {}


# ── Enums ──────────────────────────────────────────────────────────────

class FactionState(str, Enum):
    activa = "activa"
    debilitada = "debilitada"
    destruida = "destruida"
    inactiva = "inactiva"

class FrontType(str, Enum):
    frente = "frente"
    amenaza = "amenaza"
    inminente = "inminente"

class FrontState(str, Enum):
    latente = "latente"
    activo = "activo"
    contenido = "contenido"
    resuelto = "resuelto"


# ── FrontStage ────────────────────────────────────────────────────────

@dataclass
class FrontStage:
    name: str
    threshold: int = 0
    description: str = ""
    consequences: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    is_terminal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "threshold": self.threshold, "description": self.description,
                "consequences": self.consequences, "conditions": self.conditions, "is_terminal": self.is_terminal}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FrontStage:
        if not isinstance(data, dict): return cls(name="")
        return cls(name=_parse_str(data.get("name"), ""), threshold=_parse_int(data.get("threshold"), 0),
                   description=_parse_str(data.get("description"), ""),
                   consequences=_parse_list(data.get("consequences")),
                   conditions=_parse_list(data.get("conditions")),
                   is_terminal=data.get("is_terminal", False) if isinstance(data.get("is_terminal"), bool) else False)


# ── Faction ───────────────────────────────────────────────────────────

@dataclass
class Faction:
    """Faction — extension of NarrativeEntity(FACCION). entity_id MANDATORY. 26 campos."""
    entity_id: str
    name: str = ""
    id: str = ""
    objectives: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    leader_entity_ids: list[str] = field(default_factory=list)
    member_entity_ids: list[str] = field(default_factory=list)
    ally_faction_ids: list[str] = field(default_factory=list)
    enemy_faction_ids: list[str] = field(default_factory=list)
    territory_entity_ids: list[str] = field(default_factory=list)
    plan_ids: list[str] = field(default_factory=list)
    secret_ids: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    ideology: str = ""
    state: FactionState = FactionState.activa
    clock_ids: list[str] = field(default_factory=list)
    possible_reactions: list[str] = field(default_factory=list)
    relation_with_pcs: str = ""
    relation_with_factions: str = ""
    event_ids: list[str] = field(default_factory=list)
    inaction_consequences: list[str] = field(default_factory=list)
    intervention_consequences: list[str] = field(default_factory=list)
    visibility_state: str = "privado"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.id: self.id = f"fac_{uuid4().hex[:6]}"
        now = _now()
        if not self.created_at: self.created_at = now
        if not self.updated_at: self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "entity_id": self.entity_id, "name": self.name,
                "objectives": self.objectives, "resources": self.resources,
                "leader_entity_ids": self.leader_entity_ids, "member_entity_ids": self.member_entity_ids,
                "ally_faction_ids": self.ally_faction_ids, "enemy_faction_ids": self.enemy_faction_ids,
                "territory_entity_ids": self.territory_entity_ids, "plan_ids": self.plan_ids,
                "secret_ids": self.secret_ids, "methods": self.methods, "ideology": self.ideology,
                "state": self.state.value, "clock_ids": self.clock_ids,
                "possible_reactions": self.possible_reactions,
                "relation_with_pcs": self.relation_with_pcs, "relation_with_factions": self.relation_with_factions,
                "event_ids": self.event_ids,
                "inaction_consequences": self.inaction_consequences, "intervention_consequences": self.intervention_consequences,
                "visibility_state": self.visibility_state, "metadata": self.metadata,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Faction:
        if not isinstance(data, dict): return cls(entity_id="")
        return cls(entity_id=_parse_str(data.get("entity_id"), ""), name=_parse_str(data.get("name"), ""),
                   id=_parse_str(data.get("id"), ""), objectives=_parse_list(data.get("objectives")),
                   resources=_parse_list(data.get("resources")), leader_entity_ids=_parse_list(data.get("leader_entity_ids")),
                   member_entity_ids=_parse_list(data.get("member_entity_ids")), ally_faction_ids=_parse_list(data.get("ally_faction_ids")),
                   enemy_faction_ids=_parse_list(data.get("enemy_faction_ids")), territory_entity_ids=_parse_list(data.get("territory_entity_ids")),
                   plan_ids=_parse_list(data.get("plan_ids")), secret_ids=_parse_list(data.get("secret_ids")),
                   methods=_parse_list(data.get("methods")), ideology=_parse_str(data.get("ideology"), ""),
                   state=_parse_enum(FactionState, data.get("state"), FactionState.activa),
                   clock_ids=_parse_list(data.get("clock_ids")), possible_reactions=_parse_list(data.get("possible_reactions")),
                   relation_with_pcs=_parse_str(data.get("relation_with_pcs"), ""),
                   relation_with_factions=_parse_str(data.get("relation_with_factions"), ""),
                   event_ids=_parse_list(data.get("event_ids")),
                   inaction_consequences=_parse_list(data.get("inaction_consequences")),
                   intervention_consequences=_parse_list(data.get("intervention_consequences")),
                   visibility_state=_parse_str(data.get("visibility_state"), "privado"),
                   metadata=_parse_dict(data.get("metadata")),
                   created_at=_parse_str(data.get("created_at"), ""), updated_at=_parse_str(data.get("updated_at"), ""))


# ── Front ─────────────────────────────────────────────────────────────

@dataclass
class Front:
    """Dynamic narrative process with stages. 19 campos."""
    name: str
    front_type: FrontType = FrontType.frente
    id: str = ""
    description: str = ""
    faction_id: str | None = None
    state: FrontState = FrontState.latente
    stages: list[FrontStage] = field(default_factory=list)
    current_stage_index: int = 0
    entity_id: str | None = None
    clock_id: str | None = None
    advance_conditions: list[str] = field(default_factory=list)
    retreat_conditions: list[str] = field(default_factory=list)
    session_ids: list[str] = field(default_factory=list)
    affected_entity_ids: list[str] = field(default_factory=list)
    visibility_state: str = "privado"
    history: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.id: self.id = f"frt_{uuid4().hex[:6]}"
        now = _now()
        if not self.created_at: self.created_at = now
        if not self.updated_at: self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "front_type": self.front_type.value,
                "description": self.description, "faction_id": self.faction_id, "state": self.state.value,
                "stages": [s.to_dict() for s in self.stages], "current_stage_index": self.current_stage_index,
                "entity_id": self.entity_id, "clock_id": self.clock_id,
                "advance_conditions": self.advance_conditions, "retreat_conditions": self.retreat_conditions,
                "session_ids": self.session_ids, "affected_entity_ids": self.affected_entity_ids,
                "visibility_state": self.visibility_state, "history": self.history, "metadata": self.metadata,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Front:
        if not isinstance(data, dict): return cls(name="")
        stages_raw = _parse_list(data.get("stages"))
        stages = [FrontStage.from_dict(s) for s in stages_raw if isinstance(s, dict)]
        return cls(name=_parse_str(data.get("name"), ""),
                   front_type=_parse_enum(FrontType, data.get("front_type"), FrontType.frente),
                   id=_parse_str(data.get("id"), ""), description=_parse_str(data.get("description"), ""),
                   faction_id=data.get("faction_id") if isinstance(data.get("faction_id"), str) and data.get("faction_id") else None,
                   state=_parse_enum(FrontState, data.get("state"), FrontState.latente),
                   stages=stages, current_stage_index=_parse_int(data.get("current_stage_index"), 0),
                   entity_id=data.get("entity_id") if isinstance(data.get("entity_id"), str) and data.get("entity_id") else None,
                   clock_id=data.get("clock_id") if isinstance(data.get("clock_id"), str) and data.get("clock_id") else None,
                   advance_conditions=_parse_list(data.get("advance_conditions")),
                   retreat_conditions=_parse_list(data.get("retreat_conditions")),
                   session_ids=_parse_list(data.get("session_ids")),
                   affected_entity_ids=_parse_list(data.get("affected_entity_ids")),
                   visibility_state=_parse_str(data.get("visibility_state"), "privado"),
                   history=_parse_list(data.get("history")), metadata=_parse_dict(data.get("metadata")),
                   created_at=_parse_str(data.get("created_at"), ""), updated_at=_parse_str(data.get("updated_at"), ""))
