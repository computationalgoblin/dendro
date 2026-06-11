"""BETA1-B03 (ext): anidado visual, drag-mover, drop-sobre-rama y CRUD de
anillos en el canvas de Creación."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from hosts.DesktopHostPySide.widgets.graph_canvas import (
        GraphCanvasView,
        GraphTreeItem,
        _EdgeView,
        _NodeView,
    )

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def layer(layer_id: str, name: str, rank: int):
    return SimpleNamespace(id=layer_id, name=name, metadata={"causal_rank": str(rank)}, is_visible=True, order=0)


def node(entity_id: str, name: str, *, kind: str = "concepto", layer_id: str = ""):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id] if layer_id else []),
        entity_id=entity_id,
        name=name,
        kind=kind,
        subtitle="",
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


def concentric_view(qapp) -> "GraphCanvasView":
    """Ring 'mundo' holds a tree with two leaves; ring 'gente' an external leaf.
    Relations: tree↔external, tree↔own child, child↔child."""
    view = GraphCanvasView()
    layers = [layer("mundo", "Mundo", 1), layer("gente", "Gente", 2)]
    nodes = [
        node("rama-1", "Rama Uno", kind="contenedor", layer_id="mundo"),
        node("hoja-a", "Hoja A", layer_id="mundo"),
        node("hoja-b", "Hoja B", layer_id="mundo"),
        node("externa", "Externa", layer_id="gente"),
    ]
    edges = [
        edge("c1", "rama-1", "hoja-a", kind="contiene"),
        edge("c2", "rama-1", "hoja-b", kind="contiene"),
        edge("r-ext", "rama-1", "externa"),
        edge("r-int", "rama-1", "hoja-a"),
        edge("r-cc", "hoja-a", "hoja-b"),
    ]
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)
    return view


# ── Anidado visual ────────────────────────────────────────────────────────

def test_contained_leaves_nest_inside_tree_in_concentric(qapp):
    view = concentric_view(qapp)
    tree = view._trees["rama-1"]
    assert view._nodes["hoja-a"].parentItem() is tree
    assert view._nodes["hoja-b"].parentItem() is tree
    # The tree was resized beyond its minimum to hold both leaves with slack
    assert tree._width > 240 or tree._height > 120


def test_moving_tree_moves_its_content(qapp):
    view = concentric_view(qapp)
    tree = view._trees["rama-1"]
    child = view._nodes["hoja-a"]
    before = QPointF(child.scenePos())
    tree.setPos(tree.pos().x() + 300, tree.pos().y() + 150)
    after = child.scenePos()
    assert after.x() == pytest.approx(before.x() + 300)
    assert after.y() == pytest.approx(before.y() + 150)


def test_tree_relations_are_drawn(qapp):
    view = concentric_view(qapp)
    drawn = {item.edge.relation_id for item in view._edges}
    # tree↔external, tree↔own child and child↔child are visible edges;
    # 'contiene' is structural (the rectangle) and must not be a line.
    assert {"r-ext", "r-int", "r-cc"} <= drawn
    assert "c1" not in drawn and "c2" not in drawn
    # internal edges registered on the tree for collapse visibility
    tree = view._trees["rama-1"]
    internal_ids = {e.edge.relation_id for e in tree._internal_edges}
    assert {"r-int", "r-cc"} <= internal_ids


# ── Anillos reactivos ─────────────────────────────────────────────────────

def ring_of(view, ring_id):
    return next(r for r in view._ring_visuals if r.ring_id == ring_id)


def test_ring_reserves_slack_for_real_tree_size(qapp):
    view = concentric_view(qapp)
    tree = view._trees["rama-1"]
    extent = max(tree.boundingRect().width(), tree.boundingRect().height())
    ring = ring_of(view, "mundo")
    # The ring band must hold the measured tree plus slack
    assert (ring.outer_radius - ring.inner_radius) >= extent + 90.0 - 1e-6


def test_rings_react_to_collapse_and_expand(qapp):
    view = concentric_view(qapp)
    tree = view._trees["rama-1"]
    child = view._nodes["hoja-a"]
    local_before = QPointF(child.pos())
    outer_expanded = ring_of(view, "mundo").outer_radius

    tree.toggle_collapse()  # collapse → ring shrinks around smaller content
    outer_collapsed = ring_of(view, "mundo").outer_radius
    assert outer_collapsed < outer_expanded
    assert child.isVisible() is False

    tree.toggle_collapse()  # expand → content visible, same local position
    outer_back = ring_of(view, "mundo").outer_radius
    assert outer_back > outer_collapsed
    assert child.isVisible() is True
    assert child.pos().x() == pytest.approx(local_before.x())
    assert child.pos().y() == pytest.approx(local_before.y())


def test_edges_follow_moving_tree_and_nested_content(qapp):
    """Relations attached to a tree AND to its nested children must follow
    when the tree is dragged (scene-position notifications)."""
    view = concentric_view(qapp)
    tree = view._trees["rama-1"]
    ext_edge = next(e for e in view._edges if e.edge.relation_id == "r-ext")
    int_edge = next(e for e in view._edges if e.edge.relation_id == "r-cc")
    ext_before = QPointF(ext_edge.path().pointAtPercent(0.0))
    int_before = QPointF(int_edge.path().pointAtPercent(0.0))

    tree.setPos(tree.pos().x() + 400, tree.pos().y() + 200)

    ext_after = ext_edge.path().pointAtPercent(0.0)
    int_after = int_edge.path().pointAtPercent(0.0)
    assert (ext_after - ext_before).manhattanLength() > 100  # tree endpoint moved
    assert (int_after - int_before).manhattanLength() > 100  # nested endpoints moved


def test_nested_collapse_refits_parent_and_ring(qapp):
    """Collapsing a nested branch shrinks its parent container and the ring."""
    view = GraphCanvasView()
    layers = [layer("mundo", "Mundo", 1)]
    nodes = [
        node("padre", "Padre", kind="contenedor", layer_id="mundo"),
        node("sub", "Subrama", kind="contenedor", layer_id="mundo"),
        node("h1", "H1", layer_id="mundo"),
        node("h2", "H2", layer_id="mundo"),
    ]
    edges = [
        edge("c1", "padre", "sub", kind="contiene"),
        edge("c2", "sub", "h1", kind="contiene"),
        edge("c3", "sub", "h2", kind="contiene"),
    ]
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)
    padre = view._trees["padre"]
    sub = view._trees["sub"]
    assert sub.parentItem() is padre
    parent_h_before = padre._height
    ring_before = next(r for r in view._ring_visuals if r.ring_id == "mundo").outer_radius

    sub.toggle_collapse()

    assert padre._height < parent_h_before  # parent refit around collapsed sub
    ring_after = next(r for r in view._ring_visuals if r.ring_id == "mundo").outer_radius
    assert ring_after < ring_before  # ring reacted to the smaller content


def test_tree_menu_offers_relation_creation(qapp):
    view = concentric_view(qapp)
    menu = view._tree_context_menu(view._trees["rama-1"])
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert "Crear relación desde aquí" in texts


def test_tree_menu_offers_move_to_ring_and_emits(qapp):
    view = concentric_view(qapp)
    received: list[tuple[str, str]] = []
    view.nodeAssignToRingRequested.connect(lambda eid, rid: received.append((eid, rid)))

    menu = view._tree_context_menu(view._trees["rama-1"])
    ring_menu = next(a for a in menu.actions() if a.text() == "Mover a anillo").menu()

    assert ring_menu is not None
    assert [a.text() for a in ring_menu.actions()] == ["Gente"]
    ring_menu.actions()[0].trigger()
    assert received == [("rama-1", "gente")]


# ── Drag-mover y drop sobre rama ──────────────────────────────────────────

def _press(pos=QPointF(1.0, 1.0)):
    return QMouseEvent(
        QEvent.Type.MouseButtonPress, pos, pos, pos,
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_plain_press_on_node_starts_move_not_relation(qapp, monkeypatch):
    view = concentric_view(qapp)
    item = view._nodes["externa"]
    monkeypatch.setattr(view, "_item_node_at", lambda pos: item)
    view.mousePressEvent(_press())
    assert view._moving_item is item
    assert view._drag_source is None  # no relation drag on plain press


def test_drop_on_tree_emits_assignment(qapp, monkeypatch):
    view = concentric_view(qapp)
    moved = view._nodes["externa"]
    tree = view._trees["rama-1"]
    received: list[tuple[str, str]] = []
    view.nodeAssignToTreeRequested.connect(lambda s, t: received.append((s, t)))
    monkeypatch.setattr(view, "_drop_tree_target", lambda m, p: tree)
    view._handle_move_drop(moved, QPointF(0, 0))
    assert received == [("externa", "rama-1")]


def test_drop_on_current_tree_is_a_rearrange_not_reassign(qapp, monkeypatch):
    view = concentric_view(qapp)
    moved = view._nodes["hoja-a"]  # already inside rama-1
    tree = view._trees["rama-1"]
    received: list[tuple[str, str]] = []
    view.nodeAssignToTreeRequested.connect(lambda s, t: received.append((s, t)))
    monkeypatch.setattr(view, "_drop_tree_target", lambda m, p: tree)
    view._handle_move_drop(moved, QPointF(0, 0))
    assert received == []  # membership unchanged


def test_drop_target_excludes_own_ancestors(qapp):
    view = concentric_view(qapp)
    moved = view._nodes["hoja-a"]
    # items() under an arbitrary point may return the parent tree; the
    # ancestor exclusion means a child dragged within its tree finds no target
    target = view._drop_tree_target(moved, QPointF(1.0, 1.0))
    assert target is None or target is not moved.parentItem()


# ── Extracción por arrastre y anillos envolventes ─────────────────────────

def test_drag_out_of_tree_emits_extraction(qapp, monkeypatch):
    view = concentric_view(qapp)
    child = view._nodes["hoja-a"]  # nested inside rama-1
    extracted: list[str] = []
    view.nodeExtractFromTreeRequested.connect(extracted.append)
    monkeypatch.setattr(view, "_drop_tree_target", lambda m, p: None)
    # drop point far outside the parent's rectangle
    monkeypatch.setattr(view, "mapToScene", lambda p: QPointF(99999.0, 99999.0))
    view._handle_move_drop(child, QPointF(0, 0))
    assert extracted == ["hoja-a"]


def test_drop_inside_parent_is_rearrange_not_extraction(qapp, monkeypatch):
    view = concentric_view(qapp)
    child = view._nodes["hoja-a"]
    parent = view._trees["rama-1"]
    extracted: list[str] = []
    view.nodeExtractFromTreeRequested.connect(extracted.append)
    monkeypatch.setattr(view, "_drop_tree_target", lambda m, p: None)
    inside = parent.mapRectToScene(parent.rect()).center()
    monkeypatch.setattr(view, "mapToScene", lambda p: QPointF(inside))
    view._handle_move_drop(child, QPointF(0, 0))
    assert extracted == []


def test_ring_spans_wrap_items_after_manual_move(qapp):
    view = concentric_view(qapp)
    leaf = view._nodes["externa"]  # top-level in ring 'gente'
    leaf.setPos(5000.0, 0.0)  # user drags it far out
    view._refresh_ring_spans()
    ring = ring_of(view, "gente")
    rect = leaf.sceneBoundingRect()
    distance = (rect.center().x() ** 2 + rect.center().y() ** 2) ** 0.5
    assert ring.outer_radius >= distance  # the band stretched to wrap it
    # and items were NOT repositioned by the span refresh
    assert leaf.pos().x() == pytest.approx(5000.0)


# ── CRUD de anillos desde menú ────────────────────────────────────────────

def test_ring_menu_offers_crud_and_emits(qapp):
    view = concentric_view(qapp)
    received: dict[str, str] = {}
    view.ringEditRequested.connect(lambda rid: received.__setitem__("edit", rid))
    view.ringDeleteRequested.connect(lambda rid: received.__setitem__("delete", rid))
    view.ringCreateRequested.connect(lambda: received.__setitem__("create", "yes"))

    menu = view._ring_context_menu(view._ring_items["mundo"])
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert texts == [
        "Crear hoja en este anillo",
        "Crear rama en este anillo",
        "Editar anillo…",
        "Crear anillo…",
        "Eliminar anillo",
    ]
    next(a for a in menu.actions() if a.text() == "Editar anillo…").trigger()
    next(a for a in menu.actions() if a.text() == "Eliminar anillo").trigger()
    next(a for a in menu.actions() if a.text() == "Crear anillo…").trigger()
    assert received == {"edit": "mundo", "delete": "mundo", "create": "yes"}


def test_unclassified_ring_has_no_crud(qapp):
    view = GraphCanvasView()
    layers = [layer("mundo", "Mundo", 1)]
    nodes = [node("suelta", "Suelta")]  # no layer → unclassified ring
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    ring_item = view._ring_items.get("__unclassified__")
    assert ring_item is not None
    menu = view._ring_context_menu(ring_item)
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert "Editar anillo…" not in texts and "Eliminar anillo" not in texts


def test_background_menu_offers_ring_creation_in_concentric(qapp):
    view = concentric_view(qapp)
    menu = view._background_context_menu()
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert texts == ["Crear hoja aquí", "Crear rama aquí", "Crear anillo…"]
