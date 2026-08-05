"""BETA1-J02 — Validador determinista de coherencia temporal.

Una clase por regla, con caso positivo (incoherente → aviso) y negativo
(coherente o indeterminable → sin aviso).
"""

from __future__ import annotations

from packages.application.temporal_coherence import (
    evaluate_bilocation,
    evaluate_dating_sync,
    evaluate_entity,
    evaluate_knowledge,
    evaluate_milestone,
    evaluate_milestone_participants,
    evaluate_relation,
)
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneType
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


# ══════════════════════════════════════════════════════════════════════════
# Reglas de CONTINUIDAD — BETA-MULTIAGENT2-FIX-10 (G2-15)
#
# Las tres roturas de sala de guion que el modelo ya podía computar y que nadie
# miraba, más el aviso que explica el ruido de calendario.
# ══════════════════════════════════════════════════════════════════════════


def _hito(title, year, participantes=(), mtype=CausalMilestoneType.OTRO):
    return CausalMilestone(
        title=title,
        year=year,
        milestone_type=mtype,
        affected_entity_ids=[e.id for e in participantes],
    )


def _indice(*entidades):
    return {e.id: e for e in entidades}


# ── Regla 10: bilocación ──────────────────────────────────────────────────


class TestT10Bilocacion:
    def _reparto(self):
        nadia = _entity("Nadia Kerr", 1)
        enfermeria = _entity("Enfermería", 0, etype=EntityType.LOCALIZACION)
        cubierta = _entity("Cubierta 9", 0, etype=EntityType.LOCALIZACION)
        return nadia, enfermeria, cubierta

    def test_beta_m2fix10_dos_lugares_disjuntos_el_mismo_ano(self):
        nadia, enfermeria, cubierta = self._reparto()
        hitos = [
            _hito("1x06 — Trigo", 44, (nadia, enfermeria)),
            _hito("1x06b — Cubierta 9", 44, (nadia, cubierta)),
        ]
        issues = evaluate_bilocation(hitos, _indice(nadia, enfermeria, cubierta))
        assert _codes(issues) == {"T10_BILOCATION"}
        assert "Nadia Kerr" in issues[0].message and "44" in issues[0].message

    def test_beta_m2fix10_mismo_lugar_no_es_bilocacion(self):
        nadia, enfermeria, _ = self._reparto()
        hitos = [
            _hito("1x06 — Trigo", 44, (nadia, enfermeria)),
            _hito("1x06b — Otra escena", 44, (nadia, enfermeria)),
        ]
        assert evaluate_bilocation(hitos, _indice(nadia, enfermeria)) == []

    def test_beta_m2fix10_sin_lugar_declarado_se_calla(self):
        """Silencio honesto: si el hito no dice dónde pasa, no se inventa."""
        nadia, _, cubierta = self._reparto()
        hitos = [
            _hito("1x06 — Trigo", 44, (nadia,)),  # sin localización
            _hito("1x06b — Cubierta 9", 44, (nadia, cubierta)),
        ]
        assert evaluate_bilocation(hitos, _indice(nadia, cubierta)) == []

    def test_beta_m2fix10_anos_distintos_no_es_bilocacion(self):
        nadia, enfermeria, cubierta = self._reparto()
        hitos = [
            _hito("1x06 — Trigo", 44, (nadia, enfermeria)),
            _hito("1x07 — Cubierta 9", 45, (nadia, cubierta)),
        ]
        assert evaluate_bilocation(hitos, _indice(nadia, enfermeria, cubierta)) == []

    def test_beta_m2fix10_una_faccion_puede_estar_en_dos_sitios(self):
        """Una facción o una institución están repartidas por definición."""
        gremio = _entity("Gremio de la Ceniza", 1, etype=EntityType.FACCION)
        enfermeria = _entity("Enfermería", 0, etype=EntityType.LOCALIZACION)
        cubierta = _entity("Cubierta 9", 0, etype=EntityType.LOCALIZACION)
        hitos = [
            _hito("Reunión", 44, (gremio, enfermeria)),
            _hito("Asalto", 44, (gremio, cubierta)),
        ]
        assert evaluate_bilocation(hitos, _indice(gremio, enfermeria, cubierta)) == []


# ── Regla 11: participante de un HITO fuera de su lapso ───────────────────


class TestT11ParticipanteFueraDeVida:
    def test_beta_m2fix10_muerto_que_reaparece(self):
        teo = _entity("Teodor «Teo» Kerr", 1, 1)
        hito = _hito("2x08 — Habitable", 16, (teo,))
        issues = evaluate_milestone_participants(hito, [teo])
        assert _codes(issues) == {"T11_PARTICIPANT_OUTSIDE_LIFE"}
        assert issues[0].severity == "alta"
        assert issues[0].related_ids == [teo.id]

    def test_beta_m2fix10_participante_vivo_no_avisa(self):
        nadia = _entity("Nadia Kerr", 1)
        hito = _hito("2x08 — Habitable", 16, (nadia,))
        assert evaluate_milestone_participants(hito, [nadia]) == []

    def test_beta_m2fix10_inmortal_exento(self):
        """BETA1-J07: un inmortal no deja de existir, así que no hay «después»."""
        dios = _entity("El Vigía", 1, 1)
        dios.life_span.nature = TemporalNature.INMORTAL
        hito = _hito("Dentro de mil años", 1000, (dios,))
        assert evaluate_milestone_participants(hito, [dios]) == []

    def test_beta_m2fix10_hito_sin_ano_no_se_juzga(self):
        teo = _entity("Teo", 1, 1)
        assert evaluate_milestone_participants(_hito("Sin datar", None, (teo,)), [teo]) == []

    def test_beta_m2fix10_manda_el_espejo_entero_no_el_lapso_rancio(self):
        """Datación desincronizada: la Ficha dice muerte en 1, el lapso dice 0.

        Con el lapso rancio saltaba un aviso que contradecía a la propia Ficha
        (mundo de Aitor, remapeado fuera de los servicios).
        """
        teo = _entity("Teo", 1, 1)
        teo.life_span.end.year = 0  # el lapso se queda atrás; el espejo manda
        assert evaluate_milestone_participants(_hito("1x01", 1, (teo,)), [teo]) == []
        assert _codes(evaluate_milestone_participants(_hito("2x08", 16, (teo,)), [teo])) == {
            "T11_PARTICIPANT_OUTSIDE_LIFE"
        }


# ── Reglas 12 y 13: conocimiento ──────────────────────────────────────────


def _saber(source, target, rtype, birth=None):
    rel = NarrativeRelation(
        source_id=source.id, target_id=target.id, relation_type=rtype
    )
    if birth is not None:
        rel.set_life_span(TemporalSpan.from_years(birth, None))
    return rel


class TestT12T13Conocimiento:
    def _pareja(self):
        nadia = _entity("Nadia Kerr", 1)
        mentira = _entity("La Tierra es habitable", -1, etype=EntityType.REGLA_DEL_MUNDO)
        return nadia, mentira

    def test_beta_m2fix10_sabe_e_ignora_a_la_vez(self):
        nadia, mentira = self._pareja()
        rels = [
            _saber(nadia, mentira, RelationType.SABE),
            _saber(nadia, mentira, RelationType.IGNORA),
        ]
        issues = evaluate_knowledge(rels, entities=_indice(nadia, mentira))
        assert _codes(issues) == {"T12_KNOWS_AND_IGNORES"}
        assert "Nadia Kerr" in issues[0].message

    def test_beta_m2fix10_arco_de_personaje_no_es_contradiccion(self):
        """Ignoraba hasta el 10 y lo sabe desde el 11: eso es la serie, no un fallo."""
        nadia, mentira = self._pareja()
        ignora = _saber(nadia, mentira, RelationType.IGNORA)
        ignora.set_life_span(TemporalSpan.from_years(1, 10))
        rels = [ignora, _saber(nadia, mentira, RelationType.SABE, birth=11)]
        assert evaluate_knowledge(rels, entities=_indice(nadia, mentira)) == []

    def test_beta_m2fix10_sospechar_no_contradice_ignorar(self):
        nadia, mentira = self._pareja()
        rels = [
            _saber(nadia, mentira, RelationType.SOSPECHA),
            _saber(nadia, mentira, RelationType.IGNORA),
        ]
        assert evaluate_knowledge(rels, entities=_indice(nadia, mentira)) == []

    def test_beta_m2fix10_sin_datar_no_hay_t13(self):
        """Las siete relaciones de conocimiento del mundo entregado tienen
        `birth_year` a None: la regla se calla en vez de adivinar."""
        nadia, mentira = self._pareja()
        rels = [_saber(nadia, mentira, RelationType.SABE)]
        hitos = [_hito("2x03", 11, (mentira,), mtype=CausalMilestoneType.REVELACION)]
        assert "T13_KNOWS_BEFORE_REVELATION" not in _codes(
            evaluate_knowledge(rels, entities=_indice(nadia, mentira), milestones=hitos)
        )

    def test_beta_m2fix10_sabe_antes_de_que_se_revele(self):
        nadia, mentira = self._pareja()
        rels = [_saber(nadia, mentira, RelationType.SABE, birth=5)]
        hitos = [
            _hito("2x03 — Lo que dijo el Meridiano", 11, (mentira,),
                  mtype=CausalMilestoneType.REVELACION)
        ]
        issues = evaluate_knowledge(rels, entities=_indice(nadia, mentira), milestones=hitos)
        assert _codes(issues) == {"T13_KNOWS_BEFORE_REVELATION"}
        assert "2x03" in issues[0].message

    def test_beta_m2fix10_saber_despues_de_la_revelacion_es_normal(self):
        nadia, mentira = self._pareja()
        rels = [_saber(nadia, mentira, RelationType.SABE, birth=12)]
        hitos = [_hito("2x03", 11, (mentira,), mtype=CausalMilestoneType.REVELACION)]
        assert evaluate_knowledge(rels, entities=_indice(nadia, mentira), milestones=hitos) == []


# ── Regla 14: datación desincronizada ─────────────────────────────────────


class TestT14DatacionDesincronizada:
    def test_beta_m2fix10_espejo_y_lapso_discrepan(self):
        nadia = _entity("Nadia Kerr", 1)
        nadia.life_span.start.year = -9855  # escala vieja: el mundo de Aitor
        issues = evaluate_dating_sync(nadia)
        assert _codes(issues) == {"T14_DATING_DESYNC"}
        assert "-9855" in issues[0].message

    def test_beta_m2fix10_sincronizada_no_avisa(self):
        assert evaluate_dating_sync(_entity("Nadia", 1, 8)) == []

    def test_beta_m2fix10_sin_lapso_no_puede_discrepar(self):
        e = NarrativeEntity(name="Sin lapso")
        e.birth_year = 3
        assert evaluate_dating_sync(e) == []
