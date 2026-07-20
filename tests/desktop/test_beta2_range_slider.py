"""BETA2-UI2-10: rango-cámara del Mapa y slider de dos asas.

- ``interval_overlaps_range`` es pura (solape de intervalos de vida).
- ``GraphCanvasView.set_view_range`` muestra lo que existe en ALGÚN punto del
  intervalo; con ``lo == hi`` reproduce el año-cámara clásico y es no-op si el
  rango no cambia (sin reconstrucciones al arrastrar sin mover).
- ``_EraRangeSlider`` clampa/normaliza sus asas y emite ``rangeChanged``.
"""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.graph_canvas import (
    _EdgeView,
    _NodeView,
    interval_overlaps_range,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None


# ── Predicate pura ─────────────────────────────────────────────────────────


def test_interval_overlaps_range_boundaries():
    # Sin nacimiento conocido → nunca se oculta (pre-migración / derivada)
    assert interval_overlaps_range(None, None, 0, 10) is True
    # Intervalo abierto (sigue viva): solapa con todo lo posterior al birth
    assert interval_overlaps_range(10, None, 0, 9) is False
    assert interval_overlaps_range(10, None, 0, 10) is True
    assert interval_overlaps_range(10, None, 500, 900) is True
    # Intervalo cerrado, límites inclusivos por ambos lados
    assert interval_overlaps_range(10, 20, 20, 30) is True
    assert interval_overlaps_range(10, 20, 21, 30) is False
    assert interval_overlaps_range(10, 20, 0, 10) is True
    assert interval_overlaps_range(10, 20, 0, 9) is False
    # Vida contenida dentro del rango y rango contenido dentro de la vida
    assert interval_overlaps_range(10, 20, 0, 100) is True
    assert interval_overlaps_range(0, 100, 40, 60) is True
    # Con lo == hi equivale a interval_contains_year
    assert interval_overlaps_range(10, 20, 15, 15) is True
    assert interval_overlaps_range(10, 20, 21, 21) is False
    # Años negativos (a.C.)
    assert interval_overlaps_range(-1000, -500, -600, -100) is True
    assert interval_overlaps_range(-1000, -500, -499, 0) is False


# ── Helpers (patrón SimpleNamespace de la casa) ────────────────────────────


def _node(eid: str, *, birth=None, death=None) -> _NodeView:
    return _NodeView(
        entity=SimpleNamespace(id=eid),
        entity_id=eid,
        name=eid,
        kind="personaje",
        subtitle="",
        canon="canon",
        visibility="publico",
        birth_year=birth,
        death_year=death,
    )


def _edge(rid: str, src: str, tgt: str, *, birth=None, death=None) -> _EdgeView:
    return _EdgeView(
        relation=SimpleNamespace(id=rid),
        relation_id=rid,
        source_id=src,
        target_id=tgt,
        kind="conoce",
        label="conoce",
        birth_year=birth,
        death_year=death,
    )


@pytest.fixture()
def view():
    if not HAS_QT:
        pytest.skip("PySide6 not installed")
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView

    QApplication.instance() or QApplication([])
    return GraphCanvasView()


# ── Rango-cámara en la vista ───────────────────────────────────────────────


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_view_range_shows_union_of_interval(view):
    nodes = [
        _node("A", birth=-100, death=-20),  # muere en -20
        _node("B", birth=0),                # nace en 0
        _node("C", birth=-40),              # vive de -40 en adelante
    ]
    view.set_graph(nodes, [], layout_mode="free")
    assert view.view_range() is None

    # [-30, 10]: A murió en -20 (dentro), B nace en 0 (dentro), C vive → TODOS
    view.set_view_range(-30, 10)
    assert set(view._nodes.keys()) == {"A", "B", "C"}

    # [-30, -25]: B aún no existe
    view.set_view_range(-30, -25)
    assert set(view._nodes.keys()) == {"A", "C"}

    # None restaura el modo atemporal
    view.set_view_range(None)
    assert set(view._nodes.keys()) == {"A", "B", "C"}
    assert view.view_range() is None


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_view_range_single_year_matches_classic_snapshot(view):
    nodes = [
        _node("A", birth=-100, death=-20),
        _node("B", birth=0),
        _node("C", birth=-40),
    ]
    edges = [_edge("rAC", "A", "C"), _edge("rBC", "B", "C")]
    view.set_graph(nodes, edges, layout_mode="free")

    # lo == hi reproduce el comportamiento clásico de set_view_year(0)
    view.set_view_range(0, 0)
    assert set(view._nodes.keys()) == {"B", "C"}
    assert {e.edge.relation_id for e in view._edges} == {"rBC"}
    assert view.view_year() == 0

    # set_view_year sigue funcionando (compat) y view_year con rango real → None
    view.set_view_year(-30)
    assert set(view._nodes.keys()) == {"A", "C"}
    view.set_view_range(-30, 0)
    assert view.view_year() is None
    assert view.view_range() == (-30, 0)


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_view_range_normalizes_and_is_noop_when_unchanged(view, monkeypatch):
    nodes = [_node("A", birth=0)]
    view.set_graph(nodes, [], layout_mode="free")

    rebuilds = []
    original = view.set_graph

    def counting_set_graph(*args, **kwargs):
        rebuilds.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(view, "set_graph", counting_set_graph)

    view.set_view_range(10, -30)  # se normaliza a (-30, 10)
    assert view.view_range() == (-30, 10)
    assert len(rebuilds) == 1

    view.set_view_range(-30, 10)  # mismo rango → no-op, sin rebuild
    view.set_view_range(10, -30)  # normalizado idéntico → no-op
    assert len(rebuilds) == 1

    view.set_view_range(None)
    view.set_view_range(None)  # None repetido → un solo rebuild
    assert len(rebuilds) == 2


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_view_range_respects_explicit_relation_interval(view):
    nodes = [_node("X", birth=0), _node("Y", birth=0)]
    edges = [_edge("enemistad", "X", "Y", birth=50, death=60)]
    view.set_graph(nodes, edges, layout_mode="free")

    view.set_view_range(10, 40)  # ambos vivos, la relación aún no existe
    assert view._edges == []
    view.set_view_range(40, 55)  # el rango alcanza el nacimiento de la relación
    assert {e.edge.relation_id for e in view._edges} == {"enemistad"}
    view.set_view_range(61, 90)  # la relación ya terminó
    assert view._edges == []


# ── Slider de dos asas ─────────────────────────────────────────────────────


@pytest.fixture()
def slider():
    if not HAS_QT:
        pytest.skip("PySide6 not installed")
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.graph_canvas import _EraRangeSlider

    QApplication.instance() or QApplication([])
    widget = _EraRangeSlider()
    widget.resize(300, 34)
    widget.set_range(0, 100)
    return widget


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_range_slider_clamps_and_normalizes(slider):
    slider.set_values(30, 20)  # desordenado → se normaliza
    assert slider.values() == (20, 30)
    slider.set_values(-50, 900)  # fuera de rango → se clampa
    assert slider.values() == (0, 100)
    slider.set_range(10, 40)  # el rango nuevo re-clampa las asas
    assert slider.values() == (10, 40)
    slider.set_range(40, 10)  # rango degenerado → hi = lo
    assert (slider.minimum(), slider.maximum()) == (40, 40)


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_range_slider_emits_range_changed_once(slider):
    received = []
    slider.rangeChanged.connect(lambda a, b: received.append((a, b)))
    slider.set_values(20, 60)
    assert received == [(20, 60)]
    slider.set_values(20, 60)  # sin cambio → sin emisión
    assert received == [(20, 60)]
    block = slider.blockSignals(True)
    slider.set_values(0, 10)  # silenciado, como un QSlider
    slider.blockSignals(block)
    assert received == [(20, 60)]
    assert slider.values() == (0, 10)


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_range_slider_geometry_roundtrip(slider):
    # año → x → año es estable en los extremos y el centro
    for year in (0, 50, 100):
        x = slider._x_for_value(year)
        assert slider._value_for_x(x) == year
    # x fuera del groove se clampa a los límites
    assert slider._value_for_x(-999.0) == 0
    assert slider._value_for_x(9999.0) == 100
