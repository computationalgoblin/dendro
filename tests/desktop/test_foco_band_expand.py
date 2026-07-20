"""BETA2-HOVER-02: el chip de banda del Foco NO se expande; el detalle va a la
tarjeta flotante de hover (con la descripción breve ENTERA)."""

from __future__ import annotations

import pytest

try:
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.foco.foco_canvas import (
        _BAND_CHIP_H,
        _BAND_CHIP_W,
        FocoBandItem,
        FocoCanvas,
    )


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


_LONG = "palabra " * 80  # descripción larga: antes se cortaba por el clip del chip


class TestFocoBandNoExpand:
    def test_chip_rect_is_fixed_for_all_bands(self, qapp):
        for band in ("top", "bottom", "right"):
            item = FocoBandItem("e1", "N", "personaje", brief=_LONG, band=band)
            rect = item._chip_rect()
            assert rect.width() == pytest.approx(_BAND_CHIP_W)
            assert rect.height() == pytest.approx(_BAND_CHIP_H)

    def test_no_expansion_api_remains(self, qapp):
        item = FocoBandItem("e1", "N", "personaje", band="right")
        assert not hasattr(item, "_expanded_size")
        assert not hasattr(item, "_band_height_cap")
        assert not hasattr(item, "_expanded")

    def test_canvas_uses_full_viewport_update(self, qapp):
        # BETA2-HOVER-07: repintado completo (como la cronología) para que los chips
        # a baja opacidad no queden en blanco al mostrar/ocultar el conector.
        from PySide6.QtWidgets import QGraphicsView

        canvas = FocoCanvas()
        assert canvas.viewportUpdateMode() == QGraphicsView.ViewportUpdateMode.FullViewportUpdate


class TestFocoHoverResolver:
    def _canvas_with_item(self, band="right"):
        canvas = FocoCanvas()
        canvas.resize(1000, 700)
        item = FocoBandItem(
            "e1", "Sharif", "personaje", brief=_LONG, ring_name="Corte", nature="Hoja", band=band
        )
        canvas._scene.addItem(item)
        item.setPos(820.0, 300.0)
        return canvas, item

    def test_resolver_returns_full_brief(self, qapp):
        canvas, item = self._canvas_with_item()
        canvas.itemAt = lambda _p, it=item: it
        content = canvas._hover_content_at(QPoint(10, 10))
        assert content is not None
        assert content.title == "Sharif"
        # descripción ENTERA (sin recorte)
        assert content.brief == _LONG
        assert "Corte" in content.meta
        assert content.anchor_rect is not None
        assert content.avoid_rect is not None  # esquiva el conector

    def test_resolver_skips_ghost(self, qapp):
        canvas = FocoCanvas()
        canvas.resize(1000, 700)
        ghost = FocoBandItem("g", "Fantasma", "personaje", brief="x", is_ghost=True, band="right")
        canvas._scene.addItem(ghost)
        ghost.setPos(820.0, 300.0)
        canvas.itemAt = lambda _p, it=ghost: it
        assert canvas._hover_content_at(QPoint(10, 10)) is None

    def test_resolver_none_over_empty(self, qapp):
        canvas = FocoCanvas()
        canvas.resize(1000, 700)
        canvas.itemAt = lambda _p: None
        assert canvas._hover_content_at(QPoint(10, 10)) is None
