"""BETA2-CAL-07 — MiniStepper: spinner minimalista escribible.

`BotanicalSpinBox` (round −/+ overlaid) no reserva ancho mínimo y tapa el dígito al
estrecharse: los años/días "ni se veían ni se podían escribir". Este control es la
alternativa mínima: `[−] [campo escribible] [+]` con el número SIEMPRE visible, botones
pequeños y teclado directo (patrón del pill temporal: `QLineEdit` + `QIntValidator`).

Expone un subconjunto de la API de `QSpinBox` (`value/setValue/setRange/minimum/maximum/
setSingleStep` + señal `valueChanged`) para sustituir a `BotanicalSpinBox` sin fricción.
Los glifos son configurables: `−`/`+` (por defecto) o `‹`/`›` (paso año a año).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QToolButton, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK_STRONG,
    LINE,
)

_BTN_QSS = (
    f"QToolButton {{ background: transparent; border: 1px solid {LINE}; border-radius: 8px; "
    f"color: {GOLD_DEEP}; font-size: 13px; font-weight: 700; padding: 0; }} "
    f"QToolButton:hover {{ background: {GOLD_TINT}; border-color: {GOLD_SOFT}; }} "
    f"QToolButton:pressed {{ background: {GOLD_SOFT}; }} "
    f"QToolButton:disabled {{ color: {LINE}; border-color: {LINE}; }}"
)

_EDIT_QSS = (
    f"QLineEdit {{ background: transparent; border: 1px solid {LINE}; border-radius: 8px; "
    f"padding: 1px 4px; color: {INK_STRONG}; font-size: 12px; font-weight: 600; }} "
    f"QLineEdit:focus {{ border-color: {GOLD_SOFT}; background: #FFFFFF; }}"
)


class MiniStepper(QWidget):
    """Spinner compacto y escribible con API subconjunto de QSpinBox."""

    valueChanged = Signal(int)  # noqa: N815 — misma firma que QSpinBox

    def __init__(
        self,
        *,
        minimum: int = 0,
        maximum: int = 999999,
        value: int = 0,
        step: int = 1,
        glyphs: tuple[str, str] = ("−", "+"),
        edit_width: int = 48,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._min = int(minimum)
        self._max = int(maximum)
        self._step = max(1, int(step))
        self._value = self._clamp(int(value))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._minus = self._make_button(glyphs[0], -1)
        layout.addWidget(self._minus)

        self._edit = QLineEdit(str(self._value))
        self._edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._edit.setStyleSheet(_EDIT_QSS)
        self._edit.setFixedHeight(24)
        self._edit.setMinimumWidth(edit_width)
        self._edit.setValidator(QIntValidator(self._min, self._max, self._edit))
        self._edit.editingFinished.connect(self._on_edited)
        layout.addWidget(self._edit, 1)

        self._plus = self._make_button(glyphs[1], +1)
        layout.addWidget(self._plus)

        self._sync_enabled()

    # ── construcción ─────────────────────────────────────────────────────

    def _make_button(self, glyph: str, direction: int) -> QToolButton:
        btn = QToolButton()
        btn.setText(glyph)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(22, 24)
        btn.setStyleSheet(_BTN_QSS)
        btn.setAutoRepeat(True)
        btn.setAutoRepeatInterval(60)
        btn.setAutoRepeatDelay(300)
        btn.clicked.connect(lambda: self.setValue(self._value + direction * self._step))
        return btn

    # ── API tipo QSpinBox ────────────────────────────────────────────────

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:  # noqa: N802 — API de QSpinBox
        value = self._clamp(int(value))
        changed = value != self._value
        self._value = value
        if self._edit.text() != str(value):
            self._edit.blockSignals(True)
            self._edit.setText(str(value))
            self._edit.blockSignals(False)
        self._sync_enabled()
        if changed:
            self.valueChanged.emit(value)

    def setRange(self, minimum: int, maximum: int) -> None:  # noqa: N802
        self._min = int(minimum)
        self._max = int(maximum)
        self._edit.setValidator(QIntValidator(self._min, self._max, self._edit))
        self.setValue(self._value)  # re-clampa (sin emitir si no cambia)

    def minimum(self) -> int:
        return self._min

    def maximum(self) -> int:
        return self._max

    def setSingleStep(self, step: int) -> None:  # noqa: N802
        self._step = max(1, int(step))

    def setReadOnly(self, read_only: bool) -> None:  # noqa: N802
        self._edit.setReadOnly(bool(read_only))
        self._minus.setEnabled(not read_only)
        self._plus.setEnabled(not read_only)

    # ── interno ──────────────────────────────────────────────────────────

    def _clamp(self, value: int) -> int:
        return max(self._min, min(self._max, value))

    def _on_edited(self) -> None:
        text = self._edit.text().strip()
        self.setValue(int(text) if text.lstrip("-").isdigit() else self._value)

    def _sync_enabled(self) -> None:
        self._minus.setEnabled(self._value > self._min)
        self._plus.setEnabled(self._value < self._max)


__all__ = ["MiniStepper"]
