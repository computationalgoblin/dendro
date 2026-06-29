"""BETA1-UX41 — navegación de la cronología: teclado, edge-pan y filtro de era.

Comprueba las mecánicas de la vista (sin tocar la capa pura): velocidad de edge-pan,
filtro de era (reusa la ventana temporal), foco de anillo por número, navegación por
entidades/hitos con resaltado + centro, y Enter abre el actual.
"""
from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

if HAS_QT:
    from PySide6.QtCore import QPointF, QSize, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ent(eid, name, *, kind="personaje", ring="r0", birth=20, death=None):
    return SimpleNamespace(
        id=eid, name=name, entity_type=kind, layer_ids=[ring] if ring else [],
        birth_year=birth, death_year=death, custom_metadata={}, metadata={},
        visibility_state="visible_usuario", canon_state="canonico",
    )


def _layer(lid, name, rank):
    return SimpleNamespace(id=lid, name=name, metadata={"causal_rank": float(rank)},
                           order=rank, is_visible=True)


def _hito(hid, title, year, affected):
    return SimpleNamespace(id=hid, title=title, year=year,
                           affected_entity_ids=affected, metadata={})


def _project():
    eras = [
        SimpleNamespace(id="e0", name="Antigua", start_year=0, end_year=80, order=0),
        SimpleNamespace(id="e1", name="Media", start_year=80, end_year=300, order=1),
    ]
    ents = [
        _ent("a", "A", ring="r0", birth=10, death=200),
        _ent("b", "B", ring="r1", birth=20),
        _ent("c", "C", ring="r0", birth=30),
    ]
    hitos = [_hito("h1", "H1", 40, ["a"]), _hito("h2", "H2", 120, ["a", "c"])]
    return SimpleNamespace(
        entities=ents, relations=[],
        world_layers=[_layer("r0", "Mundo", 0), _layer("r1", "Meta", 1)],
        causal_milestones=hitos,
        project_chronology=SimpleNamespace(present_year=400, eras=eras, metadata={}),
    )


def _view(qapp):
    v = ChronoCanvasView()
    v._collapse_default = False  # ver todo en los tests de navegación
    v.set_atmosphere_context(SimpleNamespace(creation_chrono_expanded_ids=[]))
    v.resize(900, 500)
    v.set_project(_project())
    return v


# ── edge-pan (helper puro) ──────────────────────────────────────────────────

def test_edge_pan_cero_en_el_centro(qapp):
    v = _view(qapp)
    assert v._edge_pan_velocity(QPointF(450, 250), QSize(900, 500)) == (0.0, 0.0)


def test_edge_pan_signos_por_borde(qapp):
    v = _view(qapp)
    size = QSize(900, 500)
    assert v._edge_pan_velocity(QPointF(4, 250), size)[0] < 0      # izquierda
    assert v._edge_pan_velocity(QPointF(896, 250), size)[0] > 0    # derecha
    assert v._edge_pan_velocity(QPointF(450, 4), size)[1] < 0      # arriba
    assert v._edge_pan_velocity(QPointF(450, 496), size)[1] > 0    # abajo


# ── filtro de era ───────────────────────────────────────────────────────────

def test_focus_era_acota_la_ventana_y_alterna(qapp):
    v = _view(qapp)
    v.focus_era("e0")
    assert (v._year_min, v._year_max) == (0, 80) and v._focused_era_id == "e0"
    v.focus_era("e0")  # re-seleccionar la quita
    assert (v._year_min, v._year_max) == (None, None) and v._focused_era_id == ""


# ── foco de anillo por número ───────────────────────────────────────────────

def test_focus_ring_by_index_y_toggle(qapp):
    v = _view(qapp)
    rings = list(v._all_rings)
    v._focus_ring_by_index(0)
    assert v._focused_ring_id == rings[0][0]
    v._focus_ring_by_index(0)  # repetir quita el foco
    assert v._focused_ring_id == ""


def test_cambiar_de_anillo_directamente_con_uno_enfocado(qapp):
    # Regresión: con un anillo enfocado, layout.columns queda con uno solo; cambiar a
    # OTRO debe seguir funcionando porque se usa la lista COMPLETA (_all_rings).
    v = _view(qapp)
    rings = list(v._all_rings)
    assert len(rings) >= 2
    v._focus_ring_by_index(0)
    assert v._focused_ring_id == rings[0][0]
    assert len(v._layout.columns) == 1  # el layout queda filtrado a un anillo
    v._focus_ring_by_index(1)           # …pero se puede cambiar directo al otro
    assert v._focused_ring_id == rings[1][0]


def test_focus_era_funciona_con_anillo_ya_enfocado(qapp):
    # La era se busca en la lista COMPLETA, no en layout.eras (que el anillo no
    # filtra, pero sí lo haría una ventana previa): cambiar de era siempre acota.
    v = _view(qapp)
    v._focus_ring_by_index(0)           # anillo enfocado
    v.focus_era("e1")
    assert (v._year_min, v._year_max) == (80, 300) and v._focused_era_id == "e1"
    v.focus_era("e0")                   # cambiar de era directamente
    assert (v._year_min, v._year_max) == (0, 80) and v._focused_era_id == "e0"


# ── navegación por flechas + Enter ──────────────────────────────────────────

def test_nav_entity_avanza_y_enter_abre(qapp):
    v = _view(qapp)
    emitted = {}
    v.entityActivated.connect(lambda e: emitted.__setitem__("e", e))
    v._nav_entity(1)
    first = v._nav_entity_id
    assert first and v._nav_kind == "entity"
    v._nav_entity(1)
    assert v._nav_entity_id != first  # avanzó a otra entidad
    v._open_nav_current()
    assert emitted.get("e") == v._nav_entity_id


def test_nav_milestone_por_anio_y_enter_abre(qapp):
    v = _view(qapp)
    emitted = {}
    v.milestoneActivated.connect(lambda m: emitted.__setitem__("m", m))
    v._nav_milestone(1)
    assert v._nav_milestone_id == "h1" and v._nav_kind == "milestone"  # el más temprano
    v._nav_milestone(1)
    assert v._nav_milestone_id == "h2"
    v._open_nav_current()
    assert emitted.get("m") == "h2"


# ── Tab recorre las eras ────────────────────────────────────────────────────

def test_tab_recorre_eras(qapp):
    v = _view(qapp)
    QTest.keyClick(v, Qt.Key.Key_Tab)
    assert v._focused_era_id == "e0"
    QTest.keyClick(v, Qt.Key.Key_Tab)
    assert v._focused_era_id == "e1"
    QTest.keyClick(v, Qt.Key.Key_Backtab)  # Shift+Tab → anterior
    assert v._focused_era_id == "e0"
