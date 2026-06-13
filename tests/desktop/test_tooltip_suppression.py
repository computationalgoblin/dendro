from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QPainterPath
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_tooltip_suppressor_blocks_tooltip_events(qapp):
    from hosts.DesktopHostPySide.widgets.tooltip_suppression import install_tooltip_suppression

    first = install_tooltip_suppression(qapp)
    second = install_tooltip_suppression(qapp)

    assert first is second
    assert first.eventFilter(qapp, QEvent(QEvent.Type.ToolTip)) is True
    assert first.eventFilter(qapp, QEvent(QEvent.Type.KeyPress)) is False


def test_creation_canvas_items_do_not_define_tooltips(qapp):
    from hosts.DesktopHostPySide.widgets.graph_canvas import (
        _EdgeView,
        _NodeView,
        _RingVisual,
        GraphEdgeItem,
        GraphNodeItem,
        GraphRingItem,
        GraphTreeItem,
    )

    leaf = _NodeView(
        entity=SimpleNamespace(),
        entity_id="leaf-1",
        name="Devian",
        kind="personaje",
        subtitle="Resumen",
        canon="canon",
        visibility="publico",
    )
    tree = _NodeView(
        entity=SimpleNamespace(),
        entity_id="branch-1",
        name="Hermandad",
        kind="contenedor",
        subtitle="Rama",
        canon="canon",
        visibility="publico",
    )
    node_item = GraphNodeItem(leaf, x=0, y=0)
    tree_item = GraphTreeItem(tree, x=160, y=0)
    edge_item = GraphEdgeItem(
        _EdgeView(
            relation=SimpleNamespace(),
            relation_id="rel-1",
            source_id="leaf-1",
            target_id="branch-1",
            kind="pertenece_a",
            label="pertenece",
        ),
        node_item,
        tree_item,
    )
    ring_item = GraphRingItem(
        _RingVisual(
            ring_id="ring-root",
            display_name="Anillo raiz",
            causal_rank=1,
            color="#ffffff",
            inner_radius=0,
            outer_radius=100,
        ),
        QPainterPath(),
    )

    assert node_item.toolTip() == ""
    assert tree_item.toolTip() == ""
    assert edge_item.handle_item.toolTip() == ""
    assert ring_item.toolTip() == ""
