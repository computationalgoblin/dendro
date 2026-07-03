"""CuratedColorPicker — selector de color EMBEBIDO con paleta curada (BETA1-I73).

Sustituye al ``QColorDialog`` nativo (que se abría como ventana del SO fuera de la app). Es un
popover ligero (``Qt.Popup``) con una rejilla de colores preseleccionados coherentes con la
estética de la app (parchment + oro); clic en un swatch = elegir. Se posiciona bajo el widget
ancla y se ACOTA al recuadro de la ventana de la app para no salirse nunca.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QPushButton

from hosts.DesktopHostPySide.widgets import design_system as ds

# Paleta curada: colores apagados y distinguibles, afines al sistema visual (16, 8×2).
CURATED_COLORS: list[str] = [
    "#6E8B3D", "#4F7A3D", "#8B5E3C", "#B08D57",
    "#C9A227", "#C0632B", "#A5443D", "#8C3B4A",
    "#7A4F8C", "#7B6D8D", "#4F6F8C", "#4F7A8C",
    "#3E7A70", "#8C7A4F", "#6B6B6B", "#9A8C98",
]
_COLS = 8


class CuratedColorPicker(QFrame):
    """Popover de colores curados. Emite ``colorChosen(hex)`` al elegir."""

    colorChosen = Signal(str)  # noqa: N815 — señal Qt

    def __init__(self, parent: Any = None, *, current: str = ""):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setObjectName("curatedColorPicker")
        self.setStyleSheet(
            f"#curatedColorPicker {{ background: {ds.PAPER}; "
            f"border: 1px solid {ds.LINE_STRONG}; border-radius: {ds.RADIUS_MD}px; }}"
        )
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(6)
        cur = (current or "").lower()
        for i, color in enumerate(CURATED_COLORS):
            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(26, 26)
            btn.setToolTip(color)
            selected = color.lower() == cur
            border = ds.INK_STRONG if selected else "#7a6c53"
            width = 3 if selected else 1
            btn.setStyleSheet(
                f"QPushButton {{ background: {color}; border: {width}px solid {border}; "
                f"border-radius: 13px; }}"
                f"QPushButton:hover {{ border: 2px solid {ds.INK_STRONG}; }}"
            )
            btn.clicked.connect(lambda _=False, c=color: self._choose(c))
            grid.addWidget(btn, i // _COLS, i % _COLS)

    def _choose(self, color: str) -> None:
        self.colorChosen.emit(color)
        self.close()

    def popup_below(self, anchor: Any) -> None:
        """Muestra el popover bajo ``anchor``, acotado a la ventana de la app (no se sale)."""
        self.adjustSize()
        global_pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
        x, y = global_pos.x(), global_pos.y() + 4
        window = anchor.window()
        if window is not None:
            geo = window.frameGeometry()
            x = max(geo.left(), min(x, geo.right() - self.width()))
            y = max(geo.top(), min(y, geo.bottom() - self.height()))
        self.move(x, y)
        self.show()
