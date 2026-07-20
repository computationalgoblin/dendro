"""CRON — aplicación atómica del paso resuelta por ID.

Verifica el arreglo de la referencia colgante: aceptar los cambios de un paso
como bloque ordenado (creaciones → relaciones → ediciones) resolviendo extremos
por ID, de modo que una relación nunca quede apuntando a un nombre inexistente.
"""

from __future__ import annotations

import pytest

from packages.application.candidate_service import CandidateService
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.chronology_walk_service import ChronologyWalkService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.result import Error, Ok


def _setup():
    ps = ProjectService()
    assert isinstance(ps.create("CRON apply"), Ok)
    es = EntityService(ps)
    rs = RelationService(ps)
    cs = CandidateService(project_service=ps, entity_service=es, relation_service=rs)
    devian = es.create_entity({"name": "Devian", "entity_type": "personaje"}).value
    hito = (
        CausalMilestoneService(project_service=ps, candidate_service=cs)
        .create_hito_manual({"title": "La Purga", "year": -30, "affected_entity_ids": [devian.id]})
        .value
    )
    svc = ChronologyWalkService(project_service=ps, ai_job_service=None, candidate_service=cs)
    session = svc.start_walk(hito.id).value
    return ps, es, cs, svc, session, devian


@pytest.mark.application
def test_apply_step_creates_entity_before_relation_referencing_it():
    ps, es, cs, svc, session, devian = _setup()
    # El paso propone una entidad NUEVA (Akshan) y una relación Devian→Akshan.
    ent_cand = cs.create_candidate(
        {
            "candidate_type": "entidad",
            "proposed_data": {"name": "Akshan", "entity_type": "personaje"},
        }
    ).value
    rel_cand = cs.create_candidate(
        {
            "candidate_type": "relacion",
            "proposed_data": {
                "source_name": "Devian",
                "target_name": "Akshan",
                "relation_type": "sirve_a",
                "description": "Devian sirve a Akshan.",
            },
        }
    ).value

    # Se pasan en orden INVERSO a propósito: el servicio debe reordenar.
    res = svc.apply_step(
        session.id,
        [{"candidate_id": rel_cand.id}, {"candidate_id": ent_cand.id}],
    )

    assert isinstance(res, Ok)
    assert res.value["failed"] == []
    assert set(res.value["applied"]) == {ent_cand.id, rel_cand.id}
    project = ps.active_project
    names = {str(e.name) for e in project.entities}
    assert "Akshan" in names  # la entidad nueva se creó
    akshan = next(e for e in project.entities if e.name == "Akshan")
    # La relación apunta a IDs reales (no a un nombre colgante).
    rel = next((r for r in project.relations), None)
    assert rel is not None
    assert {rel.source_id, rel.target_id} == {devian.id, akshan.id}


@pytest.mark.application
def test_apply_step_relation_before_rename_keeps_reference_valid():
    ps, es, cs, svc, session, devian = _setup()
    akshan = es.create_entity({"name": "Akshan", "entity_type": "personaje"}).value
    # Relación Devian→Akshan + renombrado del título del hito (edición) en el mismo paso.
    rel_cand = cs.create_candidate(
        {
            "candidate_type": "relacion",
            "proposed_data": {
                "source_name": "Devian",
                "target_name": "Akshan",
                "relation_type": "sirve_a",
            },
        }
    ).value
    edit_cand = cs.create_candidate(
        {
            "candidate_type": "sugerencia_ia",
            "proposed_data": {
                "edit_kind": "milestone_edits",
                "edit_target_name": "La Purga",
                "edit_field": "title",
                "edit_proposed_value": "La Gran Purga",
            },
        }
    ).value

    res = svc.apply_step(
        session.id,
        [{"candidate_id": edit_cand.id}, {"candidate_id": rel_cand.id}],
    )

    assert isinstance(res, Ok)
    assert res.value["failed"] == []
    project = ps.active_project
    rel = next((r for r in project.relations), None)
    assert rel is not None
    assert {rel.source_id, rel.target_id} == {devian.id, akshan.id}
    assert any(getattr(m, "title", "") == "La Gran Purga" for m in project.causal_milestones)


@pytest.mark.application
def test_apply_step_renames_placeholder_milestone_by_id_then_edits_body():
    """Caso del bug: un hito marcador («nuevo hito») recibe DOS ediciones en el
    mismo paso — renombrar el título y rellenar el cuerpo. Resueltas por id, ambas
    recaen sobre el MISMO hito aunque el título cambie a mitad del bloque."""
    ps, es, cs, svc, session, devian = _setup()
    placeholder = (
        CausalMilestoneService(project_service=ps, candidate_service=cs)
        .create_hito_manual({"title": "nuevo hito", "year": 33})
        .value
    )
    rename = cs.create_candidate(
        {
            "candidate_type": "sugerencia_ia",
            "proposed_data": {
                "edit_kind": "milestone_edits",
                "edit_target_id": placeholder.id,
                "edit_target_name": "nuevo hito",
                "edit_field": "title",
                "edit_proposed_value": "El Juramento de Devian",
            },
        }
    ).value
    body = cs.create_candidate(
        {
            "candidate_type": "sugerencia_ia",
            "proposed_data": {
                "edit_kind": "milestone_edits",
                "edit_target_id": placeholder.id,
                "edit_target_name": "nuevo hito",
                "edit_field": "description",
                "edit_proposed_value": "Devian jura lealtad tras la Purga.",
            },
        }
    ).value

    res = svc.apply_step(
        session.id,
        [{"candidate_id": rename.id}, {"candidate_id": body.id}],
    )

    assert isinstance(res, Ok)
    assert res.value["failed"] == []  # la 2ª edición NO falla por el renombrado
    hito = next(m for m in ps.active_project.causal_milestones if m.id == placeholder.id)
    assert hito.title == "El Juramento de Devian"
    assert hito.description == "Devian jura lealtad tras la Purga."
    # No se creó un hito duplicado en otro año.
    assert sum(1 for m in ps.active_project.causal_milestones if m.year == 33) == 1


@pytest.mark.application
def test_apply_step_honours_user_edits_to_proposed_data():
    ps, es, cs, svc, session, devian = _setup()
    ent_cand = cs.create_candidate(
        {
            "candidate_type": "entidad",
            "proposed_data": {"name": "Borrador", "entity_type": "personaje"},
        }
    ).value

    res = svc.apply_step(
        session.id,
        [{"candidate_id": ent_cand.id, "edited_data": {"name": "Akshan el Justo"}}],
    )

    assert isinstance(res, Ok)
    assert res.value["failed"] == []
    names = {str(e.name) for e in ps.active_project.entities}
    assert "Akshan el Justo" in names
    assert "Borrador" not in names


@pytest.mark.application
def test_apply_step_reports_unresolvable_relation_as_failed():
    ps, es, cs, svc, session, devian = _setup()
    rel_cand = cs.create_candidate(
        {
            "candidate_type": "relacion",
            "proposed_data": {
                "source_name": "Devian",
                "target_name": "NoExiste",
                "relation_type": "sirve_a",
            },
        }
    ).value

    res = svc.apply_step(session.id, [{"candidate_id": rel_cand.id}])

    assert isinstance(res, Ok)
    assert res.value["applied"] == []
    assert len(res.value["failed"]) == 1
    assert res.value["failed"][0]["candidate_id"] == rel_cand.id
    # No se creó ninguna relación colgante.
    assert list(ps.active_project.relations) == []


@pytest.mark.application
def test_apply_step_resolves_open_problem_and_unblocks_advance():
    from packages.domain.chronology_walk import WalkStatus

    ps, es, cs, svc, session, devian = _setup()
    # Simula una parada dura: problema abierto sobre el hito actual + sesión en pausa.
    session.status = WalkStatus.PAUSED
    session.open_problems.append(
        {
            "id": "p1",
            "milestone_id": session.current_milestone_id,
            "kind": "motivation_incompatibility",
            "severity": "alta",
            "resolved": False,
        }
    )
    # Avanzar está bloqueado mientras el problema siga sin resolver.
    assert isinstance(svc.advance(session.id), Error)

    ent_cand = cs.create_candidate(
        {
            "candidate_type": "entidad",
            "proposed_data": {"name": "Akshan", "entity_type": "personaje"},
        }
    ).value
    res = svc.apply_step(session.id, [{"candidate_id": ent_cand.id}])

    assert isinstance(res, Ok)
    assert all(p["resolved"] for p in session.open_problems)
    assert session.status is WalkStatus.ACTIVE
    # Ahora sí avanza (hay un hito siguiente porque advance refused antes solo por el problema...
    # aquí h1 es el único; avanzar hacia el futuro completa el recorrido sin error).
    adv = svc.advance(session.id)
    assert isinstance(adv, Ok)


@pytest.mark.application
def test_apply_step_multi_field_patch_with_user_edits():
    """PLAY-15/17: patch `edit_fields` atómico; `edited_data` trae el dict COMPLETO.

    El merge de apply_step sobre proposed_data es shallow: quien revisa en el
    preview debe emitir el `edit_fields` entero ya fusionado, no un parcial.
    """
    ps, _es, cs, svc, session, devian = _setup()
    edit_cand = cs.create_candidate(
        {
            "candidate_type": "sugerencia_ia",
            "proposed_data": {
                "edit_kind": "entity_edits",
                "edit_target_name": "Devian",
                "edit_fields": {"brief_description": "Propuesta de la IA.", "birth_year": -120},
            },
        }
    ).value

    res = svc.apply_step(
        session.id,
        [
            {
                "candidate_id": edit_cand.id,
                "edited_data": {
                    "edit_fields": {
                        "brief_description": "Versión retocada por el usuario.",
                        "birth_year": -120,
                    }
                },
            }
        ],
    )

    assert isinstance(res, Ok)
    assert res.value["failed"] == []
    updated = next(e for e in ps.active_project.entities if e.id == devian.id)
    assert updated.brief_description == "Versión retocada por el usuario."
    assert updated.birth_year == -120
