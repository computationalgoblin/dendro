"""
Narrative entity — domain model.

Provides ``NarrativeEntity``, the fundamental unit of the narrative
knowledge base, and supporting enums for canon state, visibility,
entity type, certainty, importance, and development level.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from packages.domain.custom_types import CustomFieldValue

# ═══════════════════════════════════════════════════════════════════════
# Enums — §3.3, §3.4, §3.5
# ═══════════════════════════════════════════════════════════════════════


class EntityType(str, Enum):
    """Taxonomía de tipos de entidad narrativa — §3.3 (21 valores)."""

    PERSONAJE = "personaje"
    LOCALIZACION = "localizacion"
    FACCION = "faccion"
    CULTURA = "cultura"
    OBJETO = "objeto"
    EVENTO = "evento"
    ESCENA = "escena"
    SESION = "sesion"
    CONFLICTO = "conflicto"
    SECRETO = "secreto"
    PISTA = "pista"
    REGLA_DEL_MUNDO = "regla_del_mundo"
    TECNOLOGIA = "tecnologia"
    SISTEMA_MAGICO = "sistema_magico"
    RELIGION = "religion"
    IDIOMA = "idioma"
    INSTITUCION = "institucion"
    CRIATURA = "criatura"
    TRAMA = "trama"
    CONTENEDOR = "contenedor"
    NOTA = "nota"


class CanonState(str, Enum):
    """Estados de canon — §3.4 (13 valores)."""

    CANONICO = "canonico"
    BORRADOR = "borrador"
    HIPOTESIS = "hipotesis"
    SUGERIDO_IA = "sugerido_ia"
    IMPORTADO_PENDIENTE = "importado_pendiente"
    CONTRADICTORIO = "contradictorio"
    OBSOLETO = "obsoleto"
    DESCARTADO = "descartado"
    ARCHIVADO = "archivado"
    SECRETO_CANONICO = "secreto_canonico"
    RUMOR_INTERNO = "rumor_interno"
    FALSO = "falso"
    INTERPRETACION_SUBJETIVA = "interpretacion_subjetiva"


class VisibilityState(str, Enum):
    """Estados de visibilidad — §3.5 (14 valores)."""

    PRIVADO_AUTOR = "privado_autor"
    VISIBLE_USUARIO = "visible_usuario"
    VISIBLE_JUGADORES = "visible_jugadores"
    VISIBLE_PERSONAJES = "visible_personajes"
    VISIBLE_FACCIONES = "visible_facciones"
    REVELADO = "revelado"
    REVELADO_PARCIAL = "revelado_parcial"
    PREPARADO_NO_REVELADO = "preparado_no_revelado"
    EXPORTABLE = "exportable"
    NO_EXPORTABLE = "no_exportable"
    PUBLICO_MUNDO = "publico_mundo"
    SECRETO_MUNDO = "secreto_mundo"
    RUMOR = "rumor"
    MENTIRA_CONOCIDA = "mentira_conocida"


class CertaintyLevel(str, Enum):
    """Niveles de certeza — §3.2 campo 9 (5 valores)."""

    CONFIRMADO = "confirmado"
    PROBABLE = "probable"
    POSIBLE = "posible"
    DUDOSO = "dudoso"
    FALSO = "falso"


class NarrativeImportance(str, Enum):
    """Importancia narrativa — §3.2 campo 18 (5 valores)."""

    CRITICO = "critico"
    ALTO = "alto"
    MEDIO = "medio"
    BAJO = "bajo"
    MENOR = "menor"


class DevelopmentLevel(str, Enum):
    """Nivel de desarrollo — §3.2 campo 19 (5 valores)."""

    COMPLETO = "completo"
    DESARROLLADO = "desarrollado"
    ESBOZO = "esbozo"
    SEMILLA = "semilla"
    VACIO = "vacio"


# ═══════════════════════════════════════════════════════════════════════
# NarrativeEntity — §3.2
# ═══════════════════════════════════════════════════════════════════════


def _now() -> datetime:
    """Return current UTC datetime (helper for field defaults)."""
    return datetime.now(timezone.utc)


@dataclass
class NarrativeEntity:
    """Fundamental unit of the narrative knowledge base.

    Represents any person, place, faction, object, event, or concept
    within a narrative project. Contains 20 fields as specified in
    contrato_fases §3.2.

    Pertenencia al proyecto: por contención (``Project.entities``),
    NO por ``project_id`` explícito.
    """

    # --- Identity (1–3) ---
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    aliases: list[str] = field(default_factory=list)

    # --- Classification (4–6) ---
    entity_type: EntityType = EntityType.NOTA
    brief_description: str = ""
    extended_description: str = ""

    # --- State (7–9) ---
    canon_state: CanonState = CanonState.BORRADOR
    visibility_state: VisibilityState = VisibilityState.VISIBLE_USUARIO
    certainty_level: CertaintyLevel = CertaintyLevel.PROBABLE

    # --- Taxonomical (10–13) ---
    tags: list[str] = field(default_factory=list)
    domain: str = ""
    layers: list[str] = field(default_factory=list)
    origin: str = ""

    # --- Domains & layers — structured (Bloque 10) ---
    domain_ids: list[str] = field(default_factory=list)
    layer_ids: list[str] = field(default_factory=list)

    # --- Timestamps (14–15) ---
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    # --- Notes (16–17) ---
    private_notes: str = ""
    exportable_notes: str = ""

    # --- Metadata (18–20) ---
    narrative_importance: NarrativeImportance = NarrativeImportance.MEDIO
    development_level: DevelopmentLevel = DevelopmentLevel.SEMILLA
    custom_metadata: dict[str, Any] = field(default_factory=dict)

    # --- Custom types and fields (Bloque 8) ---
    custom_type_id: str | None = None
    custom_fields: list[Any] = field(default_factory=list)  # list[CustomFieldValue]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def touch(self) -> None:
        """Update ``updated_at`` to the current time."""
        self.updated_at = _now()

    # ------------------------------------------------------------------
    # Serialisation (stdlib only — no dataclasses.asdict)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Produce a serialisable dict with snake_case keys.

        Enums are converted to their string values.  Datetime fields
        are rendered as ISO-8601 strings."""
        return {
            "id": self.id,
            "name": self.name,
            "aliases": list(self.aliases),
            "entity_type": self.entity_type.value,
            "brief_description": self.brief_description,
            "extended_description": self.extended_description,
            "canon_state": self.canon_state.value,
            "visibility_state": self.visibility_state.value,
            "certainty_level": self.certainty_level.value,
            "tags": list(self.tags),
            "domain": self.domain,
            "layers": list(self.layers),
            "origin": self.origin,
            "domain_ids": list(self.domain_ids),
            "layer_ids": list(self.layer_ids),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "private_notes": self.private_notes,
            "exportable_notes": self.exportable_notes,
            "narrative_importance": self.narrative_importance.value,
            "development_level": self.development_level.value,
            "custom_metadata": dict(self.custom_metadata),
            "custom_type_id": self.custom_type_id,
            "custom_fields": [
                f if isinstance(f, dict) else (
                    f.to_dict() if hasattr(f, "to_dict") else f
                )
                for f in self.custom_fields
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NarrativeEntity:
        """Reconstruct an entity from a dict, tolerating missing keys.

        Every absent key falls back to the dataclass field default.
        """
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            name=data.get("name", ""),
            aliases=_parse_list(data.get("aliases")),
            entity_type=_parse_enum(EntityType, data.get("entity_type"), EntityType.NOTA),
            brief_description=data.get("brief_description", ""),
            extended_description=data.get("extended_description", ""),
            canon_state=_parse_enum(CanonState, data.get("canon_state"), CanonState.BORRADOR),
            visibility_state=_parse_enum(
                VisibilityState, data.get("visibility_state"), VisibilityState.VISIBLE_USUARIO
            ),
            certainty_level=_parse_enum(
                CertaintyLevel, data.get("certainty_level"), CertaintyLevel.PROBABLE
            ),
            tags=_parse_list(data.get("tags")),
            domain=data.get("domain", ""),
            layers=_parse_list(data.get("layers")),
            origin=data.get("origin", ""),
            domain_ids=_parse_list(data.get("domain_ids")),
            layer_ids=_parse_list(data.get("layer_ids")),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            private_notes=data.get("private_notes", ""),
            exportable_notes=data.get("exportable_notes", ""),
            narrative_importance=_parse_enum(
                NarrativeImportance, data.get("narrative_importance"), NarrativeImportance.MEDIO
            ),
            development_level=_parse_enum(
                DevelopmentLevel, data.get("development_level"), DevelopmentLevel.SEMILLA
            ),
            custom_metadata=_parse_dict(data.get("custom_metadata")),
            custom_type_id=data.get("custom_type_id"),
            custom_fields=[
                CustomFieldValue.from_dict(f) if isinstance(f, dict) else f
                for f in _parse_list(data.get("custom_fields"))
            ],
        )


# ═══════════════════════════════════════════════════════════════════════
# Validation (pure domain functions)
# ═══════════════════════════════════════════════════════════════════════


def validate_entity(entity: NarrativeEntity) -> list[str]:
    """Return a list of validation issues (empty = valid).

    Checks basic structural integrity: name, entity_type, timestamps.
    Does NOT perform semantic or cross-entity validation.
    """
    issues: list[str] = []

    if not entity.name.strip():
        issues.append("Entity name is empty")

    if not entity.id:
        issues.append("Entity id is empty")

    if entity.entity_type is None:
        issues.append("Entity type is missing")

    if entity.created_at is None:
        issues.append("Entity created_at is missing")

    if entity.updated_at is None:
        issues.append("Entity updated_at is missing")

    return issues


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════


def _parse_list(value: Any) -> list:
    """Coerce *value* to a ``list``, returning ``[]`` on failure."""
    if isinstance(value, list):
        return list(value)
    return []


def _parse_dict(value: Any) -> dict[str, Any]:
    """Coerce *value* to a ``dict``, returning ``{}`` on failure."""
    if isinstance(value, dict):
        return dict(value)
    return {}


_EnumType = type[Enum]


def _parse_enum(enum_cls: _EnumType, value: Any, default: Any) -> Any:
    """Parse *value* as a member of *enum_cls*, falling back to *default*."""
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    return default


def _parse_datetime(value: Any) -> datetime:
    """Parse an ISO-8601 string to datetime, or return ``_now()``."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            pass
    return _now()


__all__ = [
    "NarrativeEntity",
    "EntityType",
    "CanonState",
    "VisibilityState",
    "CertaintyLevel",
    "NarrativeImportance",
    "DevelopmentLevel",
    "validate_entity",
]
