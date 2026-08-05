"""BETA-MULTIAGENT2-FIX-08 (G2-14) — trazabilidad de lo aceptado.

El invariante sagrado se cumple (nada entra al canon sin aceptación humana), pero
una vez dentro el canon no recordaba de dónde vino: el hito aceptado nacía con
`candidate_id: null` y `source_ids: []`, la entidad con `origin: ""`, la relación
con `source: ""`, y el historial del proyecto no registraba ni un solo evento de
aceptación. Estos tests fijan la procedencia en los huecos que YA persisten (sin
migración de esquema) y el evento real `aceptacion_sugerencia`.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.application.source_service import SourceService
from packages.domain.candidate_issue import CandidateState
from packages.domain.result import Error, Ok
from packages.domain.source_history import HistoryEventType, SourceType
from packages.persistence.store import ProjectStore

pytestmark = pytest.mark.application


def _setup(*, with_history: bool = True):
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Trazabilidad")
    es = EntityService(project_service=ps)
    rs = RelationService(project_service=ps)
    svc = CandidateService(
        project_service=ps,
        entity_service=es,
        relation_service=rs,
        history_service=HistoryService(ps) if with_history else None,
        source_service=SourceService(project_service=ps),
    )
    return ps, svc


def _milestone_candidate(svc, title: str = "Matrimonio con Blanca de Borbón"):
    return svc.create_candidate({
        "title": f"Hito sugerido: {title}",
        "candidate_type": "sugerencia_ia",
        "source": "ai_suggest_composite",
        "justification": "Boda documentada en la crónica.",
        "proposed_data": {
            "kind": "causal_milestone",
            "milestone": {"title": title, "description": "Boda real.", "year": 1353},
        },
    }).value


def test_beta_m2fix08_hito_aceptado_guarda_candidate_id_y_fuente():
    ps, svc = _setup()
    c = _milestone_candidate(svc)

    result = svc.accept_candidate(c.id)

    assert not isinstance(result, Error)
    hito = ps.active_project.causal_milestones[0]
    assert hito.candidate_id == c.id
    assert hito.source_ids, "el hito aceptado debe llevar la fuente de su semilla"
    fuentes = {s.id: s for s in ps.active_project.sources}
    fuente = fuentes[hito.source_ids[0]]
    assert fuente.source_type == SourceType.SUGERENCIA_IA_ACEPTADA
    assert fuente.metadata.get("candidate_id") == c.id


def test_beta_m2fix08_entidad_aceptada_guarda_origen():
    ps, svc = _setup()
    c = svc.create_candidate({
        "title": "Hoja candidata: Alburquerque",
        "candidate_type": "entidad",
        "source": "ai_suggest_composite",
        "proposed_data": {"name": "Alburquerque", "entity_type": "personaje"},
    }).value

    result = svc.accept_candidate(c.id)

    assert not isinstance(result, Error)
    entidad = ps.active_project.entities[0]
    assert entidad.origin == SourceType.SUGERENCIA_IA_ACEPTADA.value
    assert entidad.custom_metadata.get("candidate_id") == c.id
    fuente = ps.active_project.sources[0]
    assert fuente.source_type == SourceType.SUGERENCIA_IA_ACEPTADA
    assert entidad.id in fuente.derived_entity_ids


def test_beta_m2fix08_relacion_aceptada_guarda_origen():
    ps, svc = _setup()
    es = svc.entity_service
    a = es.create_entity({"name": "Pedro I", "entity_type": "personaje"}).value
    b = es.create_entity({"name": "Blanca de Borbón", "entity_type": "personaje"}).value
    c = svc.create_candidate({
        "title": "Relación candidata",
        "candidate_type": "relacion",
        "source": "ai_suggest_composite",
        "proposed_data": {
            "source_id": a.id, "target_id": b.id,
            "relation_type": "esta_relacionado_con", "description": "Matrimonio.",
        },
    }).value

    result = svc.accept_candidate(c.id)

    assert not isinstance(result, Error)
    relacion = ps.active_project.relations[0]
    assert relacion.source == SourceType.SUGERENCIA_IA_ACEPTADA.value
    assert relacion.custom_metadata.get("candidate_id") == c.id
    fuente = ps.active_project.sources[0]
    assert relacion.id in fuente.derived_relation_ids


def test_beta_m2fix08_aceptar_registra_evento_aceptacion_sugerencia():
    ps, svc = _setup()
    c = _milestone_candidate(svc)

    assert not isinstance(svc.accept_candidate(c.id), Error)

    eventos = list(ps.active_project.history)
    tipos = [e.event_type for e in eventos]
    assert HistoryEventType.ACEPTACION_SUGERENCIA in tipos
    # …y ni un solo `creacion_entidad` falso por esta vía (el literal desconocido
    # se degradaba en silencio a ese evento).
    assert HistoryEventType.CREACION_ENTIDAD not in tipos
    aceptacion = next(
        e for e in eventos if e.event_type == HistoryEventType.ACEPTACION_SUGERENCIA
    )
    assert aceptacion.metadata.get("candidate_id") == c.id


def test_beta_m2fix08_history_service_expone_add_entry_real():
    """Criterio 4: `add_entry` tenía 4 llamadores y 0 implementaciones."""
    ps, _ = _setup()
    hs = HistoryService(ps)

    assert callable(getattr(hs, "add_entry", None))
    hs.add_entry(HistoryEventType.ACEPTACION_SUGERENCIA, "prueba de alias real")
    assert [e.event_type for e in ps.active_project.history] == [
        HistoryEventType.ACEPTACION_SUGERENCIA
    ]
    # Un tipo fuera del enum ya no se degrada EN SILENCIO: deja constancia.
    hs.add_entry("evento_inexistente", "algo raro")
    assert ps.active_project.history[-1].metadata.get("event_type_declarado") == (
        "evento_inexistente"
    )


def test_beta_m2fix08_aceptar_sin_history_service_sigue_devolviendo_ok():
    ps, svc = _setup(with_history=False)
    c = _milestone_candidate(svc)

    result = svc.accept_candidate(c.id)

    assert isinstance(result, Ok)
    assert c.state == CandidateState.ACEPTADO
    assert len(ps.active_project.causal_milestones) == 1
    assert ps.active_project.causal_milestones[0].candidate_id == c.id
    assert not ps.active_project.history


def test_beta_m2fix08_aceptar_sin_source_service_no_rompe_el_accept():
    """La trazabilidad nunca convierte un accept correcto en Error."""
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Sin fuentes")

    class _FuentesRotas:
        def create_source(self, data):
            return Error("almacén de fuentes no disponible")

    svc = CandidateService(
        project_service=ps,
        entity_service=EntityService(project_service=ps),
        relation_service=RelationService(project_service=ps),
        source_service=_FuentesRotas(),
    )
    c = _milestone_candidate(svc)

    result = svc.accept_candidate(c.id)

    assert isinstance(result, Ok)
    assert ps.active_project.causal_milestones[0].candidate_id == c.id
    assert not ps.active_project.sources
    assert c.metadata.get("provenance_error")


def test_beta_m2fix08_round_trip_conserva_trazabilidad():
    ps, svc = _setup()
    hito_cand = _milestone_candidate(svc)
    entidad_cand = svc.create_candidate({
        "title": "Hoja candidata: Cuéllar",
        "candidate_type": "entidad",
        "source": "ai_suggest_composite",
        "proposed_data": {"name": "Cuéllar", "entity_type": "localizacion"},
    }).value
    assert not isinstance(svc.accept_candidate(hito_cand.id), Error)
    assert not isinstance(svc.accept_candidate(entidad_cand.id), Error)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mundo.json"
        store = ProjectStore()
        assert not isinstance(store.save(ps.active_project, path), Error)
        loaded = store.load(path)
        assert not isinstance(loaded, Error)
        proyecto = loaded.value

    hito = proyecto.causal_milestones[0]
    assert hito.candidate_id == hito_cand.id
    assert hito.source_ids
    tipos = {s.id: s.source_type for s in proyecto.sources}
    assert tipos[hito.source_ids[0]] == SourceType.SUGERENCIA_IA_ACEPTADA
    entidad = next(e for e in proyecto.entities if e.name == "Cuéllar")
    assert entidad.origin == SourceType.SUGERENCIA_IA_ACEPTADA.value
    assert any(entidad.id in s.derived_entity_ids for s in proyecto.sources)
    assert any(
        e.event_type == HistoryEventType.ACEPTACION_SUGERENCIA for e in proyecto.history
    )
