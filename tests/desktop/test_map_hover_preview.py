"""BETA2-HOVER-04: previsualización flotante al hover en el mapa."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _node(name="Sharif", kind="personaje", brief="", image="", subtitle=""):
    return SimpleNamespace(
        entity=SimpleNamespace(brief_description=brief),
        name=name, kind=kind, color="#8B7A36", image_path=image, image_crop=None,
        subtitle=subtitle,
    )


class TestMapHoverPreview:
    def test_node_content_full_brief(self, qapp):
        view = GraphCanvasView()
        long_brief = "palabra " * 60
        content = view._node_hover_content(_node(brief=long_brief, image="p.png"))
        assert content is not None
        assert content.title == "Sharif"
        assert content.brief == long_brief  # entero (de la entidad, no el subtitle)
        assert content.kind == "entidad"
        assert content.image_path == "p.png"

    def test_branch_node_is_rama(self, qapp):
        view = GraphCanvasView()
        content = view._node_hover_content(_node(name="Casa", kind="contenedor", brief="una casa"))
        assert content.kind == "rama"

    def test_falls_back_to_subtitle_brief(self, qapp):
        view = GraphCanvasView()
        content = view._node_hover_content(_node(brief="", subtitle="desde subtitle"))
        assert content.brief == "desde subtitle"

    def test_ring_content(self, qapp):
        view = GraphCanvasView()
        ring = SimpleNamespace(display_name="Interior", count_label="3 entidades", color="#8B7A36")
        content = view._ring_hover_content(ring)
        assert content is not None
        assert content.kind == "anillo"
        assert content.title == "Interior"
        assert content.brief == "3 entidades"

    def test_resolver_dispatches_node_over_ring(self, qapp):
        view = GraphCanvasView()
        node_item = SimpleNamespace(node=_node(name="N", brief="d"))
        view._item_node_at = lambda _p: node_item
        view._item_ring_at = lambda _p: None
        content = view._hover_content_at(QPointF(1, 1))
        assert content is not None and content.title == "N"

    def test_resolver_none_over_empty(self, qapp):
        view = GraphCanvasView()
        view._item_node_at = lambda _p: None
        view._item_ring_at = lambda _p: None
        assert view._hover_content_at(QPointF(1, 1)) is None

    def test_hit_testers_accept_qpoint(self, qapp):
        # BETA2-HOVER-08: los hit-testers aceptan QPoint (el controller de hover pasa
        # QPoint). Antes asumían QPointF y ``.toPoint()`` petaba → tarjeta invisible.
        from PySide6.QtCore import QPoint

        view = GraphCanvasView()
        assert view._item_node_at(QPoint(5, 5)) is None
        assert view._item_ring_at(QPoint(5, 5)) is None
