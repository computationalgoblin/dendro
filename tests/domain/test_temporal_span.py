"""BETA1-J01 — TemporalSpan: lapso temporal rico y espejo entero.

Verifica round-trip, derivación del año entero, contains/is_dated y la
invariante de sincronización año↔span en entidad, relación e hito.
"""

from __future__ import annotations

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.entity import NarrativeEntity
from packages.domain.relation import NarrativeRelation
from packages.domain.temporal_models import (
    EventTemporality,
    TemporalNature,
    TemporalPrecision,
)
from packages.domain.temporal_span import TemporalSpan

# ── EventTemporality: año entero nuevo ────────────────────────────────────


def test_event_temporality_year_roundtrips():
    et = EventTemporality(
        year=-340, world_date="3 de Lluvias", precision=TemporalPrecision.APPROXIMATE
    )
    back = EventTemporality.from_dict(et.to_dict())
    assert back.year == -340
    assert back.world_date == "3 de Lluvias"
    assert back.precision is TemporalPrecision.APPROXIMATE


def test_event_temporality_legacy_dict_without_year():
    # Documentos viejos sin 'year' → None, sin romper.
    back = EventTemporality.from_dict({"world_date": "antiguo"})
    assert back.year is None


# ── TemporalSpan: construcción, round-trip, helpers ───────────────────────


def test_from_years_open_span_is_ongoing():
    span = TemporalSpan.from_years(120, None)
    assert span.start_year == 120
    assert span.end_year is None
    assert span.ongoing is True


def test_from_years_closed_span_not_ongoing():
    span = TemporalSpan.from_years(120, 188)
    assert span.start_year == 120 and span.end_year == 188
    assert span.ongoing is False


def test_post_init_forces_not_ongoing_when_end_present():
    span = TemporalSpan(
        start=EventTemporality(year=10), end=EventTemporality(year=20), ongoing=True
    )
    assert span.ongoing is False


def test_roundtrip_preserves_richness():
    span = TemporalSpan(
        start=EventTemporality(
            year=300, world_date="Era de Bronce", precision=TemporalPrecision.APPROXIMATE
        ),
        end=EventTemporality(year=355, precision=TemporalPrecision.EXACT),
    )
    back = TemporalSpan.from_dict(span.to_dict())
    assert back.start_year == 300 and back.end_year == 355
    assert back.start.world_date == "Era de Bronce"
    assert back.start.precision is TemporalPrecision.APPROXIMATE
    assert back.ongoing is False


def test_contains_open_and_closed():
    closed = TemporalSpan.from_years(100, 200)
    assert closed.contains(150)
    assert not closed.contains(99)
    assert not closed.contains(201)
    open_span = TemporalSpan.from_years(100, None)
    assert open_span.contains(10_000)
    assert not open_span.contains(50)


def test_is_dated_concrete_year():
    assert TemporalSpan.from_years(42, None).is_dated()


def test_is_dated_explicit_precision_without_year():
    span = TemporalSpan(start=EventTemporality(year=None, precision=TemporalPrecision.MYTHICAL))
    assert span.is_dated()


def test_is_dated_by_descriptor_without_year():
    # Sin año pero con un descriptor temporal explícito → datado.
    span = TemporalSpan(start=EventTemporality(year=None, world_date="3 de Lluvias, 342 EC"))
    assert span.is_dated() is True


def test_not_dated_blank_by_inertia():
    # Blanco real: año None, precisión por defecto UNKNOWN, sin descriptores.
    # NO cuenta como datación (clave para la regla 'obligatorio' de J04).
    span = TemporalSpan(start=EventTemporality())
    assert span.is_dated() is False


# ── Invariante de sincronización en los modelos ───────────────────────────


def test_entity_set_life_span_syncs_mirror():
    e = NarrativeEntity(name="Eldrin")
    e.set_life_span(TemporalSpan.from_years(-12, 88))
    assert e.birth_year == -12 and e.death_year == 88
    assert e.as_temporal_span().start_year == -12


def test_entity_roundtrip_preserves_life_span():
    e = NarrativeEntity(name="Eldrin")
    e.set_life_span(
        TemporalSpan(start=EventTemporality(year=-12, world_date="Fundación"), end=None)
    )
    back = NarrativeEntity.from_dict(e.to_dict())
    assert back.birth_year == -12
    assert back.life_span is not None
    assert back.life_span.start.world_date == "Fundación"
    assert back.life_span.ongoing is True


def test_entity_legacy_dict_without_life_span():
    e = NarrativeEntity(name="Legacy", birth_year=33)
    d = e.to_dict()
    d.pop("life_span")
    back = NarrativeEntity.from_dict(d)
    assert back.life_span is None
    # ensure_life_span lo construye desde el espejo entero.
    assert back.ensure_life_span().start_year == 33


def test_relation_set_life_span_syncs_mirror():
    r = NarrativeRelation(source_id="a", target_id="b")
    r.set_life_span(TemporalSpan.from_years(50, None))
    assert r.birth_year == 50 and r.death_year is None
    back = NarrativeRelation.from_dict(r.to_dict())
    assert back.life_span is not None and back.life_span.start_year == 50


def test_milestone_as_temporal_span_uses_year_mirror():
    hito = CausalMilestone(title="Origen", year=-1000)
    span = hito.as_temporal_span()
    assert span.start_year == -1000
    assert span.end is None


# ── Naturaleza temporal (BETA1-J07) ───────────────────────────────────────


def test_nature_defaults_mortal():
    assert TemporalSpan().nature is TemporalNature.MORTAL


def test_nature_roundtrips():
    span = TemporalSpan(start=EventTemporality(), nature=TemporalNature.ETERNO)
    back = TemporalSpan.from_dict(span.to_dict())
    assert back.nature is TemporalNature.ETERNO


def test_old_dict_without_nature_defaults_mortal():
    d = TemporalSpan.from_years(10, None).to_dict()
    d.pop("nature")
    assert TemporalSpan.from_dict(d).nature is TemporalNature.MORTAL


def test_is_immortal_and_eternal():
    assert TemporalSpan(nature=TemporalNature.INMORTAL).is_immortal()
    assert not TemporalSpan(nature=TemporalNature.INMORTAL).is_eternal()
    assert TemporalSpan(nature=TemporalNature.ETERNO).is_eternal()
    assert TemporalSpan(nature=TemporalNature.ATEMPORAL).is_immortal()
    assert not TemporalSpan(nature=TemporalNature.MORTAL).is_immortal()


def test_eternal_is_dated_without_year():
    # Un eterno sin año cuenta como datado por su naturaleza (no se bloquea).
    span = TemporalSpan(start=EventTemporality(year=None), nature=TemporalNature.ETERNO)
    assert span.is_dated() is True


def test_milestone_to_dict_field_count_unchanged_by_j01():
    # as_temporal_span es vista computada: J01 NO añade campos persistidos al
    # hito (su conteo de baseline, 23, queda intacto).
    assert len(CausalMilestone(title="x", year=1).to_dict()) == 24  # +parent_milestone_id (BETA2-SUB)
