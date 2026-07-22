"""BETA2-SHIP-07: guardar/arrastrar años NO debe borrar la datación rica.

Bug (auditoría de datos): reconcile_entity_dating reconstruía el lapso con
from_years en cada guardado que tocara birth/death (incluido el pass-through del
panel de ficha), destruyendo precisión/era/fecha-mundo/notas y devolviendo la
naturaleza a MORTAL — un inmortal pasaba a mortal al arrastrar su línea de vida.
"""

from __future__ import annotations

from packages.application.temporal_dating import reconcile_entity_dating
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.temporal_models import (
    EventTemporality,
    TemporalNature,
    TemporalPrecision,
)
from packages.domain.temporal_span import TemporalSpan


def _rich_entity() -> NarrativeEntity:
    span = TemporalSpan(
        start=EventTemporality(
            year=-300,
            precision=TemporalPrecision.APPROXIMATE,
            era="Primera Edad",
            notes="circa la fundación",
        ),
        nature=TemporalNature.INMORTAL,
    )
    e = NarrativeEntity(name="Deidad", entity_type=EntityType.PERSONAJE)
    e.set_life_span(span)
    return e


def test_ficha_save_preserves_rich_dating():
    """Guardado normal (pass-through de birth/death con los mismos valores)."""
    e = _rich_entity()
    # El panel de ficha reenvía birth_year/death_year aunque solo se editara la prosa.
    reconcile_entity_dating(e, {"brief_description", "birth_year", "death_year"})
    span = e.life_span
    assert span.start.precision is TemporalPrecision.APPROXIMATE  # no degradada a EXACT
    assert span.start.era == "Primera Edad"
    assert span.start.notes == "circa la fundación"
    assert span.nature is TemporalNature.INMORTAL  # no volcada a MORTAL


def test_drag_year_keeps_nature_and_descriptors():
    """Arrastrar la línea de vida cambia el AÑO pero preserva lo demás."""
    e = _rich_entity()
    e.birth_year = -280  # el arrastre mueve el año-espejo
    reconcile_entity_dating(e, {"birth_year", "death_year"})
    span = e.life_span
    assert span.start.year == -280
    assert span.start.precision is TemporalPrecision.APPROXIMATE
    assert span.start.era == "Primera Edad"
    assert span.nature is TemporalNature.INMORTAL
    assert span.end is None  # inmortal: sigue sin fin


def test_no_prior_span_still_builds_from_years():
    """Sin lapso previo, se sigue construyendo desde el espejo entero."""
    e = NarrativeEntity(name="Humano", entity_type=EntityType.PERSONAJE)
    e.birth_year = 10
    e.death_year = 80
    reconcile_entity_dating(e, {"birth_year", "death_year"})
    assert e.life_span is not None
    assert e.life_span.start.year == 10
    assert e.life_span.end.year == 80


def test_adding_death_preserves_start_richness():
    """Poner un año de muerte no borra la riqueza del inicio."""
    e = _rich_entity()
    e.life_span.nature = TemporalNature.MORTAL  # ahora sí puede morir
    e.set_life_span(e.life_span)
    e.death_year = -200
    reconcile_entity_dating(e, {"death_year"})
    span = e.life_span
    assert span.end is not None and span.end.year == -200
    assert span.start.era == "Primera Edad"  # inicio intacto
    assert span.start.precision is TemporalPrecision.APPROXIMATE
