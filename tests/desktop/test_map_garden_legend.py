"""Mini-leyenda del jardín en el Mapa (BETA2-PULIDO-06)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication, QLabel

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _widget(qapp):
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget

    project = SimpleNamespace(world_layers=[], entities=[], relations=[])
    ctx = SimpleNamespace(
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
        advanced_mode=False,
        creation_layout_mode="concentric_rings",
        creation_focused_ring_id="",
        selected_entity_id="",
        save_preferences=lambda: None,
        log=lambda *args, **kwargs: None,
    )
    widget = GraphCanvasWidget(ctx)
    widget.resize(1200, 800)
    return widget


class TestGardenLegend:
    def test_collapsed_by_default_and_parented(self, qapp):
        widget = _widget(qapp)
        legend = widget.garden_legend
        assert legend.parentWidget() is widget  # guard de parenting de la casa
        assert legend.expanded is False
        assert legend._card.isHidden()  # plegada: solo el punto ❀
        widget.deleteLater()

    def test_expand_shows_the_real_garden_language(self, qapp):
        widget = _widget(qapp)
        legend = widget.garden_legend
        legend.set_expanded(True)
        assert legend.expanded is True
        assert not legend._card.isHidden()
        texts = " ".join(label.text() for label in legend._card.findChildren(QLabel))
        for needle in ("por regar", "secada", "iluminada", "contenido débil", "arraigo"):
            assert needle in texts
        legend.set_expanded(False)
        assert legend._card.isHidden()
        widget.deleteLater()

    def test_expand_explains_rings_and_seeds(self, qapp):
        # WS-D: además del riego, la leyenda enseña las metáforas del Mapa que un
        # usuario nuevo no puede deducir de un lienzo vacío: anillos y semillas.
        widget = _widget(qapp)
        legend = widget.garden_legend
        legend.set_expanded(True)
        texts = " ".join(label.text() for label in legend._card.findChildren(QLabel))
        assert "Anillos" in texts and "potencia causal" in texts
        assert "Semillas" in texts
        assert "Regar" in texts
        # Sigue siendo de solo lectura: no añadimos botones, solo etiquetas.
        from PySide6.QtWidgets import QPushButton

        assert legend.findChildren(QPushButton) == [legend._toggle]
        widget.deleteLater()

    def test_anchored_bottom_right_after_resize(self, qapp):
        # UI2-02: la leyenda vive abajo-DERECHA (el cluster izquierdo la solapaba).
        widget = _widget(qapp)
        widget._position_garden_legend()
        legend = widget.garden_legend
        assert legend.geometry().right() == widget.width() - 12 - 1
        assert legend.geometry().bottom() <= widget.height()
        widget.resize(900, 600)
        widget._position_garden_legend()
        assert legend.geometry().bottom() <= widget.height()
        assert legend.geometry().right() == widget.width() - 12 - 1
        widget.deleteLater()

    def test_legend_respects_bottom_inset(self, qapp):
        # UI2-02: el workspace reserva hueco para las píldoras 🌱/💧 con
        # set_garden_legend_bottom_inset; la leyenda queda apilada encima.
        widget = _widget(qapp)
        legend = widget.garden_legend
        widget.set_garden_legend_bottom_inset(80)
        assert legend.geometry().bottom() <= widget.height() - 80
        widget.set_garden_legend_bottom_inset(0)
        assert legend.geometry().bottom() <= widget.height() - 12
        widget.deleteLater()

    def test_legend_is_read_only(self, qapp):
        # Ningún control de la leyenda emite señales de mutación: solo el
        # toggle de visibilidad existe como botón.
        widget = _widget(qapp)
        legend = widget.garden_legend
        from PySide6.QtWidgets import QPushButton

        buttons = legend.findChildren(QPushButton)
        assert buttons == [legend._toggle]
        widget.deleteLater()
