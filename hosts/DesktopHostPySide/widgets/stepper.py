"""BETA1-UX2B: spinbox botánico con botones −/+ en vez de las flechas nativas.

El usuario no quiere las flechitas verticales del `QSpinBox` (aparecían en muchos
menús). `BotanicalSpinBox` es un **drop-in** de `QSpinBox` (misma API e
`isinstance`), pero oculta las flechas nativas y coloca dos botones redondos −/+
a los lados del número, coherentes con el lenguaje pergamino+oro. Se puede teclear
el número y usar la rueda igual que antes.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractSpinBox, QSpinBox, QToolButton

from hosts.DesktopHostPySide.widgets.design_system import GOLD_DEEP, GOLD_SOFT, GOLD_TINT, INK, LINE


class BotanicalSpinBox(QSpinBox):
    """QSpinBox sin flechas nativas + botones −/+ superpuestos a los lados."""

    _BTN_QSS = (
        f"QToolButton {{ background: {GOLD_TINT}; color: {GOLD_DEEP}; "
        f"border: 1px solid {GOLD_SOFT}; border-radius: 11px; font-size: 14px; "
        f"font-weight: 700; padding: 0; }} "
        f"QToolButton:hover {{ background: {GOLD_SOFT}; color: {INK}; }} "
        f"QToolButton:pressed {{ background: {LINE}; }}"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(32)
        self._minus = self._make_button("−", -1)
        self._plus = self._make_button("+", +1)

    def _make_button(self, text: str, direction: int) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setObjectName("stepperButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setAutoRepeat(True)
        btn.setAutoRepeatInterval(60)
        btn.setStyleSheet(self._BTN_QSS)
        btn.clicked.connect(lambda: self._step(direction))
        return btn

    def _step(self, direction: int) -> None:
        self.setValue(self.value() + direction * self.singleStep())

    def resizeEvent(self, event):  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        size = max(20, self.height() - 8)
        y = (self.height() - size) // 2
        self._minus.setGeometry(5, y, size, size)
        self._plus.setGeometry(self.width() - size - 5, y, size, size)
        # Reservar hueco para que los dígitos no queden bajo los botones.
        edit = self.lineEdit()
        if edit is not None:
            edit.setTextMargins(size, 0, size, 0)


__all__ = ["BotanicalSpinBox"]
