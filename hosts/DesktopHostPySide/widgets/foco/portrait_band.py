"""UI2-06: banda vertical de retrato de la tarjeta central del Foco.

Antes vivía dentro de NodeDetailPanel (variant foco); ahora es de la TARJETA
(FocoView) para que el retrato quede siempre visible a la izquierda, en todas
las pestañas (Ficha / Relaciones / Cultivo).

Pinta el encuadre proyectado a rectángulo vertical (mismo centro/zoom que el
recorte canónico) con esquinas redondeadas y un degradado suave hacia la
superficie de la tarjeta en el borde interno. Sin retrato se oculta y el
layout queda como si no existiera. Sin QGraphicsEffect (regla del repo).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from hosts.DesktopHostPySide.widgets import portrait_cache
from hosts.DesktopHostPySide.widgets.design_system import SURFACE_HI


class PortraitBand(QWidget):
    """Banda de retrato a todo el alto de la tarjeta (oculta sin imagen)."""

    _WIDTH = 160
    _RADIUS = 14.0
    _FADE = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = None
        self._crop = None
        self.setFixedWidth(self._WIDTH)
        self.setVisible(False)

    def set_portrait(self, source, crop):
        self._source = source
        self._crop = crop
        self.setVisible(source is not None)
        self.update()

    def paintEvent(self, event):  # noqa: N802 (Qt signature)
        if self._source is None:
            return
        pixmap = portrait_cache.portrait_band_pixmap(
            self._source, self._crop, self.width(), self.height()
        )
        if pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), self._RADIUS, self._RADIUS)
        painter.setClipPath(clip)
        painter.drawPixmap(self.rect(), pixmap)
        # Degradado hacia la superficie de la tarjeta en el borde interno.
        fade = QLinearGradient(self.width() - self._FADE, 0, self.width(), 0)
        transparent = QColor(SURFACE_HI)
        transparent.setAlpha(0)
        solid = QColor(SURFACE_HI)
        solid.setAlpha(220)
        fade.setColorAt(0.0, transparent)
        fade.setColorAt(1.0, solid)
        painter.fillRect(self.width() - self._FADE, 0, self._FADE, self.height(), fade)
        painter.end()


__all__ = ["PortraitBand"]
