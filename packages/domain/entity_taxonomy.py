"""Taxonomía curada de tipos — BETA1-J08.

Única fuente (universal) de qué tipos se OFRECEN en las cajas (hoja, rama,
relación) y de qué **naturaleza temporal** aplica a cada tipo. La comparten
UI, servicios y validador; el prompt NO la lleva entera (la tabla manda y el
servicio corrige). stdlib-only, solo depende de otros modelos de dominio.

Principios (decididos con el usuario):
- **Hoja y Rama ofrecen subconjuntos DISTINTOS** (J08-fix): la hoja es un
  individuo/concepto concreto; la rama es un contenedor que agrupa (facción,
  cultura, localización…). Un tipo puede vivir en ambos (localización: un reino
  es contenedor; una taberna es concreta) — hoy ninguno se solapa.
- Solo los SERES (personaje, criatura) tienen eje de naturaleza temporal, y solo
  son hoja.
- No se poda el enum: los valores ocultos se conservan (datos viejos), solo se
  dejan de ofrecer.
"""

from __future__ import annotations

from packages.domain.entity import EntityType
from packages.domain.relation import RelationType
from packages.domain.temporal_models import TemporalNature

# ── EntityType: reparto hoja / rama ─────────────────────────────────────────

# Hoja = elemento individual o concepto puntual.
LEAF_ENTITY_TYPES: tuple[EntityType, ...] = (
    EntityType.PERSONAJE,
    EntityType.CRIATURA,
    EntityType.OBJETO,
    EntityType.TECNOLOGIA,
    EntityType.IDIOMA,
)

# Rama = contenedor que agrupa (miembros, sublugares, prácticas…).
BRANCH_ENTITY_TYPES: tuple[EntityType, ...] = (
    EntityType.FACCION,
    EntityType.CULTURA,
    EntityType.RELIGION,
    EntityType.INSTITUCION,
    EntityType.SISTEMA_MAGICO,
    EntityType.LOCALIZACION,
)

# Conjunto curado total (unión, en orden de enum) — lo usan el prompt, el
# inspector de corpus y cualquier consumidor "agnóstico de rol".
_OFFERED_SET = frozenset(LEAF_ENTITY_TYPES) | frozenset(BRANCH_ENTITY_TYPES)
OFFERED_ENTITY_TYPES: tuple[EntityType, ...] = tuple(
    t for t in EntityType if t in _OFFERED_SET
)

# Tipos que se conservan en el enum pero NO se ofrecen en ninguna caja:
# redundantes con subsistemas dedicados (escenas/sesiones/pistas/secretos),
# un rol más que un tipo (contenedor), o retirados por el usuario del set
# ofrecido (evento, conflicto, regla_del_mundo, trama, nota).
HIDDEN_ENTITY_TYPES: frozenset[EntityType] = frozenset(
    t for t in EntityType if t not in _OFFERED_SET
)

# ── Naturaleza temporal por tipo ────────────────────────────────────────────

# Únicos tipos con eje de naturaleza (seres). Solo viven como hoja.
BEING_TYPES: frozenset[EntityType] = frozenset(
    {EntityType.PERSONAJE, EntityType.CRIATURA}
)

# Naturalezas ofrecidas a un ser.
BEING_NATURES: tuple[TemporalNature, ...] = (
    TemporalNature.MORTAL,
    TemporalNature.INMORTAL,
    TemporalNature.ETERNO,
)


def is_branch_type(entity_type: "EntityType | str | None") -> bool:
    """¿Este tipo hace que la entidad sea una RAMA (contenedor que agrupa)?

    La ramitud se DERIVA del tipo: los tipos de rama de la taxonomía
    (`BRANCH_ENTITY_TYPES`) la hacen rama. Se reconoce además el rol legado
    `CONTENEDOR` (ramas de proyectos antiguos, creadas antes de derivar la
    ramitud del tipo) para no perder datos ni comportamiento.

    Acepta un `EntityType` o su `value` (string); un tipo personalizado
    desconocido cuenta como hoja.
    """
    if entity_type is None:
        return False
    if isinstance(entity_type, str):
        try:
            entity_type = EntityType(entity_type.strip().lower())
        except ValueError:
            return False  # tipo personalizado → hoja
    return entity_type in BRANCH_ENTITY_TYPES or entity_type == EntityType.CONTENEDOR


def is_branch(entity: object) -> bool:
    """¿Esta entidad es una rama? Se deriva de su `entity_type`."""
    return is_branch_type(getattr(entity, "entity_type", None))


def has_temporal_nature(entity_type: EntityType) -> bool:
    """¿Este tipo tiene eje de naturaleza temporal (es un ser)?"""
    return entity_type in BEING_TYPES


def allowed_natures(entity_type: EntityType) -> tuple[TemporalNature, ...]:
    """Naturalezas válidas para un tipo (vacío si no es un ser)."""
    return BEING_NATURES if entity_type in BEING_TYPES else ()


def clamp_nature(entity_type: EntityType, nature: TemporalNature) -> TemporalNature:
    """Corrige la naturaleza para que sea coherente con el tipo (la tabla manda).

    Un no-ser SIEMPRE es MORTAL (no existe un objeto eterno); un ser que reciba
    una naturaleza fuera de las permitidas cae a MORTAL."""
    if entity_type not in BEING_TYPES:
        return TemporalNature.MORTAL
    return nature if nature in BEING_NATURES else TemporalNature.MORTAL


# ── RelationType ────────────────────────────────────────────────────────────

# Familia "conocimiento" (B25) y familia del MOTOR CAUSAL (hitos): se conservan
# en el enum pero no se ofrecen como relación manual entidad↔entidad.
HIDDEN_RELATION_TYPES: frozenset[RelationType] = frozenset(
    {
        # Conocimiento (B25)
        RelationType.CONOCE,
        RelationType.DESCONOCE,
        RelationType.SOSPECHA,
        RelationType.OCULTA,
        RelationType.REVELA,
        RelationType.SABE,
        RelationType.CREE,
        RelationType.IGNORA,
        RelationType.MALINTERPRETA,
        RelationType.HA_OIDO,
        RelationType.HA_VISTO,
        RelationType.HA_RECIBIDO_PISTA,
        RelationType.CONOCE_PARCIALMENTE,
        RelationType.CONOCE_FALSAMENTE,
        RelationType.POSEE_CONOCIMIENTO,
        RelationType.REVELA_CONOCIMIENTO,
        # Motor causal (subsistema de hitos, no relación manual)
        RelationType.CAUSO,
        RelationType.FUE_CAUSADO_POR,
        RelationType.PRODUCE_CONSECUENCIA_EN,
        RelationType.CONDICIONA,
        RelationType.DERIVA_DE,
        RelationType.EXPLICA,
        RelationType.CONTRADICE,
        RelationType.DEPENDE_DE,
    }
)

OFFERED_RELATION_TYPES: tuple[RelationType, ...] = tuple(
    r for r in RelationType if r not in HIDDEN_RELATION_TYPES
)


__all__ = [
    "LEAF_ENTITY_TYPES",
    "BRANCH_ENTITY_TYPES",
    "HIDDEN_ENTITY_TYPES",
    "OFFERED_ENTITY_TYPES",
    "BEING_TYPES",
    "BEING_NATURES",
    "is_branch_type",
    "is_branch",
    "has_temporal_nature",
    "allowed_natures",
    "clamp_nature",
    "HIDDEN_RELATION_TYPES",
    "OFFERED_RELATION_TYPES",
]
