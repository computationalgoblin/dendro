"""Writing unit domain models — B19-T01.

WritingUnit is the core model for the writing layer (§19.2, §19.3).
It does NOT substitute NarrativeEntity — it links to entities via entity_ids
without automatic content/canon/state synchronisation.
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


class WritingUnitType(str, Enum):
    HISTORIA = "historia"
    ARCO_NARRATIVO = "arco_narrativo"
    TRAMA = "trama"
    SUBTRAMA = "subtrama"
    CAPITULO = "capitulo"
    ESCENA = "escena"
    SECUENCIA = "secuencia"
    PUNTO_DE_GIRO = "punto_de_giro"
    REVELACION = "revelacion"
    CONFLICTO = "conflicto"
    TEMA = "tema"
    MOTIVO = "motivo"
    SIMBOLO = "simbolo"
    VOZ_NARRATIVA = "voz_narrativa"
    PUNTO_DE_VISTA = "punto_de_vista"
    PERSONAJE_FOCAL = "personaje_focal"
    ESTADO_REVISION = "estado_revision"
    NOTA_AUTOR = "nota_autor"


class RevisionState(str, Enum):
    BORRADOR = "borrador"
    REVISADO = "revisado"
    FINAL = "final"
    ARCHIVADO = "archivado"


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


# ── WritingUnit ────────────────────────────────────────────────────────


@dataclass
class WritingUnit:
    id: str
    name: str
    unit_type: WritingUnitType
    content: str = ""
    summary: str = ""
    parent_id: str | None = None
    order: int = 0
    entity_ids: list[str] = field(default_factory=list)
    framework_ids: list[str] = field(default_factory=list)
    domain_ids: list[str] = field(default_factory=list)
    layer_ids: list[str] = field(default_factory=list)
    timeline_event_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    revision_state: RevisionState = RevisionState.BORRADOR
    author_notes: str = ""
    canon_state: str = "borrador"
    visibility_state: str = "visible_usuario"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def touch(self) -> None:
        self.updated_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "unit_type": self.unit_type.value,
            "content": self.content,
            "summary": self.summary,
            "parent_id": self.parent_id,
            "order": self.order,
            "entity_ids": self.entity_ids,
            "framework_ids": self.framework_ids,
            "domain_ids": self.domain_ids,
            "layer_ids": self.layer_ids,
            "timeline_event_ids": self.timeline_event_ids,
            "source_ids": self.source_ids,
            "revision_state": self.revision_state.value,
            "author_notes": self.author_notes,
            "canon_state": self.canon_state,
            "visibility_state": self.visibility_state,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WritingUnit:
        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            unit_type=_parse_enum(
                WritingUnitType, data.get("unit_type"), WritingUnitType.ESCENA
            ),
            content=_parse_str(data.get("content")),
            summary=_parse_str(data.get("summary")),
            parent_id=data.get("parent_id"),
            order=_parse_int(data.get("order")),
            entity_ids=_parse_list(data.get("entity_ids")),
            framework_ids=_parse_list(data.get("framework_ids")),
            domain_ids=_parse_list(data.get("domain_ids")),
            layer_ids=_parse_list(data.get("layer_ids")),
            timeline_event_ids=_parse_list(data.get("timeline_event_ids")),
            source_ids=_parse_list(data.get("source_ids")),
            revision_state=_parse_enum(
                RevisionState, data.get("revision_state"), RevisionState.BORRADOR
            ),
            author_notes=_parse_str(data.get("author_notes")),
            canon_state=data.get("canon_state", "borrador"),
            visibility_state=data.get("visibility_state", "visible_usuario"),
            tags=_parse_list(data.get("tags")),
            metadata=(
                data["metadata"] if isinstance(data.get("metadata"), dict)
                else {}
            ),  # type: ignore[arg-type]
            created_at=data.get("created_at", _now()),
            updated_at=data.get("updated_at", _now()),
        )


__all__ = ["WritingUnit", "WritingUnitType", "RevisionState"]
