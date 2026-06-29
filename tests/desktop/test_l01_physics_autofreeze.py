"""BETA1-L01 — "modo rendimiento" del canvas en grafos grandes.

Por encima de ``PHYSICS_LIVE_MAX_BODIES`` cuerpos top-level:
 - la física hace una ráfaga de asentamiento ACOTADA (autofreeze) en vez de
   correr en vivo indefinidamente tras cada cambio;
 - los anillos NO se recalculan por frame (``_maybe_live_refresh_spans`` se omite).

Los grafos pequeños conservan el comportamiento histórico (sin congelación por
presupuesto, spans en vivo). El umbral se baja por monkeypatch para no construir
cientos de nodos en el test."""

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


def _node(entity_id: str, name: str, layer_id: str = ""):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id] if layer_id else []),
        entity_id=entity_id,
        name=name,
        kind="concepto",
        subtitle="",
        canon="canonico",
        visibility="publico",
        layer_id=layer_id,
    )


def _layers():
    return [
        SimpleNamespace(
            id="mundo", name="Mundo", metadata={"causal_rank": "1"}, is_visible=True, order=0
        ),
    ]


@pytest_qt
def test_large_graph_decrements_budget_and_autofreezes(qapp, monkeypatch):
    monkeypatch.setattr(gc, "PHYSICS_LIVE_MAX_BODIES", 3)
    monkeypatch.setattr(gc, "PHYSICS_SETTLE_FRAME_BUDGET", 6)
    view = GraphCanvasView()
    view.set_graph([_node(f"n{i}", f"N{i}") for i in range(8)], [])  # 8 > 3
    assert view._physics_timer.isActive() is True  # arranca la ráfaga
    assert view._physics_frames_left == 6  # presupuesto recargado en reheat

    view._physics_tick()
    assert view._physics_frames_left == 5  # grafo grande: consume presupuesto

    for _ in range(6):
        view._physics_tick()
    # agotado el presupuesto (o convergido): el grafo se congela, no late infinito
    assert view._physics_timer.isActive() is False


@pytest_qt
def test_small_graph_never_consumes_budget(qapp, monkeypatch):
    monkeypatch.setattr(gc, "PHYSICS_LIVE_MAX_BODIES", 100)
    monkeypatch.setattr(gc, "PHYSICS_SETTLE_FRAME_BUDGET", 6)
    view = GraphCanvasView()
    view.set_graph([_node("a", "A"), _node("b", "B"), _node("c", "C")], [])  # 3 < 100
    for _ in range(20):
        view._physics_tick()
    # el autofreeze por presupuesto NO aplica a grafos pequeños
    assert view._physics_frames_left == 6


@pytest_qt
def test_large_graph_skips_live_span_refresh(qapp, monkeypatch):
    monkeypatch.setattr(gc, "PHYSICS_LIVE_MAX_BODIES", 3)
    view = GraphCanvasView()
    view.set_graph(
        [_node(f"n{i}", f"N{i}", "mundo") for i in range(8)],
        [],
        layout_mode="concentric_rings",
        layers=_layers(),
    )
    calls: list[int] = []
    monkeypatch.setattr(view, "_maybe_live_refresh_spans", lambda: calls.append(1))
    view._physics_tick()
    assert calls == []  # grafo grande: nada de recálculo de spans por frame


@pytest_qt
def test_atmosphere_pauses_above_item_threshold(qapp, monkeypatch):
    monkeypatch.setattr(gc, "ATMOSPHERE_MAX_ITEMS", 3)
    view = GraphCanvasView()
    monkeypatch.setattr(view, "isVisible", lambda: True)
    view.set_graph([_node(f"n{i}", f"N{i}") for i in range(8)], [])  # 8 > 3
    view._apply_atmosphere_budget()
    assert view._atmosphere._timer.isActive() is False  # brisa pausada: sin repintado continuo


@pytest_qt
def test_atmosphere_runs_for_small_graph(qapp, monkeypatch):
    monkeypatch.setattr(gc, "ATMOSPHERE_MAX_ITEMS", 100)
    view = GraphCanvasView()
    monkeypatch.setattr(view, "isVisible", lambda: True)
    view.set_graph([_node("a", "A"), _node("b", "B")], [])  # 2 < 100
    view._apply_atmosphere_budget()
    assert view._atmosphere._timer.isActive() is True  # brisa activa en grafos pequeños


@pytest_qt
def test_small_graph_keeps_live_span_refresh(qapp, monkeypatch):
    monkeypatch.setattr(gc, "PHYSICS_LIVE_MAX_BODIES", 100)
    view = GraphCanvasView()
    view.set_graph(
        [_node("a", "A", "mundo"), _node("b", "B", "mundo")],
        [],
        layout_mode="concentric_rings",
        layers=_layers(),
    )
    calls: list[int] = []
    monkeypatch.setattr(view, "_maybe_live_refresh_spans", lambda: calls.append(1))
    view._physics_tick()
    assert calls == [1]  # grafo pequeño: spans en vivo como siempre
