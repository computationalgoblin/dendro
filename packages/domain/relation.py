"""
Narrative relation — domain model.

Provides ``NarrativeRelation``, the first-class entity that links
two narrative entities with semantics, direction, intensity, and
traceability. Reuses ``CanonState``, ``VisibilityState``, and
``CertaintyLevel`` from ``entity.py`` to avoid incompatible states
between entities and relations.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from packages.domain.custom_types import CustomFieldValue
from packages.domain.entity import CanonState, CertaintyLevel, VisibilityState

# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class RelationType(str, Enum):
    """Tipos de relación narrativa — §4.3 (27 valores)."""

    PERTENECE_A = "pertenece_a"
    CONTIENE = "contiene"
    ESTA_UBICADO_EN = "esta_ubicado_en"
    PARTICIPO_EN = "participo_en"
    CAUSO = "causo"
    FUE_CAUSADO_POR = "fue_causado_por"
    GOBIERNA = "gobierna"
    SIRVE_A = "sirve_a"
    ES_ALIADO_DE = "es_aliado_de"
    ES_ENEMIGO_DE = "es_enemigo_de"
    CONOCE="cono..."
    DESCONOCE = "desconoce"
    SOSPECHA = "sospecha"
    OCULTA = "oculta"
    REVELA = "revela"
    CONTRADICE = "contradice"
    DEPENDE_DE = "depende_de"
    DERIVA_DE = "deriva_de"
    SIMBOLIZA = "simboliza"
    POSEE = "posee"
    BUSCA = "busca"
    PROTEGE = "protege"
    TRAICIONO = "traiciono"
    CONTROLA = "controla"
    ESTA_EN_CONFLICTO_CON = "esta_en_conflicto_con"
    TIENE_DEUDA_CON = "tiene_deuda_con"
    ESTA_RELACIONADO_CON = "esta_relacionado_con"
    # ── Knowledge types (B25-T00, DC-039) ──
    SABE = "sabe"
    CREE = "cree"
    IGNORA = "ignora"
    MALINTERPRETA = "malinterpreta"
    HA_OIDO = "ha_oido"
    HA_VISTO = "ha_visto"
    HA_RECIBIDO_PISTA = "ha_recibido_pista"
    CONOCE_PARCIALMENTE = "conoce_parcialmente"
    CONOCE_FALSAMENTE = "conoce_falsamente"
    POSEE_CONOCIMIENTO = "posee_conocimiento"
    REVELA_CONOCIMIENTO = "revela_conocimiento"


class Direction(str, Enum):
    """Dirección de la relación. La dirección real source→target la
    determinan source_id y target_id."""

    UNIDIRECCIONAL = "unidireccional"
    BIDIRECCIONAL = "bidireccional"


class IntensityLevel(str, Enum):
    """Intensidad de la relación (6 niveles)."""

    NINGUNA = "ninguna"
    MUY_BAJA = "muy_baja"
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    MUY_ALTA = "muy_alta"


# ═══════════════════════════════════════════════════════════════════════
# NarrativeRelation — §4.2
# ═══════════════════════════════════════════════════════════════════════


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class NarrativeRelation:
    """First-class relationship between two narrative entities.

    Contains 17 fields as specified in contrato_fases §4.2.
    Reuses canon/visibility/certainty states from ``entity.py``.
    Pertenencia al proyecto: por contención (``Project.relations``).
    """

    # --- Identity (1–3) ---
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""

    # --- Semantics (4–9) ---
    relation_type: RelationType = RelationType.ESTA_RELACIONADO_CON
    direction: Direction = Direction.UNIDIRECCIONAL
    description: str = ""
    intensity: IntensityLevel = IntensityLevel.MEDIA
    temporality: str = ""
    causality: str = ""

    # --- State (10–12, reused from entity.py) ---
    canon_state: CanonState = CanonState.BORRADOR
    visibility_state: VisibilityState = VisibilityState.VISIBLE_USUARIO
    certainty_level: CertaintyLevel = CertaintyLevel.PROBABLE

    # --- Traceability (13) ---
    source: str = ""

    # --- Timestamps (14–15) ---
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    # --- Conditions & metadata (16–18) ---
    validity_conditions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    custom_metadata: dict[str, Any] = field(default_factory=dict)

    # --- Custom types and fields (Bloque 8) ---
    custom_relation_type_id: str | None = None
    custom_fields: list[Any] = field(default_factory=list)  # list[CustomFieldValue]

    # --- Layers — structured (Bloque 10) ---
    layer_ids: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def touch(self) -> None:
        self.updated_at = _now()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "direction": self.direction.value,
            "description": self.description,
            "intensity": self.intensity.value,
            "temporality": self.temporality,
            "causality": self.causality,
            "canon_state": self.canon_state.value,
            "visibility_state": self.visibility_state.value,
            "certainty_level": self.certainty_level.value,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "validity_conditions": list(self.validity_conditions),
            "tags": list(self.tags),
            "custom_metadata": dict(self.custom_metadata),
            "custom_relation_type_id": self.custom_relation_type_id,
            "custom_fields": [
                f if isinstance(f, dict) else (
                    f.to_dict() if hasattr(f, "to_dict") else f
                )
                for f in self.custom_fields
            ],
            "layer_ids": list(self.layer_ids),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NarrativeRelation:
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            source_id=data.get("source_id", ""),
            target_id=data.get("target_id", ""),
            relation_type=_parse_enum(
                RelationType, data.get("relation_type"),
                RelationType.ESTA_RELACIONADO_CON,
            ),
            direction=_parse_enum(
                Direction, data.get("direction"), Direction.UNIDIRECCIONAL,
            ),
            description=data.get("description", ""),
            intensity=_parse_enum(
                IntensityLevel, data.get("intensity"), IntensityLevel.MEDIA,
            ),
            temporality=data.get("temporality", ""),
            causality=data.get("causality", ""),
            canon_state=_parse_enum(
                CanonState, data.get("canon_state"), CanonState.BORRADOR,
            ),
            visibility_state=_parse_enum(
                VisibilityState, data.get("visibility_state"),
                VisibilityState.VISIBLE_USUARIO,
            ),
            certainty_level=_parse_enum(
                CertaintyLevel, data.get("certainty_level"),
                CertaintyLevel.PROBABLE,
            ),
            source=data.get("source", ""),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            validity_conditions=_parse_list(data.get("validity_conditions")),
            tags=_parse_list(data.get("tags")),
            custom_metadata=_parse_dict(data.get("custom_metadata")),
            custom_relation_type_id=data.get("custom_relation_type_id"),
            custom_fields=[
                CustomFieldValue.from_dict(f) if isinstance(f, dict) else f
                for f in _parse_list(data.get("custom_fields"))
            ],
            layer_ids=_parse_list(data.get("layer_ids")),
        )


# ═══════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════


def validate_relation(relation: NarrativeRelation) -> list[str]:
    """Return structural validation issues (empty = valid)."""
    issues: list[str] = []

    if not relation.source_id:
        issues.append("Relation source_id is empty")
    if not relation.target_id:
        issues.append("Relation target_id is empty")
    if not relation.id:
        issues.append("Relation id is empty")

    return issues


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


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


__all__ = [
    "NarrativeRelation",
    "RelationType",
    "Direction",
    "IntensityLevel",
    "validate_relation",
]
