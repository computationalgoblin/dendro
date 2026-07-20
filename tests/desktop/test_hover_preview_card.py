"""BETA2-HOVER-01: tarjeta flotante de previsualización (contenido + clamp)."""

from __future__ import annotations

import pytest

try:
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.hover_preview_card import (
        HoverContent,
        HoverPreviewCard,
        HoverPreviewController,
    )


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


_LONG = (
    "Sharif es un veterano de guerra marcado por la violencia, la obediencia y la "
    "pérdida de sentido. Granada lo ha usado como arma y luego lo ha despreciado por "
    "aquello en lo que lo convirtió. Nasr le ofrece una causa donde su brutalidad tiene "
    "por fin un propósito, y esa promesa lo arrastra sin remedio."
)


class TestHoverPreviewCard:
    def test_shows_full_brief_without_elision(self, qapp):
        card = HoverPreviewCard()
        card.set_content(HoverContent(title="Sharif", meta="Personaje · Corte", brief=_LONG))
        # El QLabel del brief conserva el texto ENTERO (sin recorte ni elipsis).
        assert card._brief.text() == _LONG
        assert card._brief.wordWrap() is True

    def test_height_grows_with_longer_brief(self, qapp):
        # El alto se calcula con heightForWidth (no adjustSize): un brief largo
        # produce una tarjeta MÁS ALTA (el texto entero cabe, no se corta).
        short = HoverPreviewCard()
        short.set_content(HoverContent(title="A", brief="Una línea."))
        tall = HoverPreviewCard()
        tall.set_content(HoverContent(title="A", brief=_LONG))
        assert tall.height() > short.height() + 20

    def test_is_top_level_window(self, qapp):
        # No es hija de un viewport: es una ventana flotante (evita el artefacto de
        # repintado que blanqueaba ítems bajo el cursor al mostrar/ocultar la tarjeta).
        card = HoverPreviewCard()
        assert card.isWindow()

    def test_place_stays_inside_viewport(self, qapp):
        card = HoverPreviewCard()
        card.set_content(HoverContent(title="Nasr", brief=_LONG))
        viewport = QRect(0, 0, 900, 600)
        # ancla pegada al borde derecho: la tarjeta debe reubicarse dentro del viewport.
        anchor = QRect(880, 20, 16, 16)
        card.place(anchor, viewport)
        geo = card.geometry()
        assert geo.left() >= viewport.left()
        assert geo.top() >= viewport.top()
        assert geo.right() <= viewport.right()
        assert geo.bottom() <= viewport.bottom()

    def test_place_avoids_rect_when_possible(self, qapp):
        card = HoverPreviewCard()
        card.set_content(HoverContent(title="X", brief="breve"))
        viewport = QRect(0, 0, 900, 600)
        # chip pegado al borde derecho; el conector es una banda FINA hacia el centro.
        anchor = QRect(820, 300, 16, 16)
        avoid = QRect(450, 300, 370, 12)
        card.place(anchor, viewport, avoid=avoid)
        # debe reubicarse arriba/abajo del chip para no tapar el conector fino.
        assert not card.geometry().intersects(avoid)

    def test_fallback_portrait_without_image(self, qapp):
        card = HoverPreviewCard()
        card.set_content(HoverContent(title="Sin foto", brief="x", entity_type="personaje"))
        pix = card._portrait.pixmap()
        assert pix is not None and not pix.isNull()


class TestHoverPreviewController:
    def test_card_not_parented_to_viewport(self, qapp):
        # BETA2-HOVER (fix parpadeo): la tarjeta del controller NO cuelga del
        # viewport (ni siquiera como ventana propietaria) → mostrarla/ocultarla no
        # ensucia el backing-store del viewport y no blanquea ítems translúcidos.
        from PySide6.QtWidgets import QGraphicsView

        view = QGraphicsView()
        ctrl = HoverPreviewController(view, lambda _p: None)
        assert ctrl.card().parent() is None
        assert ctrl.card().isWindow()
