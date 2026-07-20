"""Mini-leyenda del jardín (BETA2-PULIDO-06): el lenguaje visual del riego.

Vive en la esquina inferior-derecha del Mapa (UI2-02: sobre las píldoras
🌱/💧, lejos del cluster izquierdo que la solapaba), PLEGADA por defecto a un
punto discreto; al expandirla explica con los colores REALES de BETA2-JARDIN qué
significa cada señal (marrón, gris-tierra, halo, caída, raíz). Solo lectura:
nada de aquí muta el proyecto. Pintura plana con QSS — sin QGraphicsEffect
(regla del repo).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    EARTH,
    EARTH_GREY,
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK_SOFT,
    LINE_SOFT,
    RADIUS_MD,
    SPACE_SM,
    SPACE_XS,
    SURFACE_HI,
    TYPE_CAPTION_PX,
    overline_label,
)

# (color de la muestra, texto) — el lenguaje REAL del jardín (BETA2-JARDIN).
_LEGEND_ROWS = (
    (EARTH, "Marrón · por regar (congelada)"),
    (EARTH_GREY, "Gris-tierra · secada a propósito"),
    (GOLD, "Halo dorado · iluminada"),
    (GOLD_TINT, "Caída al borde · contenido débil"),
    (GOLD_SOFT, "Raíz dorada · arraigo (al enfocar)"),
)


class GardenLegend(QWidget):
    """Punto plegable ⇄ tarjeta con la leyenda del estado de riego."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._expanded = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACE_XS)
        root.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        self._card = QFrame(self)
        self._card.setObjectName("gardenLegendCard")
        self._card.setStyleSheet(
            f"QFrame#gardenLegendCard {{ background: {SURFACE_HI}; "
            f"border: 1px solid {LINE_SOFT}; border-radius: {RADIUS_MD}px; }}"
        )
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(SPACE_SM + 2, SPACE_SM, SPACE_SM + 2, SPACE_SM)
        card_layout.setSpacing(SPACE_XS)
        card_layout.addWidget(overline_label("Lenguaje del jardín", color=GOLD_DEEP))
        for swatch_color, text in _LEGEND_ROWS:
            row = QHBoxLayout()
            row.setSpacing(SPACE_SM)
            swatch = QLabel("", self._card)
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(
                f"background: {swatch_color}; border: 1px solid {LINE_SOFT}; border-radius: 6px;"
            )
            row.addWidget(swatch)
            label = QLabel(text, self._card)
            label.setStyleSheet(
                f"color: {INK_SOFT}; font-size: {TYPE_CAPTION_PX}px; "
                "background: transparent; border: none;"
            )
            row.addWidget(label, 1)
            card_layout.addLayout(row)
        self._card.hide()
        root.addWidget(self._card)

        # Punto discreto: flor plegada que invita sin ocupar lienzo.
        self._toggle = QPushButton("❀", self)
        self._toggle.setFixedSize(24, 24)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setToolTip("Leyenda del jardín: qué significa cada color del riego")
        self._toggle.setStyleSheet(
            f"QPushButton {{ background: {SURFACE_HI}; color: {GOLD_DEEP}; "
            f"border: 1px solid {LINE_SOFT}; border-radius: 12px; font-size: 12px; }} "
            f"QPushButton:hover {{ background: {GOLD_TINT}; border-color: {GOLD_SOFT}; }}"
        )
        self._toggle.clicked.connect(lambda: self.set_expanded(not self._expanded))
        root.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignRight)

    # ── API ────────────────────────────────────────────────────────────────

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self._card.setVisible(self._expanded)
        self.adjustSize()
        # El host reancla (la esquina se mide distinta al expandir/plegar).
        parent = self.parentWidget()
        hook = getattr(parent, "_position_garden_legend", None)
        if hook is not None:
            hook()


__all__ = ["GardenLegend"]
