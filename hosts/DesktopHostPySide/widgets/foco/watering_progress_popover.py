"""Popover de progreso del riego en lote (BETA2-FOCO-35, vivo en FOCO-39).

Sustituye al drawer «Riego» por-entidad que el lote abría (confuso: mostraba UNA
entidad, y su borrado al navegar colgaba el lote). Se abre desde el badge «Regando
x/y» del rincón y se REFRESCA EN VIVO mientras el lote avanza (``update_progress``):
el workspace lo actualiza en cada paso del worker, así que el detalle no se queda
congelado con el snapshot del clic. Muestra el progreso y una lista de entidades
con su estado (regada / regando / error / pendiente) y el resumen de su informe.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD_DEEP,
    INK_MUTED,
    INK_STRONG,
)
from hosts.DesktopHostPySide.widgets.foco.foco_popover import Popover

_ERROR = "#C0392B"  # rojo de error de la casa (fichero no escaneado por el estático)
_STATUS_GLYPH = {
    "done": ("✓", GOLD_DEEP),
    "watering": ("⟳", INK_STRONG),
    "error": ("✗", _ERROR),
    "pending": ("·", INK_MUTED),
}


class WateringProgressPopover(Popover):
    """Detalle del lote de riego: x/y + lista de entidades con estado e informe.

    Se construye una vez y se refresca en sitio con ``update_progress`` para que,
    si el usuario lo deja abierto, siga el avance del lote sin reabrirlo."""

    def __init__(self, entries: list[dict], done: int, total: int, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(260)
        self._title = QLabel("")
        self._title.setStyleSheet(
            f"color: {INK_STRONG}; font-size: 12px; font-weight: 700; "
            "background: transparent; border: none;"
        )
        self._layout.addWidget(self._title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        holder = QWidget()
        self._col = QVBoxLayout(holder)
        self._col.setContentsMargins(0, 0, 0, 0)
        self._col.setSpacing(4)
        self._col.addStretch(1)
        self._scroll.setWidget(holder)
        self._layout.addWidget(self._scroll)
        self.update_progress(entries, done, total)

    # ── API ─────────────────────────────────────────────────────────────────

    def update_progress(
        self, entries: list[dict], done: int, total: int, *, finished: bool = False
    ) -> None:
        """Refresca título + filas en sitio (FOCO-39: el popover sigue el lote)."""
        verb = "completado" if finished else "en curso"
        self._title.setText(f"Riego {verb} · {int(done)}/{int(total)}")
        # Reconstruye las filas antes del stretch final (el conteo es estable
        # durante un lote, así que la altura no baila).
        while self._col.count() > 1:
            item = self._col.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for index, entry in enumerate(entries):
            self._col.insertWidget(index, self._row(entry))
        self._scroll.setFixedHeight(min(260, 24 * max(1, len(entries)) + 8))

    def _row(self, entry: dict) -> QWidget:
        status = str(entry.get("status", "pending"))
        glyph, color = _STATUS_GLYPH.get(status, _STATUS_GLYPH["pending"])
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        dot = QLabel(glyph)
        dot.setFixedWidth(14)
        dot.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: 700; "
            "background: transparent; border: none;"
        )
        name = QLabel(str(entry.get("name", "")))
        name.setStyleSheet(
            f"color: {INK_STRONG}; font-size: 12px; background: transparent; border: none;"
        )
        h.addWidget(dot)
        h.addWidget(name)
        summary = str(entry.get("summary", "") or "")
        if summary:
            note = QLabel(summary)
            note.setStyleSheet(
                f"color: {INK_MUTED}; font-size: 11px; background: transparent; border: none;"
            )
            note.setMaximumWidth(150)
            h.addWidget(note, 1)
        else:
            h.addStretch(1)
        return row

    def open_above(self, anchor: QWidget, *, margin: int = 6) -> None:
        """El badge vive en el rincón inferior derecho → abrir ARRIBA, alineado a
        su borde derecho, para no salir de la pantalla."""
        self.adjustSize()
        pos = anchor.mapToGlobal(QPoint(anchor.width() - self.width(), -self.height() - margin))
        self.move(pos)
        self.show()
