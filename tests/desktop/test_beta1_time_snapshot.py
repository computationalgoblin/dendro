"""BETA1-G06: "fotografía temporal" del grafo concéntrico.

El grafo de arriba (anillos) puede visitarse en cualquier año: solo se ven
las entidades vivas y las relaciones existentes en ese momento. La predicate
de intervalo es pura; el filtrado de escena se valida con Qt offscreen.

Contrato base: docs/architecture/G01_time_contract.md.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.widgets.graph_canvas import (
    _EdgeView,
    _NodeView,
    interval_contains_year,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
ROOT = Path(__file__).resolve().parents[2]


# ── Predicate pura ─────────────────────────────────────────────────────────

def test_interval_contains_year_boundaries():
    # Sin nacimiento conocido → nunca se oculta (pre-migración / derivada)
    assert interval_contains_year(None, None, 5) is True
    # Intervalo abierto (sigue viva)
    assert interval_contains_year(10, None, 9) is False
    assert interval_contains_year(10, None, 10) is True
    assert interval_contains_year(10, None, 999) is True
    # Intervalo cerrado, límites inclusivos
    assert interval_contains_year(10, 20, 10) is True
    assert interval_contains_year(10, 20, 20) is True
    assert interval_contains_year(10, 20, 21) is False
    # Años negativos (a.C.)
    assert interval_contains_year(-1000, -1, -500) is True
    assert interval_contains_year(-1000, -1, 0) is False


# ── Helpers de construcción de vistas ──────────────────────────────────────

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


# ── Fotografía en la escena concéntrica ────────────────────────────────────

@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_snapshot_filters_entities_and_derived_relations(view):
    nodes = [
        _node("A", birth=-100, death=-20),  # muerto antes del año 0
        _node("B", birth=0),                # nace en el año 0
        _node("C", birth=-40),              # vivo de -40 en adelante
    ]
    edges = [_edge("rAC", "A", "C"), _edge("rBC", "B", "C")]

    view.set_graph(nodes, edges, layout_mode="free")
    assert set(view._nodes.keys()) == {"A", "B", "C"}
    assert view.view_year() is None  # por defecto: atemporal, se ve todo

    # Año -30: A vive, C vive, B aún no existe → solo la relación A–C
    view.set_view_year(-30)
    assert set(view._nodes.keys()) == {"A", "C"}
    assert {e.edge.relation_id for e in view._edges} == {"rAC"}

    # Año 0: A ya murió, B y C viven → solo la relación B–C
    view.set_view_year(0)
    assert set(view._nodes.keys()) == {"B", "C"}
    assert {e.edge.relation_id for e in view._edges} == {"rBC"}

    # Volver a atemporal restaura todo
    view.set_view_year(None)
    assert set(view._nodes.keys()) == {"A", "B", "C"}
    assert {e.edge.relation_id for e in view._edges} == {"rAC", "rBC"}


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_snapshot_honours_explicit_relation_interval(view):
    # Dos personajes longevos; su enemistad nace en el año 50.
    nodes = [_node("X", birth=0), _node("Y", birth=0)]
    edges = [_edge("enemistad", "X", "Y", birth=50)]
    view.set_graph(nodes, edges, layout_mode="free")

    view.set_view_year(10)  # ambos vivos, pero la relación aún no existe
    assert set(view._nodes.keys()) == {"X", "Y"}
    assert view._edges == []

    view.set_view_year(60)  # la relación ya existe
    assert {e.edge.relation_id for e in view._edges} == {"enemistad"}


@pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")
def test_undated_entities_never_hidden(view):
    # Entidad sin nacimiento (pre-migración) no desaparece al fotografiar.
    nodes = [_node("legacy"), _node("dated", birth=100)]
    view.set_graph(nodes, [], layout_mode="free")
    view.set_view_year(0)
    assert set(view._nodes.keys()) == {"legacy"}  # 'dated' nace en 100


# ── Click → panel (cableado) ───────────────────────────────────────────────

def test_single_click_opens_panel_on_release_not_drag():
    """El panel se abre en el release de un click (no en un drag)."""
    source = (ROOT / "hosts/DesktopHostPySide/widgets/graph_canvas.py").read_text(encoding="utf-8")
    # El press de una hoja ya NO emite (se hace en el release sin arrastre)
    assert "NO se emite aquí" in source
    # El release emite cuando el item no se movió y no está suprimido
    assert "self.entitySelected.emit(moving.node.entity_id)" in source
    # El doble click suprime el reopen ("pop ups de nuevo")
    assert "self._suppress_release_click = True" in source
    # Las relaciones también abren panel con un click simple: el press difiere
    # y el release emite, con la misma guardia de supresión que los nodos.
    assert "self._pressed_edge_id = edge.edge.relation_id" in source
    assert "self.relationSelected.emit(rel_id)" in source
