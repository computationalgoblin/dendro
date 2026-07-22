"""Normalización de datación en el write path — BETA1-J04.

Reemplaza el antiguo default silencioso a ``present_year``: una creación sin
fecha NO recibe un "presente" falso, sino un lapso marcado **pendiente /
incierto**. La obligatoriedad (bloqueo) se aplica solo en el write path de
producto (quick-create UI, aceptación de candidatos) vía ``enforce_dating``.
"""

from __future__ import annotations

from packages.domain.entity import NarrativeEntity
from packages.domain.entity_taxonomy import clamp_nature
from packages.domain.relation import NarrativeRelation
from packages.domain.temporal_models import (
    EventTemporality,
    TemporalNature,
    TemporalPrecision,
)
from packages.domain.temporal_span import TemporalSpan

PENDING_NOTE = "sin datar (pendiente)"
PRIMORDIAL_NOTE = "origen primordial"


def coerce_nature(value) -> TemporalNature | None:
    """BETA1-J07: coacciona str/enum a TemporalNature (None si no aplica)."""
    if isinstance(value, TemporalNature):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return TemporalNature(value.strip().lower())
        except ValueError:
            return None
    return None


def apply_nature_semantics(span: TemporalSpan) -> None:
    """BETA1-J07: ajusta el lapso a su naturaleza temporal.

    - eterno/atemporal → origen primordial (sin año mortal, precisión mítica),
      sin fin, vigente.
    - inmortal → sin fin, vigente (conserva el año de creación si lo hay)."""
    if span.is_eternal():
        span.start = EventTemporality(
            year=None, precision=TemporalPrecision.MYTHICAL, notes=PRIMORDIAL_NOTE
        )
        span.end = None
        span.ongoing = True
    elif span.nature is TemporalNature.INMORTAL:
        span.end = None
        span.ongoing = True


def pending_span() -> TemporalSpan:
    """Lapso 'por datar': inicio sin año, precisión desconocida, nota pendiente."""
    return TemporalSpan(
        start=EventTemporality(precision=TemporalPrecision.UNKNOWN, notes=PENDING_NOTE)
    )


def normalize_entity_dating(entity: NarrativeEntity, *, nature=None) -> None:
    """Garantiza un ``life_span`` coherente con el espejo entero y la naturaleza.

    Prioridad de fechas: ``life_span`` explícito > años enteros > 'pendiente'.
    NUNCA inventa el presente. Si se indica ``nature`` (BETA1-J07), se aplica y
    su semántica gobierna las fechas (un eterno no recibe nacimiento mortal)."""
    if entity.life_span is not None:
        span = entity.life_span
    elif entity.birth_year is not None:
        span = TemporalSpan.from_years(entity.birth_year, entity.death_year)
    else:
        span = pending_span()
    parsed = coerce_nature(nature)
    if parsed is not None:
        span.nature = parsed
    # BETA1-J08: la tabla manda — un no-ser nunca queda inmortal/eterno.
    span.nature = clamp_nature(entity.entity_type, span.nature)
    apply_nature_semantics(span)
    entity.set_life_span(span)


def _apply_mirror_years_to_span(span: TemporalSpan, birth_year, death_year) -> None:
    """Actualiza SOLO el eje entero de un lapso YA existente, preservando su
    datación rica (precisión/era/fecha-mundo/notas) y su naturaleza.

    BETA2-SHIP-07: antes se reconstruía con ``from_years`` en cada guardado que
    tocara birth/death (incluido el pass-through del panel de ficha), lo que
    borraba en silencio precisión/era/notas y devolvía la naturaleza a MORTAL
    (un inmortal pasaba a mortal al arrastrar su línea de vida). Ahora solo se
    mueve el año; los descriptores y la naturaleza se conservan."""
    if span.start is None:
        span.start = EventTemporality()
    span.start.year = birth_year
    if birth_year is not None and span.start.precision is TemporalPrecision.UNKNOWN:
        span.start.precision = TemporalPrecision.EXACT
    if death_year is not None:
        if span.end is not None:
            span.end.year = death_year
            if span.end.precision is TemporalPrecision.UNKNOWN:
                span.end.precision = TemporalPrecision.EXACT
        else:
            span.end = EventTemporality(year=death_year, precision=TemporalPrecision.EXACT)
        span.ongoing = False
    else:
        span.end = None
        span.ongoing = True
    # La naturaleza (inmortal/eterno) gobierna la coherencia de los extremos.
    apply_nature_semantics(span)


def reconcile_entity_dating(entity: NarrativeEntity, changed_keys: set[str]) -> None:
    """Para updates: respeta qué campo tocó el usuario (mirror vs life_span)."""
    if "life_span" in changed_keys and entity.life_span is not None:
        entity.set_life_span(entity.life_span)
    elif changed_keys & {"birth_year", "death_year"}:
        # BETA2-SHIP-07: si ya hay lapso rico, solo mover el año (no reconstruir,
        # que destruía precisión/era/notas/naturaleza). from_years solo cuando no
        # hay lapso previo del que preservar nada.
        if entity.life_span is not None:
            _apply_mirror_years_to_span(entity.life_span, entity.birth_year, entity.death_year)
            entity.set_life_span(entity.life_span)
        else:
            entity.set_life_span(TemporalSpan.from_years(entity.birth_year, entity.death_year))
    else:
        normalize_entity_dating(entity)


def normalize_relation_dating(relation: NarrativeRelation) -> None:
    if relation.life_span is not None:
        relation.set_life_span(relation.life_span)
    elif relation.birth_year is not None:
        relation.set_life_span(TemporalSpan.from_years(relation.birth_year, relation.death_year))
    else:
        relation.set_life_span(pending_span())


def normalize_milestone_dating(milestone) -> None:
    """El hito no tiene ``life_span`` persistido; marca su ``temporality`` rico
    como pendiente cuando no está datado."""
    has_note = bool((milestone.temporality.notes or "").strip())
    if not milestone.as_temporal_span().is_dated() and not has_note:
        milestone.temporality.notes = PENDING_NOTE


def is_uncertain_dating(entity: NarrativeEntity) -> bool:
    """BETA1-J05: ¿la datación de la entidad está sin fundamentar?

    True si no hay datación real (pendiente) o si el inicio está marcado como
    'no fundamentado' (migración v27) o pendiente, aunque tenga un año-placeholder.
    Es el criterio de selección para la re-datación en lote por IA."""
    span = entity.life_span
    if span is None:
        return entity.birth_year is None
    if not span.is_dated():
        return True
    note = (span.start.notes or "") if span.start is not None else ""
    return "no fundamentado" in note or PENDING_NOTE in note


def find_uncertain_entities(project) -> list[NarrativeEntity]:
    """Entidades candidatas a re-datación por IA (datación sin fundamentar)."""
    return [e for e in getattr(project, "entities", []) if is_uncertain_dating(e)]


__all__ = [
    "PENDING_NOTE",
    "PRIMORDIAL_NOTE",
    "coerce_nature",
    "apply_nature_semantics",
    "pending_span",
    "normalize_entity_dating",
    "reconcile_entity_dating",
    "normalize_relation_dating",
    "normalize_milestone_dating",
    "is_uncertain_dating",
    "find_uncertain_entities",
]
