"""HomeView — Immersive home portal for B31.

Replaces the sidebar-driven navigation with three large entry cards
(Creación, Galería, Sesión) and a discrete project/config zone.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.design_system import (
    Badge,
    SectionHeader,
    make_scroll_area,
)


# ── Home entry card ──────────────────────────────────────────────────────────

class HomeEntryCard(QFrame):
    """Large clickable card representing one of the three main spaces."""

    def __init__(
        self,
        title: str,
        description: str,
        icon_text: str = "",
        tone: str = "info",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("homeCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(200)

        tone_colors = {
            "creation": ("#1A2744", "#3B6BDF", "#7DA4FF"),
            "gallery": ("#1F3A2A", "#2E8B57", "#7DCEA0"),
            "session": ("#3A1F2A", "#8B3A62", "#CE7DA0"),
        }
        bg, accent, fg = tone_colors.get(tone, ("#1A2744", "#3B6BDF", "#7DA4FF"))
        self._bg = bg
        self._accent = accent

        self.setStyleSheet(
            f"QFrame#homeCard {{ background: {bg}; border: 2px solid {accent}33; "
            f"border-radius: 18px; }} "
            f"QFrame#homeCard:hover {{ border: 2px solid {accent}; "
            f"background: {bg}CC; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        # Icon row
        icon_label = QLabel(icon_text)
        icon_label.setStyleSheet(
            f"font-size: 36px; color: {fg}; background: transparent; border: none;"
        )
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 22px; font-weight: 800; color: {fg}; "
            "background: transparent; border: none;"
        )
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            "font-size: 13px; color: #A0B0C4; background: transparent; border: none;"
        )
        layout.addWidget(desc_label)

        layout.addStretch()

        # Status area (populated on refresh)
        self._status_row = QHBoxLayout()
        self._status_row.setSpacing(8)
        layout.addLayout(self._status_row)

    def set_status(self, badges: list[tuple[str, str]]):
        """Set status badges. Each tuple is (text, tone)."""
        while self._status_row.count():
            item = self._status_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for text, tone in badges:
            self._status_row.addWidget(Badge(text, tone))
        self._status_row.addStretch()


# ── Config action button (small, icon-style) ─────────────────────────────────

class ConfigButton(QPushButton):
    """Small discrete button for the project/config zone."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #2B3546; "
            "border-radius: 8px; padding: 6px 12px; color: #8993A5; font-size: 12px; } "
            "QPushButton:hover { background: #1A2030; color: #CDD5E0; }"
        )


# ── HomeView ─────────────────────────────────────────────────────────────────

class HomeView(QWidget):
    """Immersive home portal with three space entries and discrete config."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._callbacks: dict[str, callable] = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Scrollable content
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(60, 40, 60, 40)
        layout.setSpacing(32)

        # Header zone
        header = QVBoxLayout()
        header.setSpacing(4)
        self._project_label = QLabel("Narrative Architect")
        self._project_label.setStyleSheet(
            "font-size: 28px; font-weight: 800; color: #ECEFF4; "
            "background: transparent; border: none;"
        )
        header.addWidget(self._project_label)

        self._subtitle_label = QLabel("Espacio de creación narrativa")
        self._subtitle_label.setStyleSheet(
            "font-size: 14px; color: #6B7A8D; background: transparent; border: none;"
        )
        header.addWidget(self._subtitle_label)

        self._status_label = QLabel("")
        self._status_label.setObjectName("mutedLabel")
        self._status_label.setStyleSheet("font-size: 12px; background: transparent; border: none;")
        header.addWidget(self._status_label)
        layout.addLayout(header)

        # Three entry cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(20)

        self.creation_card = HomeEntryCard(
            "Creación",
            "Explora y construye tu mundo narrativo con un grafo interactivo.",
            icon_text="✦",
            tone="creation",
        )
        self.creation_card.clicked = lambda: self._navigate("creation")

        self.gallery_card = HomeEntryCard(
            "Galería",
            "Contempla y explora tus personajes, lugares y elementos.",
            icon_text="◈",
            tone="gallery",
        )
        self.gallery_card.clicked = lambda: self._navigate("gallery")

        self.session_card = HomeEntryCard(
            "Sesión",
            "Prepara, dirige y cierra sesiones de rol en un espacio inmersivo.",
            icon_text="⚔",
            tone="session",
        )
        self.session_card.clicked = lambda: self._navigate("session")

        for card in [self.creation_card, self.gallery_card, self.session_card]:
            card.mousePressEvent = lambda event, c=card: self._on_card_click(c, event)
            cards_row.addWidget(card)

        layout.addLayout(cards_row, stretch=1)

        # Discrete config zone
        config_zone = QFrame()
        config_zone.setObjectName("configZone")
        config_zone.setStyleSheet(
            "QFrame#configZone { background: transparent; border: none; }"
        )
        cfg_layout = QHBoxLayout(config_zone)
        cfg_layout.setContentsMargins(0, 0, 0, 0)
        cfg_layout.setSpacing(8)

        self._btn_new = ConfigButton("Nuevo")
        self._btn_open = ConfigButton("Abrir")
        self._btn_save = ConfigButton("Guardar")
        self._btn_close = ConfigButton("Cerrar")
        self._btn_settings = ConfigButton("Ajustes IA")
        self._btn_advanced = ConfigButton("Modo avanzado")
        self._btn_diagnostic = ConfigButton("Diagnóstico")
        self._advanced_indicator = Badge("Modo avanzado activo", "info")
        self._advanced_indicator.setVisible(False)

        self._btn_new.clicked.connect(lambda: self._action("new_project"))
        self._btn_open.clicked.connect(lambda: self._action("open_project"))
        self._btn_save.clicked.connect(lambda: self._action("save_project"))
        self._btn_close.clicked.connect(lambda: self._action("close_project"))
        self._btn_settings.clicked.connect(lambda: self._action("ai_settings"))
        self._btn_advanced.clicked.connect(lambda: self._action("toggle_advanced"))
        self._btn_diagnostic.clicked.connect(lambda: self._action("toggle_diagnostic"))

        for btn in [
            self._btn_new, self._btn_open, self._btn_save, self._btn_close,
            self._btn_settings, self._btn_advanced, self._btn_diagnostic,
        ]:
            cfg_layout.addWidget(btn)
        cfg_layout.addWidget(self._advanced_indicator)
        cfg_layout.addStretch()

        layout.addWidget(config_zone)
        root.addWidget(make_scroll_area(content))

    def _on_card_click(self, card: HomeEntryCard, event):
        mapping = {
            id(self.creation_card): "creation",
            id(self.gallery_card): "gallery",
            id(self.session_card): "session",
        }
        space = mapping.get(id(card))
        if space:
            self._navigate(space)

    def _navigate(self, space: str):
        cb = self._callbacks.get(f"navigate_{space}")
        if cb:
            cb()

    def _action(self, action: str):
        cb = self._callbacks.get(action)
        if cb:
            cb()

    def register_callback(self, name: str, callback: callable):
        self._callbacks[name] = callback

    def set_advanced_mode(self, enabled: bool):
        self._btn_advanced.setText("Modo avanzado: ON" if enabled else "Modo avanzado")
        self._btn_diagnostic.setVisible(bool(enabled))
        self._advanced_indicator.setVisible(bool(enabled))
        self._btn_advanced.setStyleSheet(
            "QPushButton { background: #263244; border: 1px solid #5B7CFA; "
            "border-radius: 8px; padding: 6px 12px; color: #7DA4FF; font-size: 12px; } "
            if enabled else
            "QPushButton { background: transparent; border: 1px solid #2B3546; "
            "border-radius: 8px; padding: 6px 12px; color: #8993A5; font-size: 12px; } "
            "QPushButton:hover { background: #1A2030; color: #CDD5E0; }"
        )

    def refresh(self):
        pc = self.ctx.project_controller
        if pc is None:
            return
        p = pc.ps.active_project if pc else None
        if p is None:
            self._project_label.setText("Narrative Architect")
            self._subtitle_label.setText("Abre o crea un proyecto para comenzar")
            self._status_label.setText("")
            self.creation_card.set_status([])
            self.gallery_card.set_status([])
            self.session_card.set_status([])
            return

        name = getattr(p, "name", "Sin nombre")
        self._project_label.setText(f"Narrative Architect")
        self._subtitle_label.setText(name)

        schema = getattr(p, "schema_version", "?")
        self._status_label.setText(f"Schema v{schema}")

        # Card status badges
        entities = getattr(p, "entities", []) or []
        relations = getattr(p, "relations", []) or []
        campaigns = getattr(p, "campaigns", []) or []
        sessions = getattr(p, "sessions", []) or []
        factions = getattr(p, "factions", []) or []

        self.creation_card.set_status([
            (f"{len(entities)} entidades", "info"),
            (f"{len(relations)} relaciones", "neutral"),
        ])
        self.gallery_card.set_status([
            (f"{len(entities)} elementos", "success"),
        ])
        self.session_card.set_status([
            (f"{len(campaigns)} campañas", "info"),
            (f"{len(sessions)} sesiones", "neutral"),
        ])
