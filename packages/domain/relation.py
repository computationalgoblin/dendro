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
from packages.domain.temporal_span import TemporalSpan

# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class RelationType(str, Enum):
    """Tipos de relación narrativa — §4.3."""

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
    # BETA-FIX-04: el valor era literalmente "cono..." (typo) — el tipo
    # legítimo "conoce" no parseaba y caía al fallback. Alias de carga más abajo.
    CONOCE = "conoce"
    DESCONOCE = "desconoce"
    SOSPECHA = "sospecha"
    OCULTA = "oculta"
    REVELA = "revela"
    CONTRADICE = "contradice"
    DEPENDE_DE = "depende_de"
    DERIVA_DE = "deriva_de"
    CONDICIONA = "condiciona"
    EXPLICA = "explica"
    PRODUCE_CONSECUENCIA_EN = "produce_consecuencia_en"
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
    # ── Parentesco (BETA2-FIX-12, G2-16) ──
    # El enum tenía 41 tipos y NINGUNO de parentesco: en un árbol genealógico no
    # se podía decir «madre». La familia se ofrece entera (no entra en
    # HIDDEN_RELATION_TYPES) y viaja al Mapa, al Foco y al prompt.
    # OJO: parentesco NO es CONTENCIÓN. Ninguno de estos valores puede entrar en
    # los conjuntos de contención (foco_rings/foco_zones/watering_service/
    # issue_service/temporal_coherence): una madre no es una rama que contiene a
    # su hijo y no debe arrastrarlo de anillo.
    ES_PROGENITOR_DE = "es_progenitor_de"
    ES_MADRE_DE = "es_madre_de"
    ES_PADRE_DE = "es_padre_de"
    ES_HIJO_DE = "es_hijo_de"
    ES_HERMANO_DE = "es_hermano_de"
    ESTA_CASADO_CON = "esta_casado_con"
    ES_ANTEPASADO_DE = "es_antepasado_de"
    ES_DESCENDIENTE_DE = "es_descendiente_de"
    ES_FAMILIAR_DE = "es_familiar_de"


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
# Parentesco e inversos — BETA2-FIX-12 (G2-16)
# ═══════════════════════════════════════════════════════════════════════

# La familia de parentesco, como conjunto nombrado: la leen los tests de
# no-contención y cualquier consumidor que quiera tratarla como bloque.
KINSHIP_RELATION_TYPES: frozenset["RelationType"] = frozenset(
    {
        RelationType.ES_PROGENITOR_DE,
        RelationType.ES_MADRE_DE,
        RelationType.ES_PADRE_DE,
        RelationType.ES_HIJO_DE,
        RelationType.ES_HERMANO_DE,
        RelationType.ESTA_CASADO_CON,
        RelationType.ES_ANTEPASADO_DE,
        RelationType.ES_DESCENDIENTE_DE,
        RelationType.ES_FAMILIAR_DE,
    }
)

# Mapa de inversos. El enum YA practicaba el patrón (`contiene`/`pertenece_a`,
# `causo`/`fue_causado_por`) sin declararlo en ninguna parte; aquí se declara,
# para que la ficha del otro extremo pueda decir «hijo de» sin duplicar la
# arista.
#
# Reparto de género (decisión de producto de este ticket, pregunta abierta nº2):
# `es_madre_de`/`es_padre_de` existen porque son lo que la gente dice, y son
# ESPECIALIZACIONES de `es_progenitor_de`. Por eso el mapa es **total** (todo
# parentesco tiene inverso, y su inverso es también parentesco) y **cerrado**,
# pero solo es una involución estricta sobre el núcleo neutro: el inverso de
# `es_madre_de` es `es_hijo_de`, y el de `es_hijo_de` es el neutro
# `es_progenitor_de` (no puede adivinar el género del que no lo declaró). A
# partir del segundo paso el mapa es estable: inv(inv(inv(x))) == inv(x).
RELATION_INVERSES: dict["RelationType", "RelationType"] = {
    # Pares que el enum ya practicaba de hecho.
    RelationType.CONTIENE: RelationType.PERTENECE_A,
    RelationType.PERTENECE_A: RelationType.CONTIENE,
    RelationType.CAUSO: RelationType.FUE_CAUSADO_POR,
    RelationType.FUE_CAUSADO_POR: RelationType.CAUSO,
    # Parentesco.
    RelationType.ES_PROGENITOR_DE: RelationType.ES_HIJO_DE,
    RelationType.ES_MADRE_DE: RelationType.ES_HIJO_DE,
    RelationType.ES_PADRE_DE: RelationType.ES_HIJO_DE,
    RelationType.ES_HIJO_DE: RelationType.ES_PROGENITOR_DE,
    # Simétricas: son su propio inverso.
    RelationType.ES_HERMANO_DE: RelationType.ES_HERMANO_DE,
    RelationType.ESTA_CASADO_CON: RelationType.ESTA_CASADO_CON,
    RelationType.ES_FAMILIAR_DE: RelationType.ES_FAMILIAR_DE,
    RelationType.ES_ANTEPASADO_DE: RelationType.ES_DESCENDIENTE_DE,
    RelationType.ES_DESCENDIENTE_DE: RelationType.ES_ANTEPASADO_DE,
}


def inverse_relation_type(value: Any) -> "RelationType | None":
    """Tipo inverso declarado, o ``None`` si ese tipo no tiene pareja.

    Acepta el enum o su ``value``; un tipo desconocido devuelve ``None`` (no se
    inventa una simetría que el dominio no declara).
    """
    resolved = coerce_relation_type(value)
    if resolved is None:
        return None
    return RELATION_INVERSES.get(resolved)


def is_kinship(value: Any) -> bool:
    """¿Este tipo pertenece a la familia de parentesco?"""
    resolved = coerce_relation_type(value)
    return resolved is not None and resolved in KINSHIP_RELATION_TYPES


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

    # --- Temporal (BETA1-G06) ---
    birth_year: int | None = None   # año diegético en que nace la relación
    death_year: int | None = None   # año diegético en que termina; None = activa
    # Lapso rico (BETA1-J01): birth_year/death_year son su espejo entero.
    life_span: TemporalSpan | None = None

    # --- State (10–12, reused from entity.py) ---
    # BETA2-FOCO-16 (canon total): las relaciones también nacen canónicas.
    canon_state: CanonState = CanonState.CANONICO
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

    # ── Tiempo del mundo (BETA1-J01) — sincronización año↔span ─────────────

    def set_life_span(self, span: TemporalSpan) -> None:
        """Fija el lapso rico y sincroniza el espejo entero birth/death."""
        self.life_span = span
        self.birth_year = span.start_year
        self.death_year = span.end_year

    def ensure_life_span(self) -> TemporalSpan:
        if self.life_span is None:
            self.life_span = TemporalSpan.from_years(self.birth_year, self.death_year)
        return self.life_span

    def as_temporal_span(self) -> TemporalSpan:
        return self.ensure_life_span()

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
            "birth_year": self.birth_year,
            "death_year": self.death_year,
            "life_span": self.life_span.to_dict() if self.life_span is not None else None,
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
            # FIX-04: coerción con alias legado ("cono...") y fallback tolerante —
            # SOLO para cargas; la aceptación de candidatos valida antes.
            relation_type=(
                coerce_relation_type(data.get("relation_type"))
                or RelationType.ESTA_RELACIONADO_CON
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
            birth_year=_parse_optional_int(data.get("birth_year")),
            death_year=_parse_optional_int(data.get("death_year")),
            life_span=_parse_life_span(data.get("life_span")),
            canon_state=_parse_enum(
                CanonState, data.get("canon_state"), CanonState.CANONICO,
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


# FIX-04: valores persistidos por versiones con el typo del enum. Cargar sin
# pérdida (evolucion-esquema.md); al re-guardar sale ya el valor bueno.
_LEGACY_RELATION_TYPE_ALIASES: dict[str, str] = {"cono...": "conoce"}


def coerce_relation_type(value: Any) -> "RelationType | None":
    """RelationType desde texto con alias legado; None si es DESCONOCIDO.

    A diferencia de ``_parse_enum``, no aplana a un default: el llamador decide
    (la aceptación de candidatos rechaza con error visible; ``from_dict`` cae al
    default tolerante para no romper cargas).
    """
    if isinstance(value, RelationType):
        return value
    if isinstance(value, str):
        raw = value.strip().lower()
        raw = _LEGACY_RELATION_TYPE_ALIASES.get(raw, raw)
        try:
            return RelationType(raw)
        except ValueError:
            return None
    return None


def _parse_enum(enum_cls: _EnumType, value: Any, default: Any) -> Any:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    return default


def _parse_life_span(value: Any) -> TemporalSpan | None:
    """BETA1-J01: reconstruye el lapso si está presente; si no, ``None``."""
    if isinstance(value, dict):
        return TemporalSpan.from_dict(value)
    return None


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            pass
    return _now()


def _parse_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
    "coerce_relation_type",
    # BETA2-FIX-12 (G2-16)
    "KINSHIP_RELATION_TYPES",
    "RELATION_INVERSES",
    "inverse_relation_type",
    "is_kinship",
]
