"""Asistente de contención del Modo Foco (BETA2-FOCO-26).

Cuando una rama nueva va a contener una entidad que YA vive en otra rama, este
panel (overlay DENTRO de la app, patrón ``ModalOverlay``) pregunta de forma
visual qué hacer:

- «Mover»: la entidad pasa a la rama nueva y la antigua deja de contenerla.
- «Anidar»: la rama nueva entra DENTRO de la antigua conteniendo a la entidad
  (antigua ⊃ nueva ⊃ entidad).

El panel solo EMITE la decisión (``moveChosen``/``nestChosen``/``cancelled``);
quien lo abre ejecuta los cambios por los controllers — la UI nunca escribe
persistencia directamente.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_SOFT,
    INK_MUTED,
    INK_STRONG,
    LINE_CARD,
    POPUP_BG,
    SURFACE_HI,
)


def _elide(name: str, limit: int = 28) -> str:
    name = str(name or "").strip() or "(sin nombre)"
    return name if len(name) <= limit else name[: limit - 1] + "…"


class ContainmentAssistantPanel(QWidget):
    """Panel de decisión mover/anidar para contención en conflicto."""

    moveChosen = Signal()  # noqa: N815 — convención Qt de señales
    nestChosen = Signal()  # noqa: N815 — convención Qt de señales
    cancelled = Signal()  # noqa: N815 — convención Qt de señales

    def __init__(
        self,
        *,
        entity_name: str,
        old_branch_name: str,
        new_branch_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("containmentAssistant")
        # WA_StyledBackground: sin esto un QWidget plano no pinta la tarjeta.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QWidget#containmentAssistant {{ background: {POPUP_BG}; "
            f"border: 1px solid {LINE_CARD}; border-radius: 12px; }}"
        )
        self.setMinimumWidth(460)
        entity = _elide(entity_name)
        old_branch = _elide(old_branch_name)
        new_branch = _elide(new_branch_name)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(10)

        header = QLabel(f"«{entity}» ya vive en la rama «{old_branch}»")
        header.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {INK_STRONG};")
        header.setWordWrap(True)
        outer.addWidget(header)
        note = QLabel(
            f"¿Cómo debe contenerla la rama nueva «{new_branch}»? "
            "Elige qué pasa con la contención actual."
        )
        note.setStyleSheet(f"color: {INK_MUTED};")
        note.setWordWrap(True)
        outer.addWidget(note)

        option_style = (
            f"QPushButton {{ background: {SURFACE_HI}; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: 10px; color: {INK_STRONG}; padding: 12px 14px; "
            f"text-align: left; font-size: 13px; }} "
            f"QPushButton:hover {{ border-color: {GOLD}; }}"
        )
        self.move_button = QPushButton(
            f"→  Mover solo «{entity}» a «{new_branch}»\n"
            f"     «{old_branch}» deja de contenerla."
        )
        self.move_button.setObjectName("containmentMoveButton")
        self.move_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.move_button.setStyleSheet(option_style)
        self.move_button.clicked.connect(self.moveChosen.emit)
        outer.addWidget(self.move_button)

        self.nest_button = QPushButton(
            f"⊂  Anidar: «{new_branch}» dentro de «{old_branch}»\n"
            f"     {old_branch} ⊃ {new_branch} ⊃ {entity}"
        )
        self.nest_button.setObjectName("containmentNestButton")
        self.nest_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nest_button.setStyleSheet(option_style)
        self.nest_button.clicked.connect(self.nestChosen.emit)
        outer.addWidget(self.nest_button)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.cancelled.emit)
        row.addWidget(cancel)
        outer.addLayout(row)
