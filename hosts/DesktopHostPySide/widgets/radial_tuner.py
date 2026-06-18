"""RadialTuner — a fill-on-drag circular control (Fase 3, PA02).

A small circle that fills/empties when the user presses and drags vertically
(up = fill, down = empty), rendered in a characteristic accent colour. Used for
the command-bar tuners: temperature, output length and input context budget.

PA02: each tuner starts in **Auto** — it shows the per-task default (a hint set
by the host) and reports `is_auto == True`, so the host sends NO override and the
task tier/intent default applies. The user drags to take manual control; a
double-click resets back to Auto.

The drag→value math is factored into pure module functions so it can be unit
tested without a QApplication.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from hosts.DesktopHostPySide.widgets.design_system import GOLD, INK_MUTED, INK_SOFT, LINE, SURFACE

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
    """A circular fill control.

    Emits ``valueChanged(float)`` in [minimum, maximum] on manual edits, and
    ``autoChanged(bool)`` when toggling the Auto state.
    """

    valueChanged = Signal(float)
    autoChanged = Signal(bool)

    def __init__(
        self,
        *,
        minimum: float,
        maximum: float,
        value: float,
        caption: str = "",
        is_integer: bool = False,
        auto: bool = False,
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
        self._auto = bool(auto)
        self._hint: float | None = None
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

    @property
    def is_auto(self) -> bool:
        return self._auto

    def set_auto(self, auto: bool) -> None:
        """Toggle Auto. In Auto the tuner mirrors the hint and emits no override."""
        auto = bool(auto)
        if auto == self._auto:
            return
        self._auto = auto
        if auto and self._hint is not None:
            self._fraction = fraction_from_value(self._hint, self._min, self._max)
        self.update()
        self.autoChanged.emit(auto)

    def set_hint(self, value: float | None) -> None:
        """Per-task default shown while in Auto (does not leave Auto)."""
        self._hint = None if value is None else float(value)
        if self._auto and self._hint is not None:
            self._fraction = fraction_from_value(self._hint, self._min, self._max)
            self.update()

    def set_range(self, minimum: float, maximum: float) -> None:
        """Adjust bounds (e.g. when the active task's tier max changes)."""
        self._min = float(minimum)
        self._max = float(maximum)
        if self._auto and self._hint is not None:
            self._fraction = fraction_from_value(self._hint, self._min, self._max)
        self.update()

    def _commit_fraction(self, fraction: float) -> None:
        fraction = clamp01(fraction)
        changed = fraction != self._fraction
        was_auto = self._auto
        self._auto = False  # manual drag always leaves Auto
        if changed or was_auto:
            self._fraction = fraction
            self.update()
            if was_auto:
                self.autoChanged.emit(False)
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

    def mouseDoubleClickEvent(self, event):
        # Doble clic = volver a Auto (default por tarea).
        self.set_auto(True)
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

        # Liquid fill from the bottom up to the current fraction. En Auto se pinta
        # más tenue para indicar que es el valor por defecto, no un override.
        if self._fraction > 0:
            fill_h = self._diameter * self._fraction
            fill_rect = QRectF(rect.left(), rect.bottom() - fill_h, rect.width(), fill_h)
            fill_color = QColor(self._accent)
            if self._auto:
                fill_color.setAlpha(70)
            painter.save()
            painter.setClipPath(circle)
            painter.fillRect(fill_rect, QBrush(fill_color))
            painter.restore()

        # Outline.
        painter.setPen(QPen(QColor(LINE), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect)

        # Centered text: "auto" en modo Auto, el valor en modo manual.
        if self._auto:
            painter.setPen(QPen(QColor(INK_MUTED)))
            painter.drawText(rect, Qt.AlignCenter, "auto")
        else:
            painter.setPen(QPen(QColor(INK_SOFT)))
            text = str(int(self.value())) if self._is_integer else f"{self.value():.2f}"
            painter.drawText(rect, Qt.AlignCenter, text)
