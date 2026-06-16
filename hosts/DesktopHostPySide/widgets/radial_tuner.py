"""RadialTuner — a fill-on-drag circular control (Fase 3).

A small circle that fills/empties when the user presses and drags vertically
(up = fill, down = empty), rendered in a characteristic accent colour. Used for
the two command-bar tuners: temperature (Lógica↔Creatividad) and max_tokens
(Extensión). Each carries a per-function recommended default but stays editable.

The drag→value math is factored into pure module functions so it can be unit
tested without a QApplication.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from hosts.DesktopHostPySide.widgets.design_system import GOLD, INK_SOFT, LINE, SURFACE

# --- pure helpers (testable without Qt) ------------------------------------

def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def drag_to_fraction(start_fraction: float, dy_pixels: float, span_pixels: float) -> float:
    """New fill fraction after dragging.

    *dy_pixels* is (press_y - current_y): positive when the pointer moved UP, so
    the fill grows. Dragging a full *span_pixels* covers the whole 0..1 range.
    """
    span = max(1.0, float(span_pixels))
    return clamp01(float(start_fraction) + float(dy_pixels) / span)


def fraction_from_value(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 0.0
    return clamp01((float(value) - minimum) / (maximum - minimum))


def value_from_fraction(fraction: float, minimum: float, maximum: float) -> float:
    return minimum + clamp01(fraction) * (maximum - minimum)


# --- widget ----------------------------------------------------------------

class RadialTuner(QWidget):
    """A circular fill control. Emits valueChanged(float) in [minimum, maximum]."""

    valueChanged = Signal(float)

    def __init__(
        self,
        *,
        minimum: float,
        maximum: float,
        value: float,
        caption: str = "",
        is_integer: bool = False,
        accent: str = GOLD,
        diameter: int = 38,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._min = float(minimum)
        self._max = float(maximum)
        self._is_integer = bool(is_integer)
        self._accent = QColor(accent)
        self._diameter = int(diameter)
        self._caption = caption
        self._fraction = fraction_from_value(value, self._min, self._max)
        self._drag_start_y: float | None = None
        self._drag_start_fraction = self._fraction
        self.setFixedSize(self._diameter + 4, self._diameter + 4)
        self.setCursor(Qt.SizeVerCursor)

    # value API ------------------------------------------------------------
    def value(self) -> float:
        v = value_from_fraction(self._fraction, self._min, self._max)
        return float(round(v)) if self._is_integer else round(v, 3)

    def setValue(self, value: float) -> None:
        self._fraction = fraction_from_value(value, self._min, self._max)
        self.update()

    def _commit_fraction(self, fraction: float) -> None:
        fraction = clamp01(fraction)
        if fraction != self._fraction:
            self._fraction = fraction
            self.update()
            self.valueChanged.emit(self.value())

    # interaction ----------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_y = event.position().y()
            self._drag_start_fraction = self._fraction
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_start_y is None:
            return
        dy = self._drag_start_y - event.position().y()  # up = positive = fill
        self._commit_fraction(drag_to_fraction(self._drag_start_fraction, dy, self._diameter))
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_start_y = None
        event.accept()

    # painting -------------------------------------------------------------
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(2, 2, self._diameter, self._diameter)

        circle = QPainterPath()
        circle.addEllipse(rect)

        # Background disc.
        painter.fillPath(circle, QBrush(QColor(SURFACE)))

        # Liquid fill from the bottom up to the current fraction.
        if self._fraction > 0:
            fill_h = self._diameter * self._fraction
            fill_rect = QRectF(rect.left(), rect.bottom() - fill_h, rect.width(), fill_h)
            painter.save()
            painter.setClipPath(circle)
            painter.fillRect(fill_rect, QBrush(self._accent))
            painter.restore()

        # Outline.
        painter.setPen(QPen(QColor(LINE), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect)

        # Centered value text.
        painter.setPen(QPen(QColor(INK_SOFT)))
        text = str(int(self.value())) if self._is_integer else f"{self.value():.2f}"
        painter.drawText(rect, Qt.AlignCenter, text)
