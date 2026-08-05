"""Chip «siguiente paso» de la cabecera de Foco (BETA2-JARDIN-04).

Una sola sugerencia, la más urgente, derivada de ``watering_guidance``:
«Falta regar → Regar ahora» dispara el flujo de riego (con autorización);
«{Métrica} débil → Sugerir» eleva el «Sugerir X» del Cuaderno. Con todo
sano (o secada) el chip desaparece — la cabecera no regaña.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QPushButton, QWidget

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK_INVERSE,
)
from packages.application.watering_guidance import METRIC_LABELS, NextStep


class NextStepChip(QPushButton):
    """Píldora accionable; oculta si no hay paso urgente."""

    waterClicked = Signal()  # noqa: N815 — convención Qt de señales
    suggestClicked = Signal(str)  # noqa: N815 — métrica a reparar

    # PULIDO-03: el chip jamás fuerza el layout — ancho acotado + elipsis.
    # (340 da holgura al texto de riego incluso con fuentes de respaldo anchas.)
    MAX_WIDTH = 340

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._step: NextStep | None = None
        # BETA-MULTIAGENT2-FIX-06 (G2-08): riego en vuelo. Campo del widget (no un
        # `setEnabled` suelto) porque `set_step` se re-aplica a cada refresco y
        # resucitaría el disparador en mitad del lote.
        self._busy = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMaximumWidth(self.MAX_WIDTH)
        # Fuente por código (no QSS) para que la elipsis mida EXACTAMENTE la
        # misma fuente con la que se pinta el texto.
        font = self.font()
        font.setPixelSize(11)
        font.setBold(True)
        self.setFont(font)
        # UI2-11: el glifo del paso es un SVG teñido, nunca un emoji.
        self.setIconSize(QSize(14, 14))
        self.setStyleSheet(
            f"QPushButton {{ background: {GOLD_TINT}; color: {GOLD_DEEP}; "
            f"border: 1px solid {GOLD_SOFT}; border-radius: 12px; "
            f"padding: 3px 12px; text-align: left; }} "
            # PULIDO-03: hover por FONDO (gramática única de chips accionables).
            f"QPushButton:hover {{ background: {GOLD_SOFT}; color: {INK_INVERSE}; }}"
        )
        self.clicked.connect(self._on_clicked)
        self.hide()

    def _set_elided_text(self, text: str) -> None:
        metrics = QFontMetrics(self.font())
        # UI2-11: la reserva descuenta padding + icono SVG (14px + separación),
        # para que el sizeHint con icono siga cabiendo en MAX_WIDTH.
        self.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, self.MAX_WIDTH - 52))

    @property
    def step(self) -> NextStep | None:
        return self._step

    def set_busy(self, busy: bool) -> None:
        """BETA-MULTIAGENT2-FIX-06: hay un riego en vuelo → el chip no dispara otro."""
        self._busy = bool(busy)
        self._apply_busy()

    def busy(self) -> bool:
        return bool(self._busy)

    def _apply_busy(self) -> None:
        if self._busy:
            self.setEnabled(False)
            self.setToolTip("Hay un riego en curso; espera a que termine.")
        else:
            self.setEnabled(True)

    def set_step(self, step: NextStep | None) -> None:
        """Solo ``water`` y ``suggest`` son urgentes; el resto oculta el chip
        (secada se gestiona desde el Cuaderno; sano no necesita regañina)."""
        kind = step.kind if step is not None else ""
        if kind == "water":
            self._step = step
            self.setIcon(icons.icon("tool_water", color=GOLD_DEEP, size=14))
            self._set_elided_text("Falta regar → Regar ahora")
            self.setToolTip("Riega esta entidad (pasa por la autorización de coste).")
            self.show()
        elif kind == "suggest":
            self._step = step
            label = METRIC_LABELS.get(step.metric, step.metric)
            score = f" ({step.score})" if step.score is not None else ""
            self.setIcon(icons.icon("step_suggest", color=GOLD_DEEP, size=14))
            self._set_elided_text(f"{label} débil{score} → Sugerir")
            self.setToolTip(step.reason or f"Pide sugerencias para reforzar {label.lower()}.")
            self.show()
        else:
            self._step = None
            self.hide()
        # FIX-06: el estado «ocupado» manda sobre el paso recién pintado.
        self._apply_busy()

    def _on_clicked(self) -> None:
        step = self._step
        if step is None or self._busy:
            return
        if step.kind == "water":
            self.waterClicked.emit()
        elif step.kind == "suggest":
            self.suggestClicked.emit(step.metric)


__all__ = ["NextStepChip"]
