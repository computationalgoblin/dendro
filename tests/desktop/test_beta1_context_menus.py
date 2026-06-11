"""BETA1-B01: context menus on the Creation canvas.

These tests build the menus directly via the testable seams
(_node_context_menu, _tree_context_menu, ...) instead of exec()-ing them,
so no real popup is shown. Signal wiring is verified by triggering actions.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from PySide6.QtCore import QPointF
    from hosts.DesktopHostPySide.widgets.graph_canvas import (
        GraphCanvasView,
        _EdgeView,
        _NodeView,
    )


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def layer(layer_id: str, name: str, rank: int | None, *, visible: bool = True):
    metadata = {} if rank is None else {"causal_rank": str(rank)}
    return SimpleNamespace(id=layer_id, name=name, metadata=metadata, is_visible=visible, order=0)


def node(entity_id: str, name: str, *, kind: str = "concepto", layer_id: str = ""):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id] if layer_id else []),
        entity_id=entity_id,
        name=name,
        kind=kind,
        subtitle=f"Descripción de {name}",
        canon="canonico",
        visibility="publico",
        layer_id=layer_id,
    )


def edge(relation_id: str, source_id: str, target_id: str, kind: str = "deriva_de"):
    return _EdgeView(
        relation=SimpleNamespace(id=relation_id),
        relation_id=relation_id,
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        label=kind.replace("_", " "),
    )


def action_texts(menu) -> list[str]:
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def build_basic_view(qapp) -> "GraphCanvasView":
    view = GraphCanvasView()
    nodes = [
        node("hoja-1", "Hoja Uno"),
        node("hoja-2", "Hoja Dos"),
        node("rama-1", "Rama Uno", kind="contenedor"),
        node("rama-2", "Rama Dos", kind="contenedor"),
    ]
    edges = [edge("rel-1", "hoja-1", "hoja-2")]
    view.set_graph(nodes, edges)
    return view


def test_background_menu_offers_creation(qapp):
    view = GraphCanvasView()
    view.set_graph([], [])
    menu = view._build_context_menu(QPointF(5.0, 5.0))
    assert menu is not None
    assert action_texts(menu) == ["Crear hoja aquí", "Crear rama aquí"]


def test_node_menu_has_full_action_set(qapp):
    view = build_basic_view(qapp)
    item = view._nodes["hoja-1"]
    menu = view._node_context_menu(item)
    texts = action_texts(menu)
    assert texts == [
        "Editar",
        "Crear relación desde aquí",
        "Mover a rama",
        "Mover a anillo",
        "Eliminar",
    ]
    # 'Mover a anillo' has no route until B03 → must be disabled, not crash
    ring_action = next(a for a in menu.actions() if a.text() == "Mover a anillo")
    assert ring_action.isEnabled() is False
    # 'Mover a rama' lists both trees
    move_menu = next(a for a in menu.actions() if a.text() == "Mover a rama").menu()
    assert sorted(a.text() for a in move_menu.actions()) == ["Rama Dos", "Rama Uno"]


def test_tree_menu_has_tree_actions(qapp):
    view = build_basic_view(qapp)
    item = view._nodes["rama-1"]
    menu = view._tree_context_menu(item)
    assert action_texts(menu) == [
        "Editar",
        "Crear hoja dentro",
        "Crear subrama",
        "Eliminar",
    ]


def test_edge_menu_has_relation_actions(qapp):
    view = build_basic_view(qapp)
    item = view._edges[0]
    menu = view._edge_context_menu(item)
    assert action_texts(menu) == ["Editar relación", "Eliminar relación"]


def test_ring_menu_offers_ring_creation(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1), layer("politica", "Política", 5)]
    nodes = [node("m1", "M1", layer_id="metafisica"), node("p1", "P1", layer_id="politica")]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    ring_item = view._ring_items["metafisica"]
    menu = view._ring_context_menu(ring_item)
    assert action_texts(menu) == [
        "Crear hoja en este anillo",
        "Crear rama en este anillo",
    ]


def test_node_actions_emit_existing_signals(qapp):
    view = build_basic_view(qapp)
    item = view._nodes["hoja-1"]
    received: dict[str, object] = {}
    view.entitySelected.connect(lambda eid: received.__setitem__("edit", eid))
    view.contextDeleteRequested.connect(lambda: received.__setitem__("delete", True))
    view.nodeAssignToTreeRequested.connect(
        lambda eid, tid: received.__setitem__("assign", (eid, tid))
    )

    menu = view._node_context_menu(item)
    next(a for a in menu.actions() if a.text() == "Editar").trigger()
    next(a for a in menu.actions() if a.text() == "Eliminar").trigger()
    move_menu = next(a for a in menu.actions() if a.text() == "Mover a rama").menu()
    next(a for a in move_menu.actions() if a.text() == "Rama Uno").trigger()

    assert received["edit"] == "hoja-1"
    assert received["delete"] is True
    assert received["assign"] == ("hoja-1", "rama-1")


def test_tree_actions_emit_context_creation_signals(qapp):
    view = build_basic_view(qapp)
    item = view._nodes["rama-1"]
    received: dict[str, str] = {}
    view.contextCreateEntityInTreeRequested.connect(
        lambda tid: received.__setitem__("leaf_in", tid)
    )
    view.contextCreateSubtreeRequested.connect(
        lambda tid: received.__setitem__("subtree_in", tid)
    )

    menu = view._tree_context_menu(item)
    next(a for a in menu.actions() if a.text() == "Crear hoja dentro").trigger()
    next(a for a in menu.actions() if a.text() == "Crear subrama").trigger()

    assert received["leaf_in"] == "rama-1"
    assert received["subtree_in"] == "rama-1"


def test_ring_creation_selects_ring_before_emitting(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1), layer("politica", "Política", 5)]
    nodes = [node("m1", "M1", layer_id="metafisica"), node("p1", "P1", layer_id="politica")]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    events: list[str] = []
    view.contextCreateEntityRequested.connect(lambda: events.append("create"))

    menu = view._ring_context_menu(view._ring_items["politica"])
    next(a for a in menu.actions() if a.text() == "Crear hoja en este anillo").trigger()

    # The ring becomes active first so the existing creation route lands there
    assert view.active_ring_id() == "politica"
    assert events == ["create"]


def _press_event():
    """Synthetic left-press: the BETA1-B01 early branch accepts and returns
    before touching Qt internals, so a lightweight stand-in is enough."""
    from PySide6.QtCore import Qt
    return SimpleNamespace(
        button=lambda: Qt.MouseButton.LeftButton,
        position=lambda: QPointF(1.0, 1.0),
        accept=lambda: None,
    )


def test_context_relation_completes_on_next_click_target(qapp, monkeypatch):
    view = build_basic_view(qapp)
    source = view._nodes["hoja-1"]
    target = view._nodes["hoja-2"]
    results: list[tuple[str, str]] = []
    view.relationCreateRequested.connect(lambda s, t: results.append((s, t)))

    view._begin_context_relation(source)
    assert view._drag_source is source
    assert view._pending_source is None  # precondition of the early branch

    monkeypatch.setattr(view, "_item_node_at", lambda pos: target)
    view.mousePressEvent(_press_event())

    assert results == [("hoja-1", "hoja-2")]
    assert view._drag_source is None  # drag state fully cleared


def test_context_relation_cancels_on_background_click(qapp, monkeypatch):
    view = build_basic_view(qapp)
    source = view._nodes["hoja-1"]
    rejections: list[str] = []
    view.relationCreateRejected.connect(rejections.append)

    view._begin_context_relation(source)
    monkeypatch.setattr(view, "_item_node_at", lambda pos: None)
    view.mousePressEvent(_press_event())

    assert rejections == ["Relación cancelada"]
    assert view._drag_source is None


def test_ring_creation_wins_over_focused_ring(qapp):
    """Regression (B02): right-clicked ring must win even if another ring
    holds focus — active_ring_id prefers focus, so the context creation uses
    a one-shot override while the route runs."""
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1), layer("politica", "Política", 5)]
    nodes = [node("m1", "M1", layer_id="metafisica"), node("p1", "P1", layer_id="politica")]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    view.focus_ring_scope("metafisica")  # stale focus on another ring

    seen: list[str] = []
    # The workspace creation route runs synchronously inside this emit, so
    # whatever active_ring_id() returns here is what creation would use.
    view.contextCreateEntityRequested.connect(lambda: seen.append(view.active_ring_id()))
    menu = view._ring_context_menu(view._ring_items["politica"])
    next(a for a in menu.actions() if a.text() == "Crear hoja en este anillo").trigger()

    assert seen == ["politica"]
    assert view._context_ring_override == ""  # one-shot, cleared afterwards


def test_scene_rect_covers_full_concentric_layout(qapp):
    """Regression (B02): the scene rect must contain the whole layout so
    panning can reach the outer rings."""
    view = GraphCanvasView()
    layers = [layer(f"l{i}", f"Capa {i}", i) for i in range(1, 9)]
    nodes = [node(f"n{i}", f"N{i}", layer_id=f"l{i}") for i in range(1, 9)]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)

    scene_rect = view.scene_obj.sceneRect()
    content = view.scene_obj.itemsBoundingRect()
    assert scene_rect.contains(content)


def test_move_targets_exclude_self_and_cycles(qapp):
    view = build_basic_view(qapp)
    # rama-2 must not offer itself as target
    targets = view._context_target_trees(exclude_id="rama-2")
    ids = [tid for tid, _ in targets]
    assert "rama-2" not in ids
    assert "rama-1" in ids
