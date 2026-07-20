"""Sección de Memoria en el Cuaderno de Cultivo (BETA2-MEM-09).

Muestra, DENTRO de la pestaña Cultivo (no un panel técnico aparte), el estado de
Memoria de un elemento: chip de frescura (vigente/falta regar/secada/sin), resumen
editorial e incidencias accionables (contradicción/hueco/pregunta/supuesto) con
aceptar/corregir/aplazar/ignorar. Solo EMITE señales; el host aplica por
``NarrativeMemoryService`` — la UI nunca escribe persistencia. Pintura plana con QSS
(regla del repo: prohibido QGraphicsEffect).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    FONT_SERIF,
    GOLD_DEEP,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE_SOFT,
    SAGE,
    overline_label,
)
from packages.domain.narrative_memory import MemoryFreshness, MemoryIssueKind

# frescura → (etiqueta, color) — reutiliza el patrón de _STATUS_STYLES del riego.
_FRESHNESS_STYLE: dict[str, tuple[str, str]] = {
    MemoryFreshness.REGADA.value: ("Memoria vigente", SAGE),
    MemoryFreshness.FALTA_REGAR.value: ("Falta regar", GOLD_DEEP),
    MemoryFreshness.SECADA.value: ("Memoria secada", INK_MUTED),
    MemoryFreshness.SIN_MEMORIA.value: ("Sin memoria", INK_SOFT),
}

_ISSUE_GLYPH: dict[str, str] = {
    MemoryIssueKind.CONTRADICCION.value: "⚠ Contradicción",
    MemoryIssueKind.HUECO.value: "◌ Hueco",
    MemoryIssueKind.PREGUNTA_ABIERTA.value: "? Pregunta",
    MemoryIssueKind.SUPUESTO.value: "· Supuesto",
}

# acción de UI → estado destino del issue (MemoryIssueStatus.value).
_ACTIONS: tuple[tuple[str, str], ...] = (
    ("Aceptar", "aceptada"),
    ("Corregir", "corregida"),
    ("Aplazar", "aplazada"),
    ("Ignorar", "ignorada"),
)


class MemorySection(QWidget):
    """Bloque de Memoria de un elemento dentro del Cuaderno de Cultivo."""

    # (issue_id, estado_destino) — el host lo aplica vía NarrativeMemoryService.
    issueAction = Signal(str, str)  # noqa: N815 — convención Qt de señales

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 6, 0, 6)
        self._layout.setSpacing(6)
        self._layout.addWidget(overline_label("MEMORIA"))

        chip_row = QHBoxLayout()
        self.freshness_chip = QLabel("Sin memoria")
        self.freshness_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip_row.addWidget(self.freshness_chip, 0, Qt.AlignmentFlag.AlignLeft)
        chip_row.addStretch(1)
        self._layout.addLayout(chip_row)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(
            f"font-family: {FONT_SERIF}; font-size: 14px; color: {INK_STRONG};"
        )
        self._layout.addWidget(self.summary)

        self.aviso = QLabel("")
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet(f"color: {GOLD_DEEP}; font-style: italic;")
        self.aviso.setVisible(False)
        self._layout.addWidget(self.aviso)

        self._issues_box = QVBoxLayout()
        self._issues_box.setSpacing(4)
        self._layout.addLayout(self._issues_box)

    def _set_chip(self, freshness_value: str) -> None:
        label, color = _FRESHNESS_STYLE.get(freshness_value, _FRESHNESS_STYLE["sin_memoria"])
        self.freshness_chip.setText(label)
        self.freshness_chip.setStyleSheet(
            f"background: {color}; color: white; border-radius: 9px; "
            f"padding: 2px 10px; font-size: 11px; font-weight: 700;"
        )

    def _clear_issues(self) -> None:
        while self._issues_box.count():
            item = self._issues_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _issue_card(self, issue: Any) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ border: 1px solid {LINE_SOFT}; border-radius: 8px; padding: 6px; }}"
        )
        col = QVBoxLayout(frame)
        col.setContentsMargins(6, 6, 6, 6)
        col.setSpacing(4)
        head = QLabel(_ISSUE_GLYPH.get(issue.kind.value, "· Incidencia"))
        head.setStyleSheet(f"color: {INK_MUTED}; font-size: 11px; font-weight: 700;")
        col.addWidget(head)
        text = QLabel(issue.texto)
        text.setWordWrap(True)
        text.setStyleSheet(f"color: {INK_STRONG};")
        col.addWidget(text)
        actions = QHBoxLayout()
        for label, target_status in _ACTIONS:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda _=False, iid=issue.id, st=target_status: self.issueAction.emit(iid, st)
            )
            actions.addWidget(btn)
        actions.addStretch(1)
        col.addLayout(actions)
        return frame

    def render(self, block: Any) -> None:
        """Pinta el estado de Memoria del elemento (o 'sin memoria' si es None)."""
        self._clear_issues()
        if block is None:
            self._set_chip(MemoryFreshness.SIN_MEMORIA.value)
            self.summary.setText("Este elemento aún no tiene Memoria. Riégalo para generarla.")
            self.aviso.setVisible(False)
            return
        self._set_chip(block.freshness.value)
        self.summary.setText(block.resumen_editorial or "(sin resumen editorial)")
        obsoleta = block.freshness in (MemoryFreshness.FALTA_REGAR, MemoryFreshness.SECADA)
        self.aviso.setText(
            "Esta Memoria puede estar obsoleta; se recomienda Regar antes de fiarte de ella."
        )
        self.aviso.setVisible(obsoleta)
        # solo incidencias abiertas (contradicciones/huecos/preguntas/supuestos)
        for issue in block.issues:
            if getattr(issue.estado, "value", issue.estado) == "abierta":
                self._issues_box.addWidget(self._issue_card(issue))


__all__ = ["MemorySection"]
