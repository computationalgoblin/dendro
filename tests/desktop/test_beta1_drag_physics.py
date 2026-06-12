"""BETA1-C04: drag/drop con física — hojas, ramas, hijos, anillos.

Casos del ticket C04 sobre motor puro + bridge. La pausa de física durante
drag es GLOBAL (opción permitida por el contrato §4.5).
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from packages.ui.graph_physics import (
    Body,
    PhysicsEngine,
    Spring,
    resolve_effective_ring_id,
)

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from PySide6.QtCore import QPointF
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, _EdgeView, _NodeView


pytest_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    if not HAS_QT:
        return None
    return QApplication.instance() or QApplication([])


def _layer(layer_id, name, rank):
    return SimpleNamespace(id=layer_id, name=name, metadata={"causal_rank": str(rank)}, is_visible=True, order=0)


def _node(entity_id, name, layer_id="", kind="concepto"):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id] if layer_id else []),
        entity_id=entity_id, name=name, kind=kind, subtitle="",
        canon="canonico", visibility="publico", layer_id=layer_id,
    )


def _edge(relation_id, a, b, kind="deriva_de"):
    return _EdgeView(
        relation=SimpleNamespace(id=relation_id),
        relation_id=relation_id, source_id=a, target_id=b,
        kind=kind, label=kind,
    )


def physics_view(qapp) -> "GraphCanvasView":
    """Caso 1 del ticket: rama 'hermandad' en Política con 'devian' dentro;
    'akshan' fuera, relación devian↔akshan; física activa."""
    view = GraphCanvasView()
    layers = [_layer("metafisica", "Metafísica", 1), _layer("politica", "Política", 3)]
    nodes = [
        _node("hermandad", "Hermandad", "politica", kind="contenedor"),
        _node("devian", "Devian"),  # sin capa: hereda Política de la rama
        _node("akshan", "Akshan", "metafisica"),
    ]
    edges = [
        _edge("c1", "hermandad", "devian", kind="contiene"),
        _edge("r1", "devian", "akshan"),
    ]
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)
    view.set_physics_enabled(True)
    return view


# ── Caso 1: la relación externa no expulsa al hijo de su anillo ──────────

@pytest_qt
def test_external_relation_does_not_expel_nested_leaf(qapp):
    view = physics_view(qapp)
    # devian está anidado → NO es cuerpo simulable; su rama sí
    assert "devian" not in view._physics_engine.bodies
    assert "hermandad" in view._physics_engine.bodies
    # el muelle devian↔akshan se mapea a los top-level (hermandad↔akshan)
    spring = view._physics_engine.springs[0]
    assert {spring.a, spring.b} == {"hermandad", "akshan"}
    # simular: la rama jamás abandona su banda de Política
    band = view._physics_engine.bodies["hermandad"]
    for _ in range(200):
        view._physics_engine.step()
    dist = math.hypot(band.x, band.y)
    assert band.band_inner <= dist <= band.band_outer


# ── Drag en vivo y sin pins permanentes ───────────────────────────────────

@pytest_qt
def test_drag_pins_moved_body_and_release_leaves_no_pins(qapp):
    """C05 (revisión): la física actúa DURANTE el arrastre. El cuerpo en
    mano va pinned y sincronizado con el cursor; el resto sigue simulando.
    Al soltar, ningún pin sobrevive."""
    view = physics_view(qapp)
    view._moving_item = view._nodes["akshan"]
    view._physics_tick()
    assert view._physics_engine.bodies["akshan"].pinned is True  # lo lleva el usuario
    # el cuerpo pinned sigue al item, no a la simulación
    center = view._nodes["akshan"].sceneBoundingRect().center()
    body = view._physics_engine.bodies["akshan"]
    assert (body.x, body.y) == (center.x(), center.y())
    # soltar: adopta posición y reanuda sin pins
    view._moving_item = None
    view._physics_engine.sync_position("akshan", center.x(), center.y())
    view._physics_reheat()
    assert view._physics_timer.isActive() is True
    assert all(b.pinned is False for b in view._physics_engine.bodies.values())


# ── Caso 2: soltar fuera del anillo → vuelve a su corona ─────────────────

def test_drop_outside_band_returns_to_corona():
    engine = PhysicsEngine(repulsion=0.0)
    body = Body("n", 300.0, 0.0, target_radius=300.0, band_inner=250.0, band_outer=380.0)
    engine.set_world([body], [])
    engine.sync_position("n", 1500.0, 0.0)  # drop lejos, sin acción explícita
    for _ in range(120):
        engine.step()
    dist = math.hypot(engine.bodies["n"].x, engine.bodies["n"].y)
    assert 250.0 <= dist <= 380.0  # volvió a Política


# ── Drag mantiene ring id ─────────────────────────────────────────────────

@pytest_qt
def test_drag_does_not_change_ring_assignment(qapp):
    view = physics_view(qapp)
    before = dict(view._node_ring_ids)
    item = view._nodes["akshan"]
    item.setPos(item.pos().x() + 900, item.pos().y() + 400)  # arrastre manual
    assert view._node_ring_ids == before  # solo acción explícita cambia anillo
    assert view._physics_effective_ring("akshan") == "metafisica"


# ── Casos 4 y 5: cambio de anillo de rama, herencia y explícitos ─────────

def test_branch_ring_change_moves_inherited_children():
    explicit = {"rama": "politica"}
    membership = {"hoja": "rama"}
    assert resolve_effective_ring_id("hoja", explicit_ring_ids=explicit, membership=membership) == "politica"
    explicit["rama"] = "cultura"  # cambio explícito de anillo de la rama
    assert resolve_effective_ring_id("hoja", explicit_ring_ids=explicit, membership=membership) == "cultura"


def test_explicit_child_keeps_its_ring_when_branch_moves():
    explicit = {"rama": "politica", "hoja": "metafisica"}
    membership = {"hoja": "rama"}
    assert resolve_effective_ring_id("hoja", explicit_ring_ids=explicit, membership=membership) == "metafisica"
    explicit["rama"] = "cultura"
    assert resolve_effective_ring_id("hoja", explicit_ring_ids=explicit, membership=membership) == "metafisica"


# ── Caso 3: cambio explícito de anillo de hoja recoloca su target ────────

@pytest_qt
def test_explicit_ring_change_updates_physics_target(qapp):
    view = GraphCanvasView()
    layers = [_layer("metafisica", "Metafísica", 1), _layer("politica", "Política", 3)]
    nodes = [_node("a", "A", "metafisica"), _node("b", "B", "politica")]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    view.set_physics_enabled(True)
    target_meta = view._physics_engine.bodies["a"].target_radius
    # cambio explícito: la ruta de aplicación refresca el grafo (simulado
    # con un set_graph con la capa nueva), y el reheat re-empaqueta
    nodes2 = [_node("a", "A", "politica"), _node("b", "B", "politica")]
    view.set_graph(nodes2, [], layout_mode="concentric_rings", layers=layers)
    target_pol = view._physics_engine.bodies["a"].target_radius
    assert target_pol != target_meta  # nuevo target radius


# ── Aristas refrescadas tras ticks de física ──────────────────────────────

@pytest_qt
def test_edges_follow_physics_movement(qapp):
    view = GraphCanvasView()
    view.set_graph(
        [_node("a", "A"), _node("b", "B")],
        [_edge("r", "a", "b")],
    )
    view.set_physics_enabled(True)
    edge_item = view._edges[0]
    start_before = QPointF(edge_item.path().pointAtPercent(0.0))
    node_before = QPointF(view._nodes["a"].scenePos())
    for _ in range(15):
        view._physics_tick()
    node_after = view._nodes["a"].scenePos()
    if (node_after - node_before).manhattanLength() > 1.0:
        start_after = edge_item.path().pointAtPercent(0.0)
        assert (start_after - start_before).manhattanLength() > 0.0  # sin aristas flotantes
