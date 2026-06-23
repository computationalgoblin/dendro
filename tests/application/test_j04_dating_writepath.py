"""BETA1-J04 — Obligatoriedad en write path de producto + wiring del validador.

Verifica: quitar el default-presente (sin fecha → pendiente), bloqueo con
enforce_dating, y que aceptar un candidato incoherente NO bloquea pero asocia
avisos de coherencia.
"""

from __future__ import annotations

import pytest

from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.result import Error, Ok
from packages.domain.temporal_span import TemporalSpan


@pytest.fixture
def ps():
    svc = ProjectService()
    svc.create("Proyecto J04")
    return svc


# ── Entidad: sin presente falso, enforce bloquea ──────────────────────────


def test_entity_no_silent_present(ps):
    ps.active_project.project_chronology.present_year = 500
    svc = EntityService(ps, ps.store)
    res = svc.create_entity({"name": "A", "entity_type": "personaje"})
    assert isinstance(res, Ok)
    assert res.value.birth_year is None  # NO se inventa 500
    assert res.value.life_span is not None
    assert res.value.life_span.is_dated() is False


def test_entity_enforce_dating(ps):
    svc = EntityService(ps, ps.store)
    undated = svc.create_entity({"name": "B", "entity_type": "personaje"}, enforce_dating=True)
    assert isinstance(undated, Error)
    ok = svc.create_entity(
        {"name": "C", "entity_type": "personaje", "birth_year": 10}, enforce_dating=True
    )
    assert isinstance(ok, Ok) and ok.value.life_span.start_year == 10


def test_entity_life_span_mirror_sync_on_create(ps):
    svc = EntityService(ps, ps.store)
    span = TemporalSpan.from_years(-30, 12)
    res = svc.create_entity(
        {"name": "D", "entity_type": "personaje", "life_span": span.to_dict()}
    )
    assert isinstance(res, Ok)
    # El espejo entero se sincroniza desde el life_span recibido.
    assert res.value.birth_year == -30 and res.value.death_year == 12


# ── Relación: acepta fecha y enforce ──────────────────────────────────────


def test_relation_enforce_dating(ps):
    esvc = EntityService(ps, ps.store)
    a = esvc.create_entity({"name": "S", "entity_type": "personaje", "birth_year": 0}).value
    b = esvc.create_entity({"name": "T", "entity_type": "personaje", "birth_year": 0}).value
    rsvc = RelationService(ps, ps.store)
    blocked = rsvc.create_relation(
        source_id=a.id, target_id=b.id, relation_type="conoce", enforce_dating=True
    )
    assert isinstance(blocked, Error)
    ok = rsvc.create_relation(
        source_id=a.id, target_id=b.id, relation_type="conoce",
        data={"birth_year": 5}, enforce_dating=True,
    )
    assert isinstance(ok, Ok) and ok.value.life_span.start_year == 5


# ── Wiring del validador en aceptación de candidato ───────────────────────


def test_accept_incoherent_candidate_warns_but_not_blocks(ps):
    esvc = EntityService(ps, ps.store)
    rsvc = RelationService(ps, ps.store)
    csvc = CandidateService(project_service=ps, entity_service=esvc, relation_service=rsvc)

    # Dos entidades con vidas disjuntas para forzar T04 al relacionarlas.
    src = esvc.create_entity(
        {"name": "Reciente", "entity_type": "personaje", "birth_year": 200}
    ).value
    tgt = esvc.create_entity(
        {"name": "Antiguo", "entity_type": "personaje", "birth_year": 100}
    ).value

    cand = csvc.create_candidate(
        {
            "candidate_type": "relacion",
            "proposed_data": {
                "source_id": src.id,
                "target_id": tgt.id,
                "relation_type": "conoce",
                "birth_year": 150,  # antes de que nazca 'Reciente' (200) → T04
            },
        }
    )
    assert isinstance(cand, Ok)
    accepted = csvc.accept_candidate(cand.value.id)
    # NO bloquea.
    assert isinstance(accepted, Ok)
    warnings = (accepted.value.metadata or {}).get("temporal_warnings", [])
    assert any(w["code"].startswith("T04") for w in warnings), warnings
