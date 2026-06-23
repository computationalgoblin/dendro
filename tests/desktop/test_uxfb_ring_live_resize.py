"""Reajuste de anillos EN VIVO (feedback post-UX10, item 7).

Al mover contenido, las bandas de anillo deben crecer/encogerse al instante
(como la física), no solo al soltar. ``_maybe_live_refresh_spans`` reajusta los
radios cada frame del tick, con guarda por delta y SIN reconstruir la física.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, _NodeView


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _layer(layer_id, name, rank):
    return SimpleNamespace(
        id=layer_id, name=name, metadata={"causal_rank": str(rank)}, is_visible=True, order=0
    )


def _node(entity_id, name, layer_id):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id]),
        entity_id=entity_id, name=name, kind="concepto",
        subtitle="", canon="canonico", visibility="publico", layer_id=layer_id,
    )


def _build_view() -> GraphCanvasView:
    view = GraphCanvasView()
    layers = [_layer("nucleo", "Núcleo", 1)]
    nodes = [_node("n1", "Uno", "nucleo")]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    return view


def test_anillo_crece_en_vivo_al_mover_nodo(qapp) -> None:
    view = _build_view()
    before = view._ring_visuals[0].outer_radius
    item = view._nodes["n1"]
    item.moveBy(280.0, 200.0)  # arrastre simulado hacia fuera
    view._maybe_live_refresh_spans()
    after = view._ring_visuals[0].outer_radius
    assert after > before + 1.0, "el anillo debería crecer en vivo al alejar el nodo"


def test_guarda_por_delta_evita_churn(qapp) -> None:
    view = _build_view()
    view._nodes["n1"].moveBy(280.0, 200.0)
    view._maybe_live_refresh_spans()
    settled = view._ring_visuals[0].outer_radius
    # Segunda llamada sin mover nada: no debe cambiar (ni redibujar).
    view._maybe_live_refresh_spans()
    assert abs(view._ring_visuals[0].outer_radius - settled) < 0.01


def test_refresh_en_vivo_no_reconstruye_fisica(qapp, monkeypatch) -> None:
    view = _build_view()
    calls = {"n": 0}

    def _count():
        calls["n"] += 1

    monkeypatch.setattr(view, "_rebuild_physics_world", _count)
    view._nodes["n1"].moveBy(300.0, 0.0)
    view._maybe_live_refresh_spans()
    assert calls["n"] == 0, "el refresh en vivo NO debe reconstruir el mundo físico"
