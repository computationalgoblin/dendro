"""BETA1-L02 — zoom adaptativo + 'ver todo' del grafo concéntrico.

El suelo de alejamiento (antes fijo en 0.22) ahora se adapta al tamaño del grafo:
en grafos enormes se puede alejar hasta enmarcar el conjunto. 'ver todo' encuadra
todo el contenido. Zoom in/out respetan los límites."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    import hosts.DesktopHostPySide.widgets.graph_canvas as gc
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, _NodeView

pytest_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    if not HAS_QT:
        return None
    return QApplication.instance() or QApplication([])


def _node(entity_id, name):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[]),
        entity_id=entity_id, name=name, kind="concepto", subtitle="",
        canon="canonico", visibility="publico", layer_id="",
    )


def _sized_view():
    v = GraphCanvasView()
    v.resize(1000, 800)
    v.viewport().resize(1000, 800)
    return v


@pytest_qt
def test_small_graph_keeps_historic_floor(qapp):
    v = _sized_view()
    v.set_graph([_node("a", "A"), _node("b", "B")], [])
    # Grafo pequeño: el suelo sigue siendo el histórico (no se aleja al vacío).
    assert abs(v._min_zoom() - gc._ZOOM_OUT_FLOOR) < 1e-6


@pytest_qt
def test_large_graph_lowers_zoom_floor(qapp):
    v = _sized_view()
    v.set_graph([_node("a", "A"), _node("b", "B")], [])
    v._nodes["b"].setPos(30000.0, 30000.0)  # escena enorme
    # El suelo baja MUY por debajo de 0.22 → se puede enmarcar el conjunto.
    assert v._min_zoom() < 0.05


@pytest_qt
def test_zoom_out_can_reach_whole_graph(qapp):
    v = _sized_view()
    v.set_graph([_node("a", "A"), _node("b", "B")], [])
    v._nodes["b"].setPos(30000.0, 30000.0)
    v.resetTransform()
    v.scale(1.0, 1.0)
    for _ in range(120):
        v.zoom_out()
    scale = v.transform().m11()
    assert scale < 0.22  # ANTES imposible (topado en 0.22)
    assert scale >= v._min_zoom() - 1e-6  # nunca por debajo del suelo


@pytest_qt
def test_zoom_in_respects_max(qapp):
    v = _sized_view()
    v.set_graph([_node("a", "A")], [])
    for _ in range(200):
        v.zoom_in()
    assert v.transform().m11() <= gc._ZOOM_MAX + 1e-6


@pytest_qt
def test_fit_all_frames_content(qapp, monkeypatch):
    monkeypatch.setattr(gc, "MOTION_ENABLED", False)  # fit instantáneo, determinista
    v = _sized_view()
    v.set_graph([_node("a", "A"), _node("b", "B")], [])
    v._nodes["b"].setPos(20000.0, 20000.0)
    v.resetTransform()
    v.scale(2.0, 2.0)  # muy acercado
    v.fit_all()  # 'ver todo' (reutiliza el fit_all existente del canvas)
    # Tras 'ver todo' la escala baja a ~la escala-fit (todo el contenido cabe),
    # muy por debajo del antiguo suelo de 0.22 — el fit no está topado.
    assert v.transform().m11() < 0.2
