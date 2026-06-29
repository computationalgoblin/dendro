"""BETA1-L02 — selector de anillos + navegación 'un anillo a la vez'.

ring_summaries() ordena los anillos de dentro a fuera con su recuento; enfocar un
anillo atenúa el resto (opacidad) y guarda el foco; saltar contiguo recorre el
orden con clamp; salir restaura la opacidad."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
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
        entity_id=entity_id, name=name, kind="concepto", subtitle="",
        canon="canonico", visibility="publico", layer_id=layer_id,
    )


def _concentric_view():
    v = GraphCanvasView()
    v.resize(900, 700)
    v.viewport().resize(900, 700)
    layers = [_layer("mundo", "Mundo", 1), _layer("gente", "Gente", 2), _layer("magia", "Magia", 3)]
    nodes = [
        _node("a", "A", "mundo"), _node("b", "B", "mundo"),
        _node("c", "C", "gente"),
        _node("d", "D", "magia"), _node("e", "E", "magia"),
    ]
    v.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    return v


@pytest_qt
def test_ring_summaries_ordered_inner_to_outer_with_counts(qapp):
    v = _concentric_view()
    summaries = v.ring_summaries()
    assert len(summaries) >= 3
    radii = [s["inner"] for s in summaries]
    assert radii == sorted(radii)  # de dentro a fuera
    total = sum(s["count"] for s in summaries)
    assert total == 5  # los 5 nodos repartidos por anillos


@pytest_qt
def test_focus_ring_attenuates_others(qapp):
    v = _concentric_view()
    target = next(s for s in v.ring_summaries() if s["count"] > 0)
    assert v.focus_ring_scope(target["ring_id"]) is True
    assert v._focused_ring_id == target["ring_id"]
    for eid, item in v._nodes.items():
        ring = v._node_ring_ids.get(eid, "")
        if ring == target["ring_id"]:
            assert item.opacity() == 1.0
        else:
            assert item.opacity() < 0.5  # atenuado (contexto translúcido)


@pytest_qt
def test_focus_adjacent_ring_steps_and_clamps(qapp):
    v = _concentric_view()
    order = [s["ring_id"] for s in v.ring_summaries()]
    v.focus_ring_scope(order[0])
    v.focus_adjacent_ring(1)
    assert v._focused_ring_id == order[1]  # siguiente (hacia fuera)
    v.focus_ring_scope(order[0])
    v.focus_adjacent_ring(-1)
    assert v._focused_ring_id == order[0]  # clamp en el más interno


@pytest_qt
def test_clear_ring_focus_restores_opacity_and_signals(qapp):
    v = _concentric_view()
    cleared = []
    v.ringFocusCleared.connect(lambda: cleared.append(1))
    target = next(s for s in v.ring_summaries() if s["count"] > 0)
    v.focus_ring_scope(target["ring_id"])
    v.clear_ring_focus()
    assert v._focused_ring_id == ""
    assert cleared == [1]
    assert all(item.opacity() == 1.0 for item in v._nodes.values())
