"""Reusable immersive card widget for B31-T09 gallery."""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from hosts.DesktopHostPySide.widgets.design_system import Badge

_KIND_TONES = {
    "personaje": "info",
    "localizacion": "success",
    "lugar": "success",
    "faccion": "warning",
    "campaña": "info",
    "sesión": "info",
    "secreto": "danger",
    "pista": "success",
}

_KIND_COLORS = {
    "personaje": "#7C9BFF",
    "localizacion": "#7EC8A5",
    "lugar": "#7EC8A5",
    "organizacion": "#DCA35F",
    "faccion": "#D9908F",
    "objeto": "#C9A5FF",
    "evento": "#E0C46C",
    "campaña": "#8EA4C8",
    "sesión": "#9BB4C7",
    "secreto": "#D46A6A",
    "pista": "#78B891",
}


class EntityCard(QFrame):
    """Clickable calm card. Stores item identity internally but never displays IDs."""

    clicked = Signal(object)

    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("galleryCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(168)
        self.setStyleSheet(self._style())
        self._build()
        self._fade_in()

    def _style(self) -> str:
        kind_key = str(self.item.get("kind_key") or self.item.get("kind") or "").lower()
        color = _KIND_COLORS.get(kind_key, "#8EA4C8")
        return f"""
            QFrame#galleryCard {{
                background: rgba(41, 46, 58, 0.96);
                border: 1px solid rgba(216, 222, 233, 0.12);
                border-left: 5px solid {color};
                border-radius: 18px;
            }}
            QFrame#galleryCard:hover {{
                background: rgba(49, 56, 70, 0.98);
                border: 1px solid rgba(235, 203, 139, 0.30);
                border-left: 5px solid {color};
            }}
        """

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        symbol = QLabel(str(self.item.get("symbol") or "✦"))
        symbol.setStyleSheet("font-size: 24px; color: #EBCB8B;")
        top.addWidget(symbol)
        title = QLabel(str(self.item.get("title") or "Sin nombre"))
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 17px; font-weight: 700; color: #ECEFF4;")
        top.addWidget(title, 1)
        kind = str(self.item.get("kind") or "Elemento")
        tone = _KIND_TONES.get(str(self.item.get("kind_key") or kind).lower(), "info")
        top.addWidget(Badge(kind, tone))
        layout.addLayout(top)

        subtitle = QLabel(str(self.item.get("subtitle") or "Sin descripción breve"))
        subtitle.setWordWrap(True)
        subtitle.setObjectName("mutedLabel")
        layout.addWidget(subtitle)

        meta = QHBoxLayout()
        for label, tone in self.item.get("badges", [])[:3]:
            meta.addWidget(Badge(str(label), str(tone)))
        meta.addStretch()
        layout.addLayout(meta)

        footer = QHBoxLayout()
        relation_text = str(self.item.get("relation_summary") or "Sin relaciones destacadas")
        footer_label = QLabel(relation_text)
        footer_label.setObjectName("mutedLabel")
        footer_label.setWordWrap(True)
        footer.addWidget(footer_label, 1)
        open_btn = QPushButton("Ver")
        open_btn.clicked.connect(lambda: self.clicked.emit(self.item))
        footer.addWidget(open_btn)
        layout.addLayout(footer)

    def _fade_in(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self._animation = QPropertyAnimation(effect, b"opacity", self)
        self._animation.setDuration(180)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.start()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)
        super().mouseReleaseEvent(event)
