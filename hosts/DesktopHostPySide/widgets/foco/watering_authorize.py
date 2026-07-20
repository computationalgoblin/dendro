"""Autorización visible de IA para el riego y Sugerir X (BETA2-FOCO-12).

REGLA DE PRODUCTO: la IA jamás se consume sin que el usuario vea y autorice
qué se enviará, a quién afecta, qué se espera y el coste estimado
(bajo/medio/alto). Este panel se muestra en el ModalOverlay de la app; sin
confirmación explícita NO se lanza ningún job.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_DEEP,
    INK_INVERSE,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    SAGE,
    SURFACE_HI,
)

_COST_COLORS = {"bajo": SAGE, "medio": GOLD, "alto": GOLD_DEEP}


class WateringAuthorizePanel(QFrame):
    """Tarjeta de autorización: resumen + coste + Autorizar/Cancelar."""

    def __init__(
        self,
        *,
        title: str,
        lines: list[str],
        cost_class: str,
        confirm_text: str = "Autorizar",
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self.setObjectName("wateringAuthorize")
        self.setStyleSheet(
            f"QFrame#wateringAuthorize {{ background: {SURFACE_HI}; "
            f"border: 1px solid {GOLD}; border-radius: 16px; }}"
        )
        self.setFixedWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        title_label = QLabel(title, self)
        title_label.setStyleSheet(
            f"color: {INK_STRONG}; font-family: Georgia, serif; "
            "font-size: 16px; font-weight: 700; background: transparent; border: none;"
        )
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        for line in lines:
            line_label = QLabel(f"• {line}", self)
            line_label.setWordWrap(True)
            line_label.setStyleSheet(f"color: {INK_SOFT}; background: transparent; border: none;")
            layout.addWidget(line_label)

        cost_row = QHBoxLayout()
        cost_caption = QLabel("Coste estimado:", self)
        cost_caption.setStyleSheet(f"color: {INK_MUTED}; background: transparent; border: none;")
        cost_row.addWidget(cost_caption)
        self.cost_chip = QLabel(cost_class.upper(), self)
        self.cost_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cost_chip.setStyleSheet(
            f"QLabel {{ background: {_COST_COLORS.get(cost_class, INK_MUTED)}; "
            f"border-radius: 9px; padding: 2px 10px; color: {INK_INVERSE}; font-weight: 700; }}"
        )
        cost_row.addWidget(self.cost_chip)
        cost_row.addStretch(1)
        layout.addLayout(cost_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_button = QPushButton("Cancelar", self)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE_SOFT}; "
            f"border-radius: 10px; color: {INK_SOFT}; padding: 6px 14px; }}"
        )
        self.cancel_button.clicked.connect(self._cancel)
        buttons.addWidget(self.cancel_button)
        self.authorize_button = QPushButton(confirm_text, self)
        self.authorize_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.authorize_button.setStyleSheet(
            f"QPushButton {{ background: {GOLD}; border: none; border-radius: 10px; "
            f"color: {INK_INVERSE}; font-weight: 700; padding: 6px 16px; }}"
        )
        self.authorize_button.clicked.connect(self._confirm)
        buttons.addWidget(self.authorize_button)
        layout.addLayout(buttons)

    def _confirm(self) -> None:
        self._on_confirm()

    def _cancel(self) -> None:
        if self._on_cancel is not None:
            self._on_cancel()


def request_watering_authorization(
    overlay,
    *,
    title: str,
    lines: list[str],
    cost_class: str,
    confirm_text: str,
    on_confirm: Callable[[], None],
) -> WateringAuthorizePanel | None:
    """Muestra la autorización en el ModalOverlay. Sin overlay NO se autoriza
    nada (jamás se consume IA sin confirmación visible)."""
    if overlay is None:
        return None
    panel = WateringAuthorizePanel(
        title=title,
        lines=lines,
        cost_class=cost_class,
        confirm_text=confirm_text,
        on_confirm=lambda: (overlay.dismiss(emit=False), on_confirm()),
        on_cancel=lambda: overlay.dismiss(),
    )
    overlay.open_widget(panel)
    return panel
