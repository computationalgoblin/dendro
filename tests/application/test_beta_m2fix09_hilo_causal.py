"""BETA-MULTIAGENT2-FIX-09 (G2-15): el hilo causal setup→payoff.

El mundo del beta (`guionista-serie`, 20 hitos y 21 enlaces de paternidad) dejó
tres cosas medidas: `causal_child_hito_ids` no lo escribía NADIE, recorrer la
cadena devolvía UN elemento y «plantado sin recoger» devolvía 20 de 20 porque
medía `caused_relation_ids`. Aquí se fija el contrato nuevo.
"""

from __future__ import annotations

import pytest

from packages.application import causal_links
from packages.application.candidate_service import CandidateService
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.project_service import ProjectService
from packages.application.status_quo_explainer import explain_status_quo
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


def _setup():
    ps = ProjectService(ProjectStore())
    ps.create(name="FIX-09")
    cs = CandidateService(ps)
    return ps, CausalMilestoneService(ps, candidate_service=cs), cs


def _hijos(service, hito_id: str) -> list[str]:
    result = service.list_causal_children(hito_id)
    assert isinstance(result, Ok)
    return [h.id for h in result.value]


@pytest.mark.application
def test_beta_m2fix09_reciprocidad_en_las_cuatro_rutas():
    """Las CUATRO rutas que meten un hito con padres dejan al padre enterado."""
    ps, service, cs = _setup()
    raiz = service.create_hito_manual({"id": "h_raiz", "title": "Setup", "year": 1}).value

    # 1) create_hito_manual
    manual = service.create_hito_manual(
        {"title": "Payoff manual", "year": 2, "causal_parent_hito_ids": ["h_raiz"]}
    )
    assert isinstance(manual, Ok)

    # 2) approve_hito desde candidato
    candidato = service.create_hito_candidate(
        {"title": "Payoff aprobado", "year": 3, "causal_parent_hito_ids": ["h_raiz"]}
    )
    assert isinstance(candidato, Ok)
    aprobado = service.approve_hito(candidato.value.id)
    assert isinstance(aprobado, Ok)

    # 3) CandidateService.accept_candidate de un candidato causal_milestone
    semilla = service.create_hito_candidate(
        {"title": "Payoff aceptado", "year": 4, "causal_parent_hito_ids": ["h_raiz"]}
    )
    assert isinstance(semilla, Ok)
    assert isinstance(cs.accept_candidate(semilla.value.id), Ok)

    # 4) update_hito con causal_parent_hito_ids
    huerfano = service.create_hito_manual({"title": "Payoff editado", "year": 5}).value
    assert isinstance(
        service.update_hito(huerfano.id, {"causal_parent_hito_ids": ["h_raiz"]}), Ok
    )

    hijos = _hijos(service, "h_raiz")
    titulos = {
        h.title
        for h in ps.active_project.causal_milestones
        if h.id in hijos
    }
    assert titulos == {
        "Payoff manual",
        "Payoff aprobado",
        "Payoff aceptado",
        "Payoff editado",
    }
    # y el espejo en disco también lo sabe (lo escribe un único punto)
    assert sorted(raiz.causal_child_hito_ids) == sorted(hijos)


@pytest.mark.application
def test_beta_m2fix09_simetria_al_deshacer():
    """Quitar el padre o borrar el hijo no deja punteros muertos; sin duplicados."""
    ps, service, _ = _setup()
    padre = service.create_hito_manual({"title": "Planta", "year": 1}).value
    hijo = service.create_hito_manual({"title": "Recoge", "year": 2}).value

    assert isinstance(service.link_causal(hijo.id, padre.id), Ok)
    # declarar dos veces no duplica
    assert isinstance(service.link_causal(hijo.id, padre.id), Ok)
    assert hijo.causal_parent_hito_ids == [padre.id]
    assert padre.causal_child_hito_ids == [hijo.id]

    # deshacer por el servicio: los dos lados limpios
    assert isinstance(service.unlink_causal(hijo.id, padre.id), Ok)
    assert hijo.causal_parent_hito_ids == []
    assert padre.causal_child_hito_ids == []
    assert _hijos(service, padre.id) == []

    # y la reconciliación no lo resucita desde el espejo rancio
    assert causal_links.reconcile_causal_links(ps.active_project) is False
    assert _hijos(service, padre.id) == []

    # borrar el hijo tampoco deja punteros muertos en el padre
    assert isinstance(service.link_causal(hijo.id, padre.id), Ok)
    assert isinstance(service.delete_hito(hijo.id), Ok)
    assert padre.causal_child_hito_ids == []
    assert _hijos(service, padre.id) == []

    # quitar el padre por update_hito (payload parcial) es igual de simétrico
    otro = service.create_hito_manual({"title": "Otro", "year": 3}).value
    assert isinstance(service.link_causal(otro.id, padre.id), Ok)
    assert isinstance(service.update_hito(otro.id, {"causal_parent_hito_ids": []}), Ok)
    assert padre.causal_child_hito_ids == []


@pytest.mark.application
def test_beta_m2fix09_no_admite_autoenlace_ni_ciclos():
    ps, service, _ = _setup()
    a = service.create_hito_manual({"title": "A", "year": 1}).value
    b = service.create_hito_manual({"title": "B", "year": 2}).value
    assert isinstance(service.link_causal(a.id, a.id), Error)
    assert isinstance(service.link_causal(b.id, a.id), Ok)
    # A no puede colgar de B: el hilo daría una vuelta
    assert isinstance(service.link_causal(a.id, b.id), Error)


@pytest.mark.application
def test_beta_m2fix09_cadena_en_orden_cronologico():
    """La cadena sale ordenada por año, no en anchura."""
    ps, service, _ = _setup()
    setup = service.create_hito_manual({"id": "s", "title": "1x03", "year": 3}).value
    service.create_hito_manual(
        {"id": "b1", "title": "1x04", "year": 4, "causal_parent_hito_ids": ["s"]}
    )
    # rama tardía colgada del setup: en anchura saldría ANTES que el nieto de 1x04
    service.create_hito_manual(
        {"id": "b2", "title": "2x03", "year": 20, "causal_parent_hito_ids": ["s"]}
    )
    service.create_hito_manual(
        {"id": "n1", "title": "1x05", "year": 5, "causal_parent_hito_ids": ["b1"]}
    )

    chain = service.list_causal_chain(setup.id)
    assert isinstance(chain, Ok)
    assert [h.title for h in chain.value] == ["1x03", "1x04", "1x05", "2x03"]


@pytest.mark.application
def test_beta_m2fix09_cadena_tolera_ciclos_declarados_a_mano():
    ps, service, _ = _setup()
    a = service.create_hito_manual({"id": "a", "title": "A", "year": 1}).value
    b = service.create_hito_manual(
        {"id": "b", "title": "B", "year": 2, "causal_parent_hito_ids": ["a"]}
    ).value
    # ciclo introducido a mano (no por el servicio, que lo rechaza)
    a.causal_parent_hito_ids = [b.id]
    chain = service.list_causal_chain(a.id)
    assert isinstance(chain, Ok)
    assert [h.id for h in chain.value] == ["a", "b"]


@pytest.mark.application
def test_beta_m2fix09_hilos_sueltos_mide_hijos():
    """El setup CON payoff no se lista; el que no lo tiene, sí. Y las
    `caused_relation_ids` no cambian el resultado (medían otra cosa)."""
    ps, service, _ = _setup()
    con_payoff = service.create_hito_manual({"id": "p", "title": "Planta", "year": 1}).value
    payoff = service.create_hito_manual(
        {"id": "r", "title": "Recoge", "year": 2, "causal_parent_hito_ids": ["p"]}
    ).value
    sin_payoff = service.create_hito_manual({"title": "Plantado y olvidado", "year": 3}).value

    sueltos = service.find_hitos_without_consequences()
    assert isinstance(sueltos, Ok)
    ids = [h.id for h in sueltos.value]
    assert con_payoff.id not in ids
    assert payoff.id in ids and sin_payoff.id in ids

    # tener o no relaciones causadas es irrelevante para el hilo narrativo
    con_payoff.caused_relation_ids = ["rel_1"]
    sin_payoff.caused_relation_ids = ["rel_2"]
    otra_vez = service.find_hitos_without_consequences()
    assert [h.id for h in otra_vez.value] == ids


@pytest.mark.application
def test_beta_m2fix09_hilos_sueltos_excluye_hitos_marco():
    """Un hito-marco (TEMPORADA 1) es contención temporal, no un setup."""
    ps, service, _ = _setup()
    marco = service.create_hito_manual({"title": "TEMPORADA 1", "year": 1}).value
    episodio = service.create_subhito(marco.id, {"title": "1x01", "year": 1})
    assert isinstance(episodio, Ok)

    sueltos = service.find_hitos_without_consequences()
    ids = [h.id for h in sueltos.value]
    assert marco.id not in ids
    assert episodio.value.id in ids


@pytest.mark.application
def test_beta_m2fix09_status_quo_usa_la_misma_consulta():
    ps, service, _ = _setup()
    service.create_hito_manual({"id": "p", "title": "Planta", "year": 1})
    service.create_hito_manual(
        {"title": "Recoge", "year": 2, "causal_parent_hito_ids": ["p"]}
    )
    service.create_hito_manual({"title": "Suelto", "year": 3})

    reporte = explain_status_quo(ps.active_project)
    del_servicio = service.find_hitos_without_consequences()
    assert isinstance(del_servicio, Ok)
    assert reporte["hitos_without_consequences"] == len(del_servicio.value) == 2


@pytest.mark.application
def test_beta_m2fix09_reviewer_no_avisa_de_causalidad_debil_con_consecuencias():
    """«Causalidad débil» se disparaba SIEMPRE (leía el campo que nadie escribía)."""
    from packages.application.causal_milestone_reviewer import review_causal_milestone

    ps, service, _ = _setup()
    padre = service.create_hito_manual({"id": "p", "title": "Guerra", "year": 1}).value
    service.create_hito_manual(
        {"title": "Tratado", "year": 2, "causal_parent_hito_ids": ["p"]}
    )

    etiquetas = [f.label for f in review_causal_milestone(padre, ps.active_project)]
    assert "Causalidad débil" not in etiquetas


@pytest.mark.application
def test_beta_m2fix09_proyecto_v40_con_solo_padres_ensena_la_cadena_al_abrir():
    """Criterio 8: sin migración — la lectura deriva del lado padre.

    Se simula un proyecto ya guardado (v40) cuyos hitos traen SOLO
    `causal_parent_hito_ids`, que es exactamente lo que hay en los 8 mundos del
    beta, y se comprueba que la cadena sale completa sin reparar nada.
    """
    ps, service, _ = _setup()
    for i, (hid, padre) in enumerate(
        [("h1", None), ("h2", "h1"), ("h3", "h2"), ("h4", "h3")]
    ):
        data = {"id": hid, "title": f"Episodio {i}", "year": i}
        if padre:
            data["causal_parent_hito_ids"] = [padre]
        service.create_hito_manual(data)
    # el espejo se vacía a mano: así llega un proyecto guardado por la app vieja
    for hito in ps.active_project.causal_milestones:
        hito.causal_child_hito_ids = []

    chain = service.list_causal_chain("h1")
    assert isinstance(chain, Ok)
    assert [h.id for h in chain.value] == ["h1", "h2", "h3", "h4"]


@pytest.mark.application
def test_beta_m2fix09_adopta_los_enlaces_escritos_solo_en_el_espejo():
    """Un proyecto reparado A MANO (solo hijos) no pierde su declaración."""
    ps, service, _ = _setup()
    padre = service.create_hito_manual({"id": "p", "title": "Planta", "year": 1}).value
    hijo = service.create_hito_manual({"id": "h", "title": "Recoge", "year": 2}).value
    padre.causal_child_hito_ids = [hijo.id]  # solo el espejo, como el tester

    assert causal_links.reconcile_causal_links(ps.active_project) is True
    assert hijo.causal_parent_hito_ids == [padre.id]
    assert _hijos(service, padre.id) == [hijo.id]
    # idempotente
    assert causal_links.reconcile_causal_links(ps.active_project) is False


@pytest.mark.application
def test_beta_m2fix09_mundo_del_beta_deja_de_devolver_20_de_20():
    """Criterio 4, medido sobre el mundo entregado por el tester."""
    import json
    from pathlib import Path

    ruta = (
        Path(__file__).resolve().parents[2]
        / "beta-testing"
        / "2026-08-04"
        / "guionista-serie"
        / "mundo"
        / "orbita-muerta.json"
    )
    if not ruta.exists():  # pragma: no cover — el mundo del beta puede no estar
        pytest.skip("mundo del beta no disponible")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    from packages.domain.project import Project

    proyecto = Project.from_dict(datos)
    assert len(proyecto.causal_milestones) == 20
    sueltos = causal_links.loose_threads(proyecto)
    assert [h.title for h in sueltos] == ["2x08 — Habitable"]
    # y la cadena del setup 1x03 enseña su payoff
    setup = next(h for h in proyecto.causal_milestones if h.title.startswith("1x03"))
    cadena = [h.title for h in causal_links.causal_chain(proyecto, setup.id)]
    assert len(cadena) > 1
    assert any(t.startswith("2x03") for t in cadena)
    años = [
        h.year
        for h in causal_links.causal_chain(proyecto, setup.id)
        if isinstance(h.year, int)
    ]
    assert años == sorted(años)
