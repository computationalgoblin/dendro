"""Secret and Clue domain models — B21-T01.

Secreto (21 fields) and Pista (20 fields) implement the knowledge
layer (§21.2, §21.3).

Design rules:
  1. Secreto/Pista do NOT replace NarrativeEntity(SECRETO/PISTA).
     entity_id provides optional linking to the core entity.
  2. who_knows_entity_ids, who_suspects_entity_ids, who_ignores_entity_ids,
     who_hides_entity_ids are MANUAL auxiliary lists — NOT automatic cache.
     The source of truth for knowledge is RelationService.
  3. importance, clarity, redundancy, loss_risk are clamped to 1-5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Enums ──────────────────────────────────────────────────────────────


class RevelationState(str, Enum):
    oculto = "oculto"
    parcialmente_revelado = "parcialmente_revelado"
    revelado = "revelado"
    rumoreado = "rumoreado"
    malinterpretado = "malinterpretado"


class DeliveryState(str, Enum):
    pendiente = "pendiente"
    entregada = "entregada"
    perdida = "perdida"
    ignorada = "ignorada"
    malinterpretada = "malinterpretada"


class ClueForm(str, Enum):
    documento = "documento"
    testimonio = "testimonio"
    objeto = "objeto"
    rastro = "rastro"
    rumor = "rumor"
    vision = "vision"
    sueño = "sueño"
    descubrimiento = "descubrimiento"


# ── Helpers ────────────────────────────────────────────────────────────


def _parse_enum(enum_cls, value, default):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    return default


def _parse_list(value):
    return list(value) if isinstance(value, list) else []


def _parse_str(value, default=""):
    return value if isinstance(value, str) else default


def _parse_int(value, default=0):
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, (str, float)):
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
    return default


def _parse_dict(value):
    return value if isinstance(value, dict) else {}


def _clamp_range(value, min_val=1, max_val=5, default=3):
    """Clamp a value to [min, max], returning default for None/non-numeric."""
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            value = round(value)
        val = int(value)
        if val < min_val:
            return min_val
        if val > max_val:
            return max_val
        return val
    if isinstance(value, str):
        try:
            return _clamp_range(int(value), min_val, max_val, default)
        except (ValueError, TypeError):
            pass
    return default


# ── Secreto ────────────────────────────────────────────────────────────


@dataclass
class Secreto:
    """Secret — hidden information with revelation tracking.

    21 campos técnicos (§21.2), más entity_id opcional.
    Does NOT replace NarrativeEntity(SECRETO) — entity_id links optionally.
    """
    content: str
    id: str = ""
    entity_id: str | None = None
    affected_entity_ids: list[str] = field(default_factory=list)
    revelation_state: RevelationState = RevelationState.oculto
    who_knows_entity_ids: list[str] = field(default_factory=list)
    who_suspects_entity_ids: list[str] = field(default_factory=list)
    who_ignores_entity_ids: list[str] = field(default_factory=list)
    who_hides_entity_ids: list[str] = field(default_factory=list)
    associated_clue_ids: list[str] = field(default_factory=list)
    revelation_consequences: list[str] = field(default_factory=list)
    concealment_consequences: list[str] = field(default_factory=list)
    planned_revelation_session_ids: list[str] = field(default_factory=list)
    actual_revelation_session_id: str | None = None
    revelation_form: str = ""
    importance: int = 3
    canon_state: str = "borrador"
    visibility_state: str = "privado"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"sec_{uuid4().hex[:6]}"
        now = _now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        self.importance = _clamp_range(self.importance, 1, 5, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "entity_id": self.entity_id,
            "affected_entity_ids": self.affected_entity_ids,
            "revelation_state": self.revelation_state.value,
            "who_knows_entity_ids": self.who_knows_entity_ids,
            "who_suspects_entity_ids": self.who_suspects_entity_ids,
            "who_ignores_entity_ids": self.who_ignores_entity_ids,
            "who_hides_entity_ids": self.who_hides_entity_ids,
            "associated_clue_ids": self.associated_clue_ids,
            "revelation_consequences": self.revelation_consequences,
            "concealment_consequences": self.concealment_consequences,
            "planned_revelation_session_ids": self.planned_revelation_session_ids,
            "actual_revelation_session_id": self.actual_revelation_session_id,
            "revelation_form": self.revelation_form,
            "importance": self.importance,
            "canon_state": self.canon_state,
            "visibility_state": self.visibility_state,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Secreto:
        if not isinstance(data, dict):
            return cls(content="")
        entity_id = data.get("entity_id")
        return cls(
            content=_parse_str(data.get("content"), ""),
            id=_parse_str(data.get("id"), ""),
            entity_id=entity_id if isinstance(entity_id, str) and entity_id else None,
            affected_entity_ids=_parse_list(data.get("affected_entity_ids")),
            revelation_state=_parse_enum(RevelationState, data.get("revelation_state"), RevelationState.oculto),
            who_knows_entity_ids=_parse_list(data.get("who_knows_entity_ids")),
            who_suspects_entity_ids=_parse_list(data.get("who_suspects_entity_ids")),
            who_ignores_entity_ids=_parse_list(data.get("who_ignores_entity_ids")),
            who_hides_entity_ids=_parse_list(data.get("who_hides_entity_ids")),
            associated_clue_ids=_parse_list(data.get("associated_clue_ids")),
            revelation_consequences=_parse_list(data.get("revelation_consequences")),
            concealment_consequences=_parse_list(data.get("concealment_consequences")),
            planned_revelation_session_ids=_parse_list(data.get("planned_revelation_session_ids")),
            actual_revelation_session_id=data.get("actual_revelation_session_id"),
            revelation_form=_parse_str(data.get("revelation_form"), ""),
            importance=_clamp_range(data.get("importance"), 1, 5, 3),
            canon_state=_parse_str(data.get("canon_state"), "borrador"),
            visibility_state=_parse_str(data.get("visibility_state"), "privado"),
            metadata=_parse_dict(data.get("metadata")),
            created_at=_parse_str(data.get("created_at"), ""),
            updated_at=_parse_str(data.get("updated_at"), ""),
        )


# ── Pista ──────────────────────────────────────────────────────────────


@dataclass
class Pista:
    """Clue — fragment of information leading to a secret.

    20 campos técnicos (§21.3), más entity_id opcional.
    associated_secret_id is optional — a clue without a secret is valid
    (the consistency engine detects it as an issue).
    """
    content: str
    id: str = ""
    entity_id: str | None = None
    associated_secret_id: str | None = None
    source_entity_id: str | None = None
    location_entity_id: str | None = None
    associated_npc_entity_id: str | None = None
    delivery_form: ClueForm = ClueForm.documento
    delivery_state: DeliveryState = DeliveryState.pendiente
    clarity: int = 3
    redundancy: int = 1
    loss_risk: int = 3
    planned_session_ids: list[str] = field(default_factory=list)
    delivered_session_id: str | None = None
    character_ids_who_know: list[str] = field(default_factory=list)
    probable_interpretation: str = ""
    possible_misinterpretations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"clu_{uuid4().hex[:6]}"
        now = _now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        self.clarity = _clamp_range(self.clarity, 1, 5, 3)
        self.redundancy = _clamp_range(self.redundancy, 1, 5, 1)
        self.loss_risk = _clamp_range(self.loss_risk, 1, 5, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "entity_id": self.entity_id,
            "associated_secret_id": self.associated_secret_id,
            "source_entity_id": self.source_entity_id,
            "location_entity_id": self.location_entity_id,
            "associated_npc_entity_id": self.associated_npc_entity_id,
            "delivery_form": self.delivery_form.value,
            "delivery_state": self.delivery_state.value,
            "clarity": self.clarity,
            "redundancy": self.redundancy,
            "loss_risk": self.loss_risk,
            "planned_session_ids": self.planned_session_ids,
            "delivered_session_id": self.delivered_session_id,
            "character_ids_who_know": self.character_ids_who_know,
            "probable_interpretation": self.probable_interpretation,
            "possible_misinterpretations": self.possible_misinterpretations,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pista:
        if not isinstance(data, dict):
            return cls(content="")
        entity_id = data.get("entity_id")
        associated_secret_id = data.get("associated_secret_id")
        source_entity_id = data.get("source_entity_id")
        location_entity_id = data.get("location_entity_id")
        associated_npc_entity_id = data.get("associated_npc_entity_id")
        return cls(
            content=_parse_str(data.get("content"), ""),
            id=_parse_str(data.get("id"), ""),
            entity_id=entity_id if isinstance(entity_id, str) and entity_id else None,
            associated_secret_id=associated_secret_id if isinstance(associated_secret_id, str) and associated_secret_id else None,
            source_entity_id=source_entity_id if isinstance(source_entity_id, str) and source_entity_id else None,
            location_entity_id=location_entity_id if isinstance(location_entity_id, str) and location_entity_id else None,
            associated_npc_entity_id=associated_npc_entity_id if isinstance(associated_npc_entity_id, str) and associated_npc_entity_id else None,
            delivery_form=_parse_enum(ClueForm, data.get("delivery_form"), ClueForm.documento),
            delivery_state=_parse_enum(DeliveryState, data.get("delivery_state"), DeliveryState.pendiente),
            clarity=_clamp_range(data.get("clarity"), 1, 5, 3),
            redundancy=_clamp_range(data.get("redundancy"), 1, 5, 1),
            loss_risk=_clamp_range(data.get("loss_risk"), 1, 5, 3),
            planned_session_ids=_parse_list(data.get("planned_session_ids")),
            delivered_session_id=data.get("delivered_session_id"),
            character_ids_who_know=_parse_list(data.get("character_ids_who_know")),
            probable_interpretation=_parse_str(data.get("probable_interpretation"), ""),
            possible_misinterpretations=_parse_list(data.get("possible_misinterpretations")),
            metadata=_parse_dict(data.get("metadata")),
            created_at=_parse_str(data.get("created_at"), ""),
            updated_at=_parse_str(data.get("updated_at"), ""),
        )
