"""BETA2-FOCO-27: tarjeta compacta de SOLO lectura de un hito.

En la tarjeta de descripción del Foco (modo lectura), clicar un rombo de la
cronología abre este panel a la derecha: nombre + descripción corta + fecha/año
del hito. Sin edición — solo visualizar (la edición vive en el modo edición, en
el cajón inferior del editor). Pintura a mano (sin QGraphicsEffect).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    FONT_SERIF,
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    SPACE_SM,
)


class MilestoneReadCard(QWidget):
    """Vista compacta, solo lectura, de un hito causal."""

    def __init__(
        self,
        hito: Any,
        *,
        temporal_label: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(SPACE_SM)

        title = str(getattr(hito, "title", "") or "Hito sin título")
        name = QLabel(title)
        name.setWordWrap(True)
        name.setStyleSheet(
            f"color: {INK_STRONG}; font-family: {FONT_SERIF}; font-size: 18px; "
            "font-weight: 700; background: transparent; border: none;"
        )
        box.addWidget(name)

        label = str(temporal_label or "").strip()
        if label:
            chip = QLabel(label)
            chip.setStyleSheet(
                f"color: {GOLD_DEEP}; background: {GOLD_TINT}; "
                f"border: 1px solid {GOLD_SOFT}; border-radius: 12px; "
                "padding: 2px 10px; font-size: 12px;"
            )
            # Fila con stretch para que la cápsula abrace su contenido (no se estira).
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(chip, 0, Qt.AlignmentFlag.AlignLeft)
            row.addStretch(1)
            box.addLayout(row)

        description = str(getattr(hito, "description", "") or "").strip()
        body = QLabel(description or "Sin descripción.")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body_color = INK_SOFT if description else INK_MUTED
        italic = "" if description else " font-style: italic;"
        body.setStyleSheet(
            f"color: {body_color}; font-family: {FONT_SERIF}; font-size: 14px; "
            f"background: transparent; border: none;{italic}"
        )
        box.addWidget(body)
        box.addStretch(1)


__all__ = ["MilestoneReadCard"]
