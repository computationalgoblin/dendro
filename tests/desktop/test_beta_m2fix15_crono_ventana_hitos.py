"""BETA2-FIX-15 (G2-27) — la ventana temporal filtra TAMBIÉN los hitos.

El bucle de marcas de `build_chrono_layout` no miraba el `scope` ni una vez: acotar
los años (scrubber) o enfocar una era dejaba los mismos hitos en el lienzo (18, 18 y
18 con las tres ventanas que probó el tester). Eras y líneas de vida sí lo hacían.

Aquí se fija la simetría: el hito entra si su intervalo `[year, end_year]` solapa la
ventana, incluidas las cajas de hito-marco (que se construían sobre la lista COMPLETA
de hitos y habrían dejado marcos huérfanos).
"""
from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from hosts.DesktopHostPySide.widgets.chrono_canvas import (  # noqa: E402
    ChronoScope,
    build_chrono_layout,
)


def _ent(eid, name, *, ring="r0", birth=0, death=None):
    return SimpleNamespace(
        id=eid, name=name, entity_type="personaje", layer_ids=[ring],
        birth_year=birth, death_year=death, custom_metadata={}, metadata={},
        visibility_state="visible_usuario", canon_state="canonico",
    )


def _hito(hid, title, year, *, affected=(), end=None, parent="", meta=None):
    span = SimpleNamespace(end_year=end) if end is not None else None
    return SimpleNamespace(
        id=hid, title=title, year=year, affected_entity_ids=list(affected),
        metadata=dict(meta or {}), custom_metadata={}, parent_milestone_id=parent,
        as_temporal_span=(lambda s=span: s) if span is not None else None,
    )


def _layer(lid, name, rank):
    return SimpleNamespace(id=lid, name=name, metadata={"causal_rank": float(rank)},
                           order=rank, is_visible=True)


def _project(hitos, *, ents=None, layers=None, eras=None):
    return SimpleNamespace(
        entities=list(ents if ents is not None else [_ent("e0", "Testigo")]),
        relations=[],
        world_layers=list(layers if layers is not None else [_layer("r0", "Uno", 0)]),
        causal_milestones=list(hitos),
        project_chronology=SimpleNamespace(present_year=400, eras=list(eras or []), metadata={}),
    )


def _ids(layout):
    return [mark.milestone_id for mark in layout.milestones]


# ── Ventana temporal ────────────────────────────────────────────────────────

def test_sin_ventana_no_cambia_nada():
    proj = _project([_hito("h1", "Uno", 10), _hito("h2", "Dos", 100),
                     _hito("h3", "Tres", 300)])
    assert sorted(_ids(build_chrono_layout(proj))) == ["h1", "h2", "h3"]


def test_ventana_temporal_recorta_hitos():
    proj = _project([_hito("h1", "Uno", 10), _hito("h2", "Dos", 100),
                     _hito("h3", "Tres", 300)])
    layout = build_chrono_layout(proj, scope=ChronoScope(year_min=80, year_max=150))
    assert _ids(layout) == ["h2"]


def test_ventana_temporal_conserva_hito_con_lapso_que_solapa():
    # Mismo criterio de solape que `_entity_in_window`: el hito arranca antes de la
    # ventana pero su lapso entra en ella.
    proj = _project([_hito("h1", "Guerra larga", 50, end=120),
                     _hito("h2", "Fuera", 10, end=20)])
    layout = build_chrono_layout(proj, scope=ChronoScope(year_min=80, year_max=150))
    assert _ids(layout) == ["h1"]


def test_hito_fuera_de_ventana_no_deja_ni_punto_ni_franja():
    # Criterio 4: ni banda, ni título, ni punto. La marca ES la fuente de los tres,
    # así que basta con que no se emita ninguna para el hito recortado.
    ent = _ent("e0", "Testigo")
    proj = _project([_hito("h1", "Antiguo", 10, affected=["e0"]),
                     _hito("h2", "Actual", 100, affected=["e0"])], ents=[ent])
    layout = build_chrono_layout(proj, scope=ChronoScope(year_min=80, year_max=150))
    assert _ids(layout) == ["h2"]
    assert all(mark.entity_ids == ["e0"] for mark in layout.milestones)


def test_ventana_temporal_recorta_cajas_de_subhitos():
    marco = _hito("marco", "La Guerra", 10, end=20)
    sub = _hito("sub", "Escaramuza", 15, parent="marco")
    proj = _project([marco, sub, _hito("h2", "Actual", 100)])
    completo = build_chrono_layout(proj)
    assert [box.milestone_id for box in completo.milestone_boxes] == ["marco"]
    recortado = build_chrono_layout(proj, scope=ChronoScope(year_min=80, year_max=150))
    assert _ids(recortado) == ["h2"]
    assert recortado.milestone_boxes == []


def test_hito_sin_ano_se_ubica_en_el_presente_y_la_ventana_lo_trata_ahi():
    # Decisión consciente: un hito sin año se dibuja en el presente, así que una
    # ventana que no contenga el presente lo recorta (coherente con dónde se pinta).
    proj = _project([_hito("h1", "Sin fecha", None)])  # present_year = 400
    assert _ids(build_chrono_layout(proj)) == ["h1"]
    dentro = build_chrono_layout(proj, scope=ChronoScope(year_min=350, year_max=450))
    assert _ids(dentro) == ["h1"]
    fuera = build_chrono_layout(proj, scope=ChronoScope(year_min=0, year_max=100))
    assert _ids(fuera) == []


# ── Franja hueca: participantes todos filtrados (pregunta abierta 2) ────────

def test_hito_con_todos_los_participantes_filtrados_no_deja_franja_hueca():
    # Decisión: se oculta SOLO si el hito TENÍA participantes y un filtro se los
    # ha llevado a todos (antes se pintaba una banda cruzando el lienzo con cero
    # puntos). Aquí el filtro es el foco de anillo.
    ents = [_ent("a", "A", ring="r0"), _ent("b", "B", ring="r1")]
    layers = [_layer("r0", "Uno", 0), _layer("r1", "Dos", 1)]
    hitos = [_hito("h_a", "De A", 100, affected=["a"]),
             _hito("h_b", "De B", 100, affected=["b"])]
    proj = _project(hitos, ents=ents, layers=layers)
    assert sorted(_ids(build_chrono_layout(proj))) == ["h_a", "h_b"]
    enfocado = build_chrono_layout(proj, scope=ChronoScope(focused_ring_id="r0"))
    assert _ids(enfocado) == ["h_a"]


def test_hito_sin_participantes_se_dibuja_siempre():
    # Un hito sin participantes es LEGAL (una era que cambia, un suceso del mundo):
    # no puede desaparecer por la regla anterior.
    ents = [_ent("a", "A", ring="r0"), _ent("b", "B", ring="r1")]
    layers = [_layer("r0", "Uno", 0), _layer("r1", "Dos", 1)]
    proj = _project([_hito("h0", "El Diluvio", 100)], ents=ents, layers=layers)
    assert _ids(build_chrono_layout(proj)) == ["h0"]
    assert _ids(build_chrono_layout(proj, scope=ChronoScope(focused_ring_id="r0"))) == ["h0"]


def test_colapsar_una_rama_no_borra_sus_hitos():
    # El colapso OCULTA carriles, no filtra entidades: un hito cuyos participantes
    # están dentro de la rama colapsada sigue dibujándose (con sus puntos plegados).
    rama = SimpleNamespace(
        id="t0", name="La Orden", entity_type="contenedor", layer_ids=["r0"],
        birth_year=0, death_year=None, custom_metadata={}, metadata={},
        visibility_state="visible_usuario", canon_state="canonico",
    )
    miembro = _ent("m0", "Miembro")
    proj = _project([_hito("h1", "Interno", 100, affected=["m0"])], ents=[rama, miembro])
    proj.relations = [SimpleNamespace(relation_type="contiene", source_id="t0",
                                      target_id="m0")]
    colapsado = build_chrono_layout(proj, scope=ChronoScope(collapse_default=True))
    assert {lf.entity_id for lf in colapsado.lifelines} == {"t0"}
    assert _ids(colapsado) == ["h1"]


# ── Foco de era (criterio 5), vía la vista ──────────────────────────────────

def test_foco_de_era_deja_solo_los_hitos_de_esa_era():
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    _ = QApplication.instance() or QApplication([])
    eras = [
        SimpleNamespace(id="era1", name="Primera", start_year=0, end_year=100, order=0),
        SimpleNamespace(id="era2", name="Segunda", start_year=101, end_year=200, order=1),
    ]
    proj = _project([_hito("h1", "Temporada 1", 50), _hito("h2", "Temporada 2", 150)],
                    eras=eras)
    view = ChronoCanvasView()
    view.set_project(proj)
    assert view._layout is not None
    assert sorted(_ids(view._layout)) == ["h1", "h2"]

    view.focus_era("era2")
    assert _ids(view._layout) == ["h2"]

    view.focus_era("era1")
    assert _ids(view._layout) == ["h1"]

    view.focus_era("era1")  # re-seleccionar quita el foco
    assert sorted(_ids(view._layout)) == ["h1", "h2"]


def test_scrubber_de_intervalo_recorta_los_hitos():
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    _ = QApplication.instance() or QApplication([])
    proj = _project([_hito("h1", "Temporada 1", 50), _hito("h2", "Temporada 2", 150)])
    view = ChronoCanvasView()
    view.set_project(proj)
    view.set_time_window(0, 100)
    assert _ids(view._layout) == ["h1"]
    view.set_time_window(None, None)
    assert sorted(_ids(view._layout)) == ["h1", "h2"]
