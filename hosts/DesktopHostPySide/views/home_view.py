"""HomeView — Dendro home portal (BETA 1: single Creación card).

Normal mode is intentionally non-technical: no schema, no provider status, no
counts, no raw IDs. Project/config actions are grouped behind quiet icon buttons
placed at the bottom corners of the home surface.

BETA1-A04 note: originally a three-space portal (B31). Gallery/Session cards
were disconnected in A01; some internal helpers (_BranchLine, gallery/session
tones) remain classified as LEGACY INTERNO — see
docs/architecture/A03_legacy_classification.md.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
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
from hosts.DesktopHostPySide.widgets.design_system import Badge, make_scroll_area, ICON_GLYPHS


class HomeNode(QFrame):
    """Soft clickable node for a Dendro product space (BETA 1: Creación)."""

    def __init__(self, title: str, subtitle: str, glyph: str, tone: str, ctx=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._ctx = ctx
        self.setObjectName("dendroNode")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(230, 230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tone = tone
        self._fg_default = ""
        self._bg_default = ""
        self._border_default = ""
        self._apply_tone_style(tone)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)
        layout.addStretch(1)

        self._icon = QLabel(glyph)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            f"font-size: 38px; color: {self._fg_default}; background: transparent; border: none;"
        )
        layout.addWidget(self._icon)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(
            f"font-size: 24px; font-weight: 700; color: {self._fg_default}; "
            "font-family: Georgia, 'Courier New', serif; background: transparent; border: none;"
        )
        layout.addWidget(self._title_label)

        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setStyleSheet(
            "font-size: 13px; color: #6E705E; background: transparent; border: none;"
        )
        layout.addWidget(self._subtitle_label)

        # Worldbuilding indicator placeholder (hidden by default)
        self._wb_label = QLabel(f"{ICON_GLYPHS['worldbuilding']} Capas")
        self._wb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wb_label.setStyleSheet(
            "font-size: 11px; color: #7A733D; background: transparent; border: none; "
            "margin-top: 2px;"
        )
        self._wb_label.setVisible(False)
        layout.addWidget(self._wb_label)

        layout.addStretch(1)

        self._hint = QLabel("Entrar")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(
            f"font-size: 12px; color: {self._fg_default}; background: transparent; border: none; letter-spacing: 1px;"
        )
        layout.addWidget(self._hint)

        # Opacity effect for dimmed state and zoom animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

    def _apply_tone_style(self, tone: str):
        tones = {
            "creation": ("#F7F4EA", "#7A733D", "#AFA77A"),
            "gallery": ("#F3F5EE", "#6E7B59", "#B5BBA5"),
            "session": ("#F6F1E8", "#8A6849", "#C8AF8C"),
        }
        bg, fg, border = tones.get(tone, tones["creation"])
        self._bg_default = bg
        self._fg_default = fg
        self._border_default = border
        self.setStyleSheet(
            f"QFrame#dendroNode {{ background: {bg}; border: 1px solid {border}; "
            "border-radius: 36px; }} "
            f"QFrame#dendroNode:hover {{ background: #FBFAF4; border: 2px solid {fg}; }}"
        )

    def set_dimmed(self, dimmed: bool):
        """Set dimmed/disabled appearance when no project is loaded."""
        if dimmed:
            self._opacity_effect.setOpacity(0.45)
            self._subtitle_label.setText("Abre o crea un proyecto")
        else:
            self._opacity_effect.setOpacity(1.0)

    def set_worldbuilding_indicator(self, active: bool):
        """Show or hide the worldbuilding 'Capas' indicator."""
        self._wb_label.setVisible(active)

    def animate_zoom_in(self, on_finished: Callable):
        """Fade to 0.6 opacity over 250ms, then call on_finished."""
        self._opacity_effect.setOpacity(1.0)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        duration = self._ctx.animation_duration(250) if self._ctx else 250
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.6)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(on_finished)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def animate_restore(self):
        """Restore opacity back to 1.0."""
        self._opacity_effect.setOpacity(0.6)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        duration = self._ctx.animation_duration(200) if self._ctx else 200
        anim.setDuration(duration)
        anim.setStartValue(0.6)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class QuietIconButton(QPushButton):
    """Small grouped action button used on the Home surface.

    When constructed with a glyph only (icon_only=True), renders as a round
    32x32 button with the glyph centred and no text label.
    """

    def __init__(self, glyph: str, label: str = "", icon_only: bool = False, parent: QWidget | None = None):
        if icon_only:
            super().__init__(glyph, parent)
        else:
            super().__init__(f"{glyph} {label}" if label else glyph, parent)
        self._icon_only = icon_only
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon_only:
            self.setFixedSize(QSize(32, 32))
            self.setStyleSheet(
                "QPushButton { background: rgba(255,255,255,0.45); border: 1px solid #D8D6C8; "
                "border-radius: 16px; padding: 0px; color: #6F6A42; font-size: 16px; } "
                "QPushButton:hover { background: #F8F5EA; border: 1px solid #AFA77A; color: #504B2E; }"
            )
        else:
            self.setStyleSheet(
                "QPushButton { background: rgba(255,255,255,0.45); border: 1px solid #D8D6C8; "
                "border-radius: 18px; padding: 8px 14px; color: #6F6A42; font-size: 12px; } "
                "QPushButton:hover { background: #F8F5EA; border: 1px solid #AFA77A; color: #504B2E; }"
            )


class _BranchLine(QFrame):
    """Visual connector (thin vertical line) between the cards and a central hub."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(2)
        self.setMinimumHeight(24)
        self.setStyleSheet("background: #C9C5B1; border: none;")


class HomeView(QWidget):
    """Dendro home: Creación space + grouped configuration (BETA 1)."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._callbacks: dict[str, Callable] = {}
        self._current_project_type: str = "otro"
        self._current_worldbuilding: bool = False
        self._project_loaded: bool = False
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

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
        layout.setSpacing(20)

        # ---- Top: title area ----
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
        self._continue_btn = QuietIconButton("↳", "Continuar", icon_only=False)
        self._continue_btn.setVisible(False)
        self._continue_btn.clicked.connect(lambda: self._action("open_last_project"))
        title_box.addWidget(self._continue_btn)
        layout.addLayout(title_box)

        # Advanced indicator (kept from original, hidden by default)
        self._advanced_indicator = Badge("Avanzado", "warning")
        self._advanced_indicator.setVisible(False)
        layout.addWidget(self._advanced_indicator)

        layout.addStretch(1)

        # ---- Middle: node cards ----
        # BETA1-A01: only the Creation card is part of the runtime.
        # Gallery/Session cards removed from Home (their workspaces are
        # disconnected from the stack in MainWindow).

        cards_container = QVBoxLayout()
        cards_container.setSpacing(0)
        cards_container.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Horizontal wrapper to centre cards
        cards_row = QHBoxLayout()
        cards_row.addStretch(1)

        cards_col = QVBoxLayout()
        cards_col.setSpacing(0)
        cards_col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.creation_card = HomeNode(
            "Creación",
            "Grafo, entidades, relaciones y semillas narrativas.",
            ICON_GLYPHS["creation"],
            "creation",
            ctx=self.ctx,
        )

        self.creation_card.mousePressEvent = lambda event: self._navigate("creation")
        self.creation_card.setToolTip("Entrar en Creación: grafo, hojas, ramas, relaciones y sugerencias IA")

        cards_col.addWidget(self.creation_card, 3)

        cards_row.addLayout(cards_col)
        cards_row.addStretch(1)
        layout.addLayout(cards_row, stretch=4)

        layout.addStretch(1)

        # ---- Bottom: icon-only buttons at corners ----
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)

        self._btn_config = QuietIconButton(ICON_GLYPHS["settings"], icon_only=True)
        self._btn_config.clicked.connect(lambda: self._action("config_menu"))
        bottom_row.addWidget(self._btn_config)

        bottom_row.addStretch(1)

        self._btn_project = QuietIconButton(ICON_GLYPHS["project"], icon_only=True)
        self._btn_project.clicked.connect(lambda: self._action("project_menu"))
        bottom_row.addWidget(self._btn_project)

        layout.addLayout(bottom_row)

        root.addWidget(make_scroll_area(content))

        # Whole-view fade effect for animate_arrival
        self._fade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fade)
        self._fade.setOpacity(1.0)

    def _branch_line(self) -> QFrame:
        """Return a thin vertical connector line between cards."""
        line = QFrame()
        line.setFixedHeight(18)
        line.setMinimumWidth(2)
        line.setMaximumWidth(60)
        line.setStyleSheet("background: transparent; border: none;")
        # Use a label with a decorative glyph for the branch
        inner = QHBoxLayout(line)
        inner.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("┃")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 18px; color: #C9C5B1; background: transparent; border: none;")
        inner.addWidget(lbl)
        return line

    # ------------------------------------------------------------------
    # Dynamic visibility
    # ------------------------------------------------------------------

    def update_project_visibility(self, project_type: str | None, worldbuilding_active: bool):
        """Update card indicators based on project metadata.

        BETA1-A01: only the Creation card exists on Home, so project_type no
        longer toggles card visibility. Rules kept:
          - worldbuilding_active → show "🌐 Capas" on creation card
          - No project loaded → card visible but dimmed
        """
        self._current_project_type = project_type or "otro"
        self._current_worldbuilding = worldbuilding_active

        # Worldbuilding indicator on creation card
        self.creation_card.set_worldbuilding_indicator(worldbuilding_active)

        # If no project is loaded, dim the card
        self.creation_card.set_dimmed(not self._project_loaded)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def register_callback(self, name: str, callback: Callable):
        self._callbacks[name] = callback

    def set_last_project_option(self, project_name: str | None):
        """Show a quiet Home action to continue the last valid project."""
        if project_name:
            self._continue_btn.setText(f"↳ Continuar con {project_name}")
            self._continue_btn.setVisible(True)
        else:
            self._continue_btn.setVisible(False)

    def set_advanced_mode(self, enabled: bool):
        # T05: Always hidden from UI — advanced mode kept internal only
        self._advanced_indicator.setVisible(False)

    # ------------------------------------------------------------------
    # Animations
    # ------------------------------------------------------------------

    def animate_arrival(self):
        """Restore all cards to full visibility (called when returning to Home).

        We reset the parent fade to 1.0 immediately (no animation) to avoid
        compounding opacity effects with the MainWindow stack-level animation
        and the per-card opacity effects. Cards that were left at 0.6 opacity
        from a previous zoom-in are restored to full opacity directly.
        """
        # Reset parent fade immediately — the MainWindow stack animation
        # already provides a fade-in; an additional parent fade would compound
        # (multiplicative) with card-level effects making cards invisible.
        if hasattr(self, '_fade') and self._fade:
            self._fade.setOpacity(1.0)

        # Force all visible cards to full opacity immediately.
        # Cards may be at 0.6 from a previous animate_zoom_in that never
        # finished its restore cycle.
        for card in (self.creation_card,):
            if card.isVisible() and hasattr(card, '_opacity_effect'):
                card._opacity_effect.setOpacity(1.0)

    def _animate_card_zoom(self, card: HomeNode, space: str):
        """Zoom/fade the card, then navigate once the animation finishes."""
        card.animate_zoom_in(lambda: self._do_navigate(space))

    def _do_navigate(self, space: str):
        cb = self._callbacks.get(f"navigate_{space}")
        if cb:
            cb()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate(self, space: str):
        # BETA1-A01: only Creation is navigable from Home
        if space == "creation" and not self._project_loaded:
            self._status_label.setText("Abre o crea un proyecto para entrar en Creación.")
            return
        card = {
            "creation": self.creation_card,
        }.get(space)
        if card and card.isVisible():
            self._animate_card_zoom(card, space)
        else:
            # Fallback: navigate immediately
            self._do_navigate(space)

    def _action(self, action: str):
        cb = self._callbacks.get(action)
        if cb:
            cb()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self):
        pc = self.ctx.project_controller
        p = pc.ps.active_project if pc else None

        if p is None:
            self._project_loaded = False
            self._project_label.setText("Dendro")
            self._subtitle_label.setText("Un escritorio tranquilo para crear mundos, relatos y sesiones.")
            self._status_label.setText("Abre o crea un proyecto para comenzar.")
            self.update_project_visibility(None, False)
            return

        self._project_loaded = True
        name = getattr(p, "name", "Sin nombre") or "Sin nombre"
        project_type = getattr(p, "project_type", "otro") or "otro"
        worldbuilding_active = getattr(p, "worldbuilding_active", False) or False

        self._project_label.setText("Dendro")
        self._subtitle_label.setText(name)
        self._status_label.setText("Proyecto activo")
        self.update_project_visibility(project_type, worldbuilding_active)
