"""BETA1-J02 — Validador determinista de coherencia temporal.

Una clase por regla, con caso positivo (incoherente → aviso) y negativo
(coherente o indeterminable → sin aviso).
"""

from __future__ import annotations

from packages.application.temporal_coherence import (
    evaluate_entity,
    evaluate_milestone,
    evaluate_relation,
)
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.era import Era
from packages.domain.project_chronology import ProjectChronology
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.temporal_models import EventTemporality, TemporalNature
from packages.domain.temporal_span import TemporalSpan


def _codes(issues):
    return {i.code for i in issues}


def _entity(name, birth, death=None, etype=EntityType.PERSONAJE):
    e = NarrativeEntity(name=name, entity_type=etype)
    e.set_life_span(TemporalSpan.from_years(birth, death))
    return e


def _chrono(present=1000, eras=None):
    return ProjectChronology(present_year=present, eras=eras or [])


# ── Regla 1: fin antes que inicio ─────────────────────────────────────────


class TestRule1EndBeforeStart:
    def test_flags_end_before_start(self):
        e = _entity("Paradoja", 100, 50)
        assert "T01_END_BEFORE_START" in _codes(evaluate_entity(e))

    def test_ok_when_ordered(self):
        e = _entity("Normal", 50, 100)
        assert "T01_END_BEFORE_START" not in _codes(evaluate_entity(e))


# ── Regla 2: fuera de eras ────────────────────────────────────────────────


class TestRule2OutsideEras:
    def test_flags_year_outside_eras(self):
        eras = [Era(name="Edad", start_year=0, end_year=500)]
        e = _entity("Tardío", 900)
        assert "T02_OUTSIDE_ERAS" in _codes(evaluate_entity(e, chronology=_chrono(2000, eras)))

    def test_ok_inside_era(self):
        eras = [Era(name="Edad", start_year=0, end_year=500)]
        e = _entity("Dentro", 300)
        assert "T02_OUTSIDE_ERAS" not in _codes(evaluate_entity(e, chronology=_chrono(2000, eras)))

    def test_skipped_when_no_eras(self):
        e = _entity("SinCalendario", 9999)
        assert "T02_OUTSIDE_ERAS" not in _codes(evaluate_entity(e, chronology=_chrono(0, [])))


# ── Regla 3: inicio después del presente ──────────────────────────────────


class TestRule3StartAfterPresent:
    def test_flags_future_start(self):
        e = _entity("Futuro", 3000)
        assert "T03_START_AFTER_PRESENT" in _codes(evaluate_entity(e, chronology=_chrono(1000)))

    def test_ok_in_past(self):
        e = _entity("Pasado", 500)
        assert "T03_START_AFTER_PRESENT" not in _codes(evaluate_entity(e, chronology=_chrono(1000)))


# ── Regla 4: relación fuera de la vida de un extremo ──────────────────────


class TestRule4RelationWithinEndpoints:
    def test_flags_relation_before_endpoint_born(self):
        src = _entity("Reciente", 200)
        tgt = _entity("Antiguo", 100)
        rel = NarrativeRelation(
            source_id=src.id, target_id=tgt.id, relation_type=RelationType.CONOCE
        )
        rel.set_life_span(TemporalSpan.from_years(150, None))  # antes de que nazca src(200)
        codes = _codes(evaluate_relation(rel, source=src, target=tgt))
        assert "T04_RELATION_BEFORE_ENDPOINT" in codes

    def test_flags_relation_after_endpoint_died(self):
        src = _entity("Muerto", 100, 180)
        tgt = _entity("Vivo", 100)
        rel = NarrativeRelation(
            source_id=src.id, target_id=tgt.id, relation_type=RelationType.CONOCE
        )
        rel.set_life_span(TemporalSpan.from_years(200, None))  # tras la muerte de src(180)
        codes = _codes(evaluate_relation(rel, source=src, target=tgt))
        assert "T04_RELATION_AFTER_ENDPOINT" in codes

    def test_ok_within_both(self):
        src = _entity("A", 100, 300)
        tgt = _entity("B", 50, 400)
        rel = NarrativeRelation(
            source_id=src.id, target_id=tgt.id, relation_type=RelationType.CONOCE
        )
        rel.set_life_span(TemporalSpan.from_years(150, None))
        codes = _codes(evaluate_relation(rel, source=src, target=tgt))
        assert "T04_RELATION_BEFORE_ENDPOINT" not in codes
        assert "T04_RELATION_AFTER_ENDPOINT" not in codes


# ── Regla 5: evento fuera de la vida del participante ─────────────────────


class TestRule5EventWithinParticipant:
    def _setup(self, participant_birth, participant_death, event_year):
        participant = _entity("Héroe", participant_birth, participant_death)
        event = _entity("Batalla", event_year, etype=EntityType.EVENTO)
        rel = NarrativeRelation(
            source_id=participant.id,
            target_id=event.id,
            relation_type=RelationType.PARTICIPO_EN,
        )
        rel.set_life_span(TemporalSpan.from_years(event_year, None))
        return rel, participant, event

    def test_flags_event_before_birth(self):
        rel, p, e = self._setup(200, 260, 150)
        assert "T05_EVENT_OUTSIDE_PARTICIPANT_LIFE" in _codes(
            evaluate_relation(rel, source=p, target=e)
        )

    def test_ok_event_during_life(self):
        rel, p, e = self._setup(200, 260, 230)
        assert "T05_EVENT_OUTSIDE_PARTICIPANT_LIFE" not in _codes(
            evaluate_relation(rel, source=p, target=e)
        )


# ── Regla 6: contenedor antes que contenido ───────────────────────────────


class TestRule6ParentBeforeChild:
    def test_flags_child_before_container(self):
        parent = _entity("Reino", 100, etype=EntityType.FACCION)
        child = _entity("Provincia", 50, etype=EntityType.LOCALIZACION)
        rel = NarrativeRelation(
            source_id=parent.id, target_id=child.id, relation_type=RelationType.CONTIENE
        )
        rel.set_life_span(TemporalSpan.from_years(100, None))
        assert "T06_CHILD_BEFORE_PARENT" in _codes(
            evaluate_relation(rel, source=parent, target=child)
        )

    def test_respects_direction_pertenece_a(self):
        # PERTENECE_A: source(hijo) -> target(padre)
        child = _entity("Gremio", 50)
        parent = _entity("Ciudad", 100)
        rel = NarrativeRelation(
            source_id=child.id, target_id=parent.id, relation_type=RelationType.PERTENECE_A
        )
        rel.set_life_span(TemporalSpan.from_years(100, None))
        assert "T06_CHILD_BEFORE_PARENT" in _codes(
            evaluate_relation(rel, source=child, target=parent)
        )

    def test_ok_child_after_parent(self):
        parent = _entity("Reino", 100, etype=EntityType.FACCION)
        child = _entity("Provincia", 150, etype=EntityType.LOCALIZACION)
        rel = NarrativeRelation(
            source_id=parent.id, target_id=child.id, relation_type=RelationType.CONTIENE
        )
        rel.set_life_span(TemporalSpan.from_years(150, None))
        assert "T06_CHILD_BEFORE_PARENT" not in _codes(
            evaluate_relation(rel, source=parent, target=child)
        )

    def test_non_container_relation_ignored(self):
        a = _entity("A", 100)
        b = _entity("B", 50)
        rel = NarrativeRelation(
            source_id=a.id, target_id=b.id, relation_type=RelationType.ES_ALIADO_DE
        )
        rel.set_life_span(TemporalSpan.from_years(100, None))
        assert "T06_CHILD_BEFORE_PARENT" not in _codes(evaluate_relation(rel, source=a, target=b))


# ── Regla 7: hito hijo posterior a su padre ───────────────────────────────


class TestRule7MilestoneAfterParent:
    def test_flags_child_before_parent(self):
        parent = CausalMilestone(title="Origen", year=-1000)
        child = CausalMilestone(title="Consecuencia", year=-1200)
        assert "T07_MILESTONE_BEFORE_PARENT" in _codes(
            evaluate_milestone(child, parent_milestones=[parent])
        )

    def test_ok_child_after_parent(self):
        parent = CausalMilestone(title="Origen", year=-1000)
        child = CausalMilestone(title="Consecuencia", year=-800)
        assert "T07_MILESTONE_BEFORE_PARENT" not in _codes(
            evaluate_milestone(child, parent_milestones=[parent])
        )


# ── Robustez: indeterminables no producen falsos positivos ────────────────


class TestRule8And9Nature:
    def test_t08_immortal_with_death(self):
        e = _entity("Ángel", 650, 700)  # tiene muerte
        e.life_span.nature = TemporalNature.INMORTAL
        assert "T08_IMMORTAL_WITH_DEATH" in _codes(evaluate_entity(e))

    def test_t09_eternal_with_finite_birth(self):
        e = _entity("Ángel", 650)  # nacimiento mortal concreto
        e.life_span.nature = TemporalNature.ETERNO
        assert "T09_ETERNAL_WITH_FINITE_BIRTH" in _codes(evaluate_entity(e))

    def test_eternal_without_birth_is_clean(self):
        e = NarrativeEntity(name="Eterno", entity_type=EntityType.CRIATURA)
        e.set_life_span(
            TemporalSpan(start=EventTemporality(year=None), nature=TemporalNature.ETERNO)
        )
        codes = _codes(evaluate_entity(e))
        assert "T09_ETERNAL_WITH_FINITE_BIRTH" not in codes
        assert "T08_IMMORTAL_WITH_DEATH" not in codes


class TestRule4ImmortalExemption:
    def test_relation_after_immortal_endpoint_not_flagged(self):
        # Un inmortal con un end_year heredado no debe disparar 'tras su muerte'.
        immortal = _entity("Deidad", 100, 180)
        immortal.life_span.nature = TemporalNature.INMORTAL
        other = _entity("Mortal", 100)
        rel = NarrativeRelation(
            source_id=immortal.id, target_id=other.id, relation_type=RelationType.CONOCE
        )
        rel.set_life_span(TemporalSpan.from_years(200, None))  # tras 180
        codes = _codes(evaluate_relation(rel, source=immortal, target=other))
        assert "T04_RELATION_AFTER_ENDPOINT" not in codes

    def test_relation_before_eternal_endpoint_not_flagged(self):
        eternal = NarrativeEntity(name="Primordial", entity_type=EntityType.CRIATURA)
        eternal.set_life_span(
            TemporalSpan(start=EventTemporality(year=500), nature=TemporalNature.ETERNO)
        )
        other = _entity("Mortal", 50)
        rel = NarrativeRelation(
            source_id=eternal.id, target_id=other.id, relation_type=RelationType.CONOCE
        )
        rel.set_life_span(TemporalSpan.from_years(100, None))  # antes de 500
        codes = _codes(evaluate_relation(rel, source=eternal, target=other))
        assert "T04_RELATION_BEFORE_ENDPOINT" not in codes


class TestNoFalsePositives:
    def test_unknown_years_skip_all_rules(self):
        e = NarrativeEntity(name="SinDatar")  # birth/death None
        assert evaluate_entity(e, chronology=_chrono(1000)) == []

    def test_to_issue_maps_relation_id(self):
        e = _entity("Paradoja", 100, 50)
        issue = evaluate_entity(e)[0].to_issue()
        assert issue.affected_entity_id == e.id
        assert issue.metadata["code"] == "T01_END_BEFORE_START"
