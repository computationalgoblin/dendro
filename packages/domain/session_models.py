"""Session and SessionScene domain models — B23-T01. Session is a PREPARATION container, not a live execution engine."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

def _now(): return datetime.now(timezone.utc).isoformat()
def _parse_enum(ec, v, d):
    if isinstance(v, ec): return v
    if isinstance(v, str):
        try: return ec(v)
        except ValueError: pass
    return d
def _parse_list(v): return list(v) if isinstance(v, list) else []
def _parse_str(v, d=""): return v if isinstance(v, str) else d
def _parse_int(v, d=0):
    if isinstance(v, int) and not isinstance(v, bool): return v
    if isinstance(v, (str, float)):
        try: return int(v)
        except (ValueError, TypeError): pass
    return d
def _parse_dict(v): return v if isinstance(v, dict) else {}

class SessionState(str, Enum):
    preparacion = "preparacion"
    activa = "activa"
    completada = "completada"
    archivada = "archivada"

class SceneType(str, Enum):
    prevista = "prevista"
    opcional = "opcional"
    improvisada = "improvisada"

@dataclass
class SessionScene:
    name: str
    id: str = ""
    description: str = ""
    scene_type: SceneType = SceneType.prevista
    order: int = 0
    location_id: str | None = None
    npc_ids: list[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self):
        if not self.id: self.id = f"scn_{uuid4().hex[:6]}"

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description,
                "scene_type": self.scene_type.value, "order": self.order,
                "location_id": self.location_id, "npc_ids": self.npc_ids, "notes": self.notes}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict): return cls(name="")
        return cls(name=_parse_str(data.get("name"), ""), id=_parse_str(data.get("id"), ""),
                   description=_parse_str(data.get("description")),
                   scene_type=_parse_enum(SceneType, data.get("scene_type"), SceneType.prevista),
                   order=_parse_int(data.get("order")),
                   location_id=data.get("location_id") if isinstance(data.get("location_id"), str) and data.get("location_id") else None,
                   npc_ids=_parse_list(data.get("npc_ids")), notes=_parse_str(data.get("notes")))

@dataclass
class Session:
    """Session — preparation container. 34 campos. NOT a live execution engine."""
    name: str
    campaign_id: str
    id: str = ""
    entity_id: str | None = None
    session_number: int = 0
    real_date: str = ""
    internal_date: str = ""
    context_summary: str = ""
    gm_objectives: list[str] = field(default_factory=list)
    player_known_objectives: list[str] = field(default_factory=list)
    planned_scenes: list[SessionScene] = field(default_factory=list)
    optional_scenes: list[SessionScene] = field(default_factory=list)
    planned_location_ids: list[str] = field(default_factory=list)
    planned_npc_ids: list[str] = field(default_factory=list)
    relevant_faction_ids: list[str] = field(default_factory=list)
    active_conflict_ids: list[str] = field(default_factory=list)
    available_clue_ids: list[str] = field(default_factory=list)
    revealable_secret_ids: list[str] = field(default_factory=list)
    clock_ids: list[str] = field(default_factory=list)
    rumors: list[str] = field(default_factory=list)
    encounters: list[str] = field(default_factory=list)
    rewards: list[str] = field(default_factory=list)
    complications: list[str] = field(default_factory=list)
    expected_consequences: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    improvised_material: list[str] = field(default_factory=list)
    private_notes: list[str] = field(default_factory=list)
    player_safe_summary: str = ""
    continuity_checklist: list[str] = field(default_factory=list)
    ia_suggestion_candidate_ids: list[str] = field(default_factory=list)
    state: SessionState = SessionState.preparacion
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.id: self.id = f"ses_{uuid4().hex[:6]}"
        now = _now()
        if not self.created_at: self.created_at = now
        if not self.updated_at: self.updated_at = now

    def to_dict(self):
        return {"id": self.id, "entity_id": self.entity_id, "campaign_id": self.campaign_id,
                "session_number": self.session_number, "name": self.name,
                "real_date": self.real_date, "internal_date": self.internal_date,
                "context_summary": self.context_summary, "gm_objectives": self.gm_objectives,
                "player_known_objectives": self.player_known_objectives,
                "planned_scenes": [s.to_dict() for s in self.planned_scenes],
                "optional_scenes": [s.to_dict() for s in self.optional_scenes],
                "planned_location_ids": self.planned_location_ids,
                "planned_npc_ids": self.planned_npc_ids,
                "relevant_faction_ids": self.relevant_faction_ids,
                "active_conflict_ids": self.active_conflict_ids,
                "available_clue_ids": self.available_clue_ids,
                "revealable_secret_ids": self.revealable_secret_ids,
                "clock_ids": self.clock_ids, "rumors": self.rumors,
                "encounters": self.encounters, "rewards": self.rewards,
                "complications": self.complications, "expected_consequences": self.expected_consequences,
                "open_questions": self.open_questions, "improvised_material": self.improvised_material,
                "private_notes": self.private_notes, "player_safe_summary": self.player_safe_summary,
                "continuity_checklist": self.continuity_checklist,
                "ia_suggestion_candidate_ids": self.ia_suggestion_candidate_ids,
                "state": self.state.value, "metadata": self.metadata,
                "created_at": self.created_at, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict): return cls(name="", campaign_id="")
        ps = [SessionScene.from_dict(s) for s in _parse_list(data.get("planned_scenes")) if isinstance(s, dict)]
        os_ = [SessionScene.from_dict(s) for s in _parse_list(data.get("optional_scenes")) if isinstance(s, dict)]
        return cls(name=_parse_str(data.get("name"), ""), campaign_id=_parse_str(data.get("campaign_id"), ""),
                   id=_parse_str(data.get("id")), entity_id=data.get("entity_id") if isinstance(data.get("entity_id"), str) and data.get("entity_id") else None,
                   session_number=_parse_int(data.get("session_number")),
                   real_date=_parse_str(data.get("real_date")), internal_date=_parse_str(data.get("internal_date")),
                   context_summary=_parse_str(data.get("context_summary")),
                   gm_objectives=_parse_list(data.get("gm_objectives")),
                   player_known_objectives=_parse_list(data.get("player_known_objectives")),
                   planned_scenes=ps, optional_scenes=os_,
                   planned_location_ids=_parse_list(data.get("planned_location_ids")),
                   planned_npc_ids=_parse_list(data.get("planned_npc_ids")),
                   relevant_faction_ids=_parse_list(data.get("relevant_faction_ids")),
                   active_conflict_ids=_parse_list(data.get("active_conflict_ids")),
                   available_clue_ids=_parse_list(data.get("available_clue_ids")),
                   revealable_secret_ids=_parse_list(data.get("revealable_secret_ids")),
                   clock_ids=_parse_list(data.get("clock_ids")),
                   rumors=_parse_list(data.get("rumors")), encounters=_parse_list(data.get("encounters")),
                   rewards=_parse_list(data.get("rewards")), complications=_parse_list(data.get("complications")),
                   expected_consequences=_parse_list(data.get("expected_consequences")),
                   open_questions=_parse_list(data.get("open_questions")),
                   improvised_material=_parse_list(data.get("improvised_material")),
                   private_notes=_parse_list(data.get("private_notes")),
                   player_safe_summary=_parse_str(data.get("player_safe_summary")),
                   continuity_checklist=_parse_list(data.get("continuity_checklist")),
                   ia_suggestion_candidate_ids=_parse_list(data.get("ia_suggestion_candidate_ids")),
                   state=_parse_enum(SessionState, data.get("state"), SessionState.preparacion),
                   metadata=_parse_dict(data.get("metadata")),
                   created_at=_parse_str(data.get("created_at")), updated_at=_parse_str(data.get("updated_at")))
