"""BETA1-L02b — teclas 1…0 enfocan el anillo N por orden causal.

`focus_ring_by_index(i)` reutiliza `focus_ring_scope` (cámara + atenuación +
breadcrumb + resaltado): enfoca el anillo i-ésimo de `ring_summaries()` y atenúa el
resto. Índice fuera de rango = no-op; en modo no concéntrico = no-op."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, _NodeView

pytest_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    if not HAS_QT:
        return None
    return QApplication.instance() or QApplication([])


def _layer(lid, name, rank):
    return SimpleNamespace(
        id=lid, name=name, metadata={"causal_rank": str(rank)}, is_visible=True, order=0
    )


def _node(entity_id, name, layer_id):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id]),
        entity_id=entity_id,
        name=name,
        kind="concepto",
        subtitle="",
        canon="canonico",
        visibility="publico",
        layer_id=layer_id,
    )


def _concentric_view():
    v = GraphCanvasView()
    v.resize(900, 700)
    v.viewport().resize(900, 700)
    layers = [_layer("mundo", "Mundo", 1), _layer("gente", "Gente", 2), _layer("magia", "Magia", 3)]
    nodes = [
        _node("a", "A", "mundo"),
        _node("b", "B", "mundo"),
        _node("c", "C", "gente"),
        _node("d", "D", "magia"),
        _node("e", "E", "magia"),
    ]
    v.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    return v


@pytest_qt
def test_focus_ring_by_index_focuses_nth_ring(qapp):
    v = _concentric_view()
    order = [s["ring_id"] for s in v.ring_summaries()]
    assert v.focus_ring_by_index(2) is True
    assert v._focused_ring_id == order[2]  # 3er anillo (tecla '3')
    # El resto queda atenuado (contexto translúcido detrás).
    for eid, item in v._nodes.items():
        if v._node_ring_ids.get(eid, "") == order[2]:
            assert item.opacity() == 1.0
        else:
            assert item.opacity() < 0.5


@pytest_qt
def test_focus_ring_by_index_out_of_range_is_noop(qapp):
    v = _concentric_view()
    assert v.focus_ring_by_index(99) is False
    assert v._focused_ring_id == ""  # sin foco
    assert v.focus_ring_by_index(-1) is False
    assert v._focused_ring_id == ""


@pytest_qt
def test_focus_ring_by_index_noop_when_not_concentric(qapp):
    v = GraphCanvasView()
    v.resize(900, 700)
    v.viewport().resize(900, 700)
    v.set_graph([_node("a", "A", ""), _node("b", "B", "")], [])  # layout libre
    assert v.focus_ring_by_index(0) is False
    assert v._focused_ring_id == ""


@pytest_qt
def test_digit_key_focuses_ring(qapp):
    # BETA1-L02c: pulsar un dígito (aquí '2') enfoca el anillo correspondiente vía
    # keyPressEvent — verifica el gate concéntrico + el cableado de las teclas.
    v = _concentric_view()
    order = [s["ring_id"] for s in v.ring_summaries()]
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier)
    v.keyPressEvent(event)
    assert v._focused_ring_id == order[1]  # tecla '2' → segundo anillo


@pytest_qt
def test_focus_dims_ring_items_not_just_nodes(qapp):
    # BETA1-L02c: al enfocar, los CÍRCULOS de anillo no enfocados también se atenúan.
    v = _concentric_view()
    target = next(s for s in v.ring_summaries() if s["count"] > 0)
    v.focus_ring_scope(target["ring_id"])
    assert v._ring_items, "el grafo concéntrico debe tener círculos de anillo"
    for ring_id, ring_item in v._ring_items.items():
        if ring_id == target["ring_id"]:
            assert ring_item.opacity() == 1.0
        else:
            assert ring_item.opacity() < 0.5  # vecino tenue, pero visible


@pytest_qt
def test_reset_to_panorama_clears_focus_and_restores(qapp):
    # BETA1-L02c: F (reset_to_panorama) SIEMPRE restaura: quita el foco y devuelve
    # opacidad plena a nodos y a círculos de anillo.
    v = _concentric_view()
    target = next(s for s in v.ring_summaries() if s["count"] > 0)
    v.focus_ring_scope(target["ring_id"])
    v.reset_to_panorama()
    assert v._focused_ring_id == ""
    assert all(item.opacity() == 1.0 for item in v._nodes.values())
    assert all(ring_item.opacity() == 1.0 for ring_item in v._ring_items.values())
