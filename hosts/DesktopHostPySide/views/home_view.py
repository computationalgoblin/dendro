"""HomeView — Dendro immersive portal for B31 UX fix.

Normal mode is intentionally non-technical: no schema, no provider status, no
counts, no raw IDs. Project/config actions are grouped behind quiet icon buttons.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.design_system import Badge, make_scroll_area


class HomeNode(QFrame):
    """Soft clickable node for one of Dendro's three product spaces."""

    def __init__(self, title: str, subtitle: str, glyph: str, tone: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("dendroNode")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(230, 230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        tones = {
            "creation": ("#F7F4EA", "#7A733D", "#AFA77A"),
            "gallery": ("#F3F5EE", "#6E7B59", "#B5BBA5"),
            "session": ("#F6F1E8", "#8A6849", "#C8AF8C"),
        }
        bg, fg, border = tones.get(tone, tones["creation"])
        self.setStyleSheet(
            f"QFrame#dendroNode {{ background: {bg}; border: 1px solid {border}; "
            "border-radius: 36px; }} "
            f"QFrame#dendroNode:hover {{ background: #FBFAF4; border: 2px solid {fg}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)
        layout.addStretch(1)

        icon = QLabel(glyph)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"font-size: 38px; color: {fg}; background: transparent; border: none;")
        layout.addWidget(icon)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(
            f"font-size: 24px; font-weight: 700; color: {fg}; "
            "font-family: Georgia, 'Courier New', serif; background: transparent; border: none;"
        )
        layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("font-size: 13px; color: #6E705E; background: transparent; border: none;")
        layout.addWidget(subtitle_label)
        layout.addStretch(1)

        self._hint = QLabel("Entrar")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(
            f"font-size: 12px; color: {fg}; background: transparent; border: none; letter-spacing: 1px;"
        )
        layout.addWidget(self._hint)


class QuietIconButton(QPushButton):
    """Small grouped action button used on the Home surface."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.45); border: 1px solid #D8D6C8; "
            "border-radius: 18px; padding: 8px 14px; color: #6F6A42; font-size: 12px; } "
            "QPushButton:hover { background: #F8F5EA; border: 1px solid #AFA77A; color: #504B2E; }"
        )


class HomeView(QWidget):
    """Dendro home: three connected narrative spaces + grouped configuration."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._callbacks: dict[str, Callable] = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget()
        content.setObjectName("dendroHome")
        content.setStyleSheet(
            "QWidget#dendroHome { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, "
            "stop:0 #F7F5EA, stop:0.55 #EEEEDF, stop:1 #E8E8DC); }"
        )
        layout = QVBoxLayout(content)
        layout.setContentsMargins(64, 42, 64, 34)
        layout.setSpacing(24)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self._project_label = QLabel("Dendro")
        self._project_label.setStyleSheet(
            "font-size: 42px; font-weight: 600; color: #67643A; "
            "font-family: Georgia, 'Courier New', serif; background: transparent; border: none;"
        )
        title_box.addWidget(self._project_label)
        self._subtitle_label = QLabel("Un escritorio tranquilo para crear mundos, relatos y sesiones.")
        self._subtitle_label.setStyleSheet("font-size: 14px; color: #7C806E; background: transparent; border: none;")
        title_box.addWidget(self._subtitle_label)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 12px; color: #8C8A74; background: transparent; border: none;")
        title_box.addWidget(self._status_label)
        top.addLayout(title_box)
        top.addStretch(1)

        self._btn_project = QuietIconButton("◇ Proyecto")
        self._btn_config = QuietIconButton("⚙ Configuración")
        self._advanced_indicator = Badge("Avanzado", "warning")
        self._advanced_indicator.setVisible(False)
        self._btn_project.clicked.connect(lambda: self._action("project_menu"))
        self._btn_config.clicked.connect(lambda: self._action("config_menu"))
        top.addWidget(self._advanced_indicator)
        top.addWidget(self._btn_project)
        top.addWidget(self._btn_config)
        layout.addLayout(top)

        layout.addStretch(1)

        node_row = QHBoxLayout()
        node_row.setSpacing(20)
        self.creation_card = HomeNode(
            "Creación",
            "Grafo, entidades, relaciones y semillas narrativas.",
            "✧",
            "creation",
        )
        self.gallery_card = HomeNode(
            "Galería",
            "Material narrativo como tarjetas, referencias y hallazgos.",
            "◌",
            "gallery",
        )
        self.session_card = HomeNode(
            "Sesión",
            "Preparación, mesa viva y cierre de partida.",
            "☉",
            "session",
        )
        self.creation_card.mousePressEvent = lambda event: self._navigate("creation")
        self.gallery_card.mousePressEvent = lambda event: self._navigate("gallery")
        self.session_card.mousePressEvent = lambda event: self._navigate("session")
        node_row.addStretch(1)
        node_row.addWidget(self.creation_card, 3)
        node_row.addWidget(self._branch("━━"))
        node_row.addWidget(self.gallery_card, 3)
        node_row.addWidget(self._branch("━━"))
        node_row.addWidget(self.session_card, 3)
        node_row.addStretch(1)
        layout.addLayout(node_row, stretch=4)

        self._normal_paths = QLabel(
            "Modo normal: crea entidades desde el grafo, revisa sugerencias, organiza fuentes y capas sin tablas técnicas."
        )
        self._normal_paths.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._normal_paths.setWordWrap(True)
        self._normal_paths.setStyleSheet("font-size: 13px; color: #777660; background: transparent; border: none;")
        layout.addWidget(self._normal_paths)
        layout.addStretch(1)

        root.addWidget(make_scroll_area(content))

        self._fade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fade)
        self._fade.setOpacity(1.0)

    def _branch(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 22px; color: #B4B29B; background: transparent; border: none;")
        label.setMinimumWidth(44)
        return label

    def register_callback(self, name: str, callback: Callable):
        self._callbacks[name] = callback

    def set_advanced_mode(self, enabled: bool):
        self._advanced_indicator.setVisible(bool(enabled))

    def animate_arrival(self):
        self._fade.setOpacity(0.7)
        animation = QPropertyAnimation(self._fade, b"opacity", self)
        animation.setDuration(220)
        animation.setStartValue(0.7)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _navigate(self, space: str):
        cb = self._callbacks.get(f"navigate_{space}")
        if cb:
            cb()

    def _action(self, action: str):
        cb = self._callbacks.get(action)
        if cb:
            cb()

    def refresh(self):
        pc = self.ctx.project_controller
        p = pc.ps.active_project if pc else None
        if p is None:
            self._project_label.setText("Dendro")
            self._subtitle_label.setText("Un escritorio tranquilo para crear mundos, relatos y sesiones.")
            self._status_label.setText("Abre o crea un proyecto para comenzar.")
            return
        name = getattr(p, "name", "Sin nombre") or "Sin nombre"
        self._project_label.setText("Dendro")
        self._subtitle_label.setText(name)
        self._status_label.setText("Proyecto activo")
