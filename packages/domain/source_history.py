"""
Source and history entry — domain models.

Provides ``Source`` (traceable origin of narrative data) and
``HistoryEntry`` (audit event for every relevant mutation).
Bloque 5 — contrato_fases §5.2–§5.4.
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


class SourceType(str, Enum):
    """Tipos de fuente — §5.2 (10 valores)."""

    ENTRADA_MANUAL = "entrada_manual"
    DOCUMENTO_IMPORTADO = "documento_importado"
    FRAGMENTO_DOCUMENTAL = "fragmento_documental"
    GENERACION_IA = "generacion_ia"
    SUGERENCIA_IA_ACEPTADA = "sugerencia_ia_aceptada"
    SESION_ROL = "sesion_rol"
    NOTA_POST_SESION = "nota_post_sesion"
    DECISION_USUARIO = "decision_usuario"
    VERSION_ANTERIOR = "version_anterior"
    PLANTILLA_MARCO = "plantilla_marco"


class SourceState(str, Enum):
    """Estado de fuente (2 valores)."""

    ACTIVA = "activa"
    ARCHIVADA = "archivada"


class HistoryEventType(str, Enum):
    """Tipos de evento trazable — §5.4 (16 operaciones) + riego (BETA2-FOCO, 3)."""

    CREACION_PROYECTO = "creacion_proyecto"
    CAMBIO_CONFIGURACION = "cambio_configuracion"
    CREACION_ENTIDAD = "creacion_entidad"
    EDICION_ENTIDAD = "edicion_entidad"
    CAMBIO_CANON = "cambio_canon"
    CAMBIO_VISIBILIDAD = "cambio_visibilidad"
    ARCHIVADO_ENTIDAD = "archivado_entidad"
    RESTAURACION_ENTIDAD = "restauracion_entidad"
    CREACION_RELACION = "creacion_relacion"
    EDICION_RELACION = "edicion_relacion"
    ARCHIVADO_RELACION = "archivado_relacion"
    ASOCIACION_FUENTE = "asociacion_fuente"
    FUSION_ENTIDADES = "fusion_entidades"
    ACEPTACION_SUGERENCIA = "aceptacion_sugerencia"
    IMPORTACION_DOCUMENTAL = "importacion_documental"
    ACTUALIZACION_POST_SESION = "actualizacion_post_sesion"
    # BETA2-FOCO: jardín narrativo (riego). El riego diagnostica, no muta canon.
    RIEGO_ENTIDAD = "riego_entidad"
    SECADO_ENTIDAD = "secado_entidad"
    CULTIVO_ENTIDAD = "cultivo_entidad"


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


def _parse_list(value: Any) -> list:
    if isinstance(value, list):
        return list(value)
    return []


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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


# ═══════════════════════════════════════════════════════════════════════
# Source — §5.2
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class Source:
    """Traceable origin of narrative data.

    11 fields as specified in §5.2.  This is a standalone entity;
    existing ``origin`` / ``source`` string fields in
    ``NarrativeEntity`` and ``NarrativeRelation`` are preserved for
    backward compatibility and coexist with ``Source`` objects.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: SourceType = SourceType.ENTRADA_MANUAL
    name: str = ""
    description: str = ""
    reference: str = ""
    fragment: str = ""
    incorporated_at: datetime = field(default_factory=_now)
    state: SourceState = SourceState.ACTIVA
    metadata: dict[str, Any] = field(default_factory=dict)
    derived_entity_ids: list[str] = field(default_factory=list)
    derived_relation_ids: list[str] = field(default_factory=list)

    def touch(self) -> None:
        pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type.value,
            "name": self.name,
            "description": self.description,
            "reference": self.reference,
            "fragment": self.fragment,
            "incorporated_at": self.incorporated_at.isoformat(),
            "state": self.state.value,
            "metadata": dict(self.metadata),
            "derived_entity_ids": list(self.derived_entity_ids),
            "derived_relation_ids": list(self.derived_relation_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Source:
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            source_type=_parse_enum(
                SourceType, data.get("source_type"), SourceType.ENTRADA_MANUAL,
            ),
            name=data.get("name", ""),
            description=data.get("description", ""),
            reference=data.get("reference", ""),
            fragment=data.get("fragment", ""),
            incorporated_at=_parse_datetime(data.get("incorporated_at")),
            state=_parse_enum(
                SourceState, data.get("state"), SourceState.ACTIVA,
            ),
            metadata=_parse_dict(data.get("metadata")),
            derived_entity_ids=_parse_list(data.get("derived_entity_ids")),
            derived_relation_ids=_parse_list(data.get("derived_relation_ids")),
        )


# ═══════════════════════════════════════════════════════════════════════
# HistoryEntry — §5.3
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class HistoryEntry:
    """Audit event for every relevant mutation.

    14 fields as specified in §5.3.  Created automatically by
    ``HistoryService`` (B05-T03) whenever a tracked operation
    occurs on an entity, relation, or source.

    ``previous_value`` and ``new_value`` are ``Any | None`` to
    support strings, dicts, lists, and other JSON-serializable types.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: HistoryEventType = HistoryEventType.CREACION_ENTIDAD
    timestamp: datetime = field(default_factory=_now)
    affected_entity_id: str | None = None
    affected_relation_id: str | None = None
    affected_source_id: str | None = None
    previous_value: Any | None = None
    new_value: Any | None = None
    change_origin: str = ""
    reason: str = ""
    operation: str = ""
    responsible: str = ""
    reversible: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def description(self) -> str:
        """Backward-compatible alias used by HistoryService callers."""
        return self.reason

    @description.setter
    def description(self, value: str) -> None:
        self.reason = value

    def touch(self) -> None:
        pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "affected_entity_id": self.affected_entity_id,
            "affected_relation_id": self.affected_relation_id,
            "affected_source_id": self.affected_source_id,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
            "change_origin": self.change_origin,
            "reason": self.reason,
            "operation": self.operation,
            "responsible": self.responsible,
            "reversible": self.reversible,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryEntry:
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            event_type=_parse_enum(
                HistoryEventType, data.get("event_type"),
                HistoryEventType.CREACION_ENTIDAD,
            ),
            timestamp=_parse_datetime(data.get("timestamp")),
            affected_entity_id=data.get("affected_entity_id"),
            affected_relation_id=data.get("affected_relation_id"),
            affected_source_id=data.get("affected_source_id"),
            previous_value=data.get("previous_value"),
            new_value=data.get("new_value"),
            change_origin=data.get("change_origin", ""),
            reason=data.get("reason", ""),
            operation=data.get("operation", ""),
            responsible=data.get("responsible", ""),
            reversible=data.get("reversible", False),
            metadata=_parse_dict(data.get("metadata")),
        )


__all__ = [
    "Source",
    "SourceType",
    "SourceState",
    "HistoryEntry",
    "HistoryEventType",
]
