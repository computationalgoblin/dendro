"""Minimal desktop design-system widgets for B27.5 UX redesign.

These widgets are intentionally presentation-only. They do not import persistence
or infrastructure and do not mutate domain objects directly.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import Qt, QEasingCurve, QEvent, QObject, QParallelAnimationGroup, QPropertyAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


# ─────────────────────────────────────────────────────────────────────────
# Dendro — paleta con identidad ("tinta, pergamino y oro botánico")
#
# Una sola fuente de verdad para el color. Pergamino cálido con una escalera
# tonal real (de hundido a elevado), tinta profunda para contraste serio, y un
# ÚNICO acento de oro-oliva con carácter para las acciones. La estética sigue
# siendo orgánica y editorial; lo que cambia es la PROFUNDIDAD y el aplomo.
# ─────────────────────────────────────────────────────────────────────────

# Superficies (escalera cálida: de lo hundido a lo elevado)
PAPER       = "#E8E1CF"   # base de la app (detrás de todo)
CANVAS      = "#E6DFCD"   # lienzo del grafo (con viñeta propia)
WELL        = "#DDD5BF"   # carriles/pozos hundidos
SURFACE     = "#F4EFE1"   # tarjetas, cajones
SURFACE_HI  = "#FBF8EF"   # tarjetas elevadas, barras flotantes
INPUT_BG    = "#FFFDF8"   # campos de texto

# Tinta (texto) — más profunda y cálida, para contraste profesional
INK_STRONG  = "#34301E"
INK         = "#45402E"
INK_SOFT    = "#6E6950"
INK_MUTED   = "#948C6E"

# Líneas y bordes
LINE        = "#D2CAB1"
LINE_SOFT   = "#E3DCC8"
LINE_STRONG = "#BCB28E"

# Acento — oro-oliva (identidad / acciones)
GOLD        = "#8B7A36"
GOLD_DEEP   = "#6E622E"
GOLD_SOFT   = "#BBAA66"
GOLD_TINT   = "#ECE4C7"   # relleno sutil de acento (hover/selección)

# Verde botánico (secundario, con mucha mesura: vida, foco orgánico)
SAGE        = "#6E7E58"
SAGE_DEEP   = "#54624330"  # noqa: usado solo como referencia documental

# Sombra cálida base (RGB) — las sombras nunca son grises neutros aquí
SHADOW_RGB  = (52, 47, 28)


def _qss() -> str:
    """Hoja de estilo global construida desde la paleta (una sola verdad)."""
    return f"""
QMainWindow, QWidget {{
    background: {PAPER};
    color: {INK};
    font-family: "Georgia", "Iowan Old Style", "Palatino Linotype", serif;
    font-size: 13px;
}}
QToolTip {{
    background: {INK_STRONG};
    color: {SURFACE_HI};
    border: 1px solid {GOLD_DEEP};
    border-radius: 6px;
    padding: 5px 8px;
}}
QPushButton {{
    background: {SURFACE_HI};
    border: 1px solid {LINE};
    border-radius: 11px;
    padding: 8px 14px;
    color: {INK_SOFT};
    font-weight: 600;
}}
QPushButton:hover {{ background: {INPUT_BG}; border-color: {GOLD_SOFT}; color: {INK_STRONG}; }}
QPushButton:focus {{ border: 2px solid {GOLD}; padding: 7px 13px; }}
QPushButton:pressed {{ background: {WELL}; padding-top: 9px; padding-bottom: 7px; }}
QPushButton:disabled {{ background: {SURFACE}; color: {INK_MUTED}; border-color: {LINE_SOFT}; }}
QPushButton#primaryButton {{
    background: {GOLD};
    border: 1px solid {GOLD_DEEP};
    color: #FCF8EC;
    font-weight: 700;
    padding: 9px 16px;
}}
QPushButton#primaryButton:hover {{ background: {GOLD_DEEP}; border-color: {GOLD_DEEP}; }}
QPushButton#primaryButton:pressed {{ background: #5E5427; }}
QPushButton#primaryButton:disabled {{ background: {GOLD_SOFT}; color: {SURFACE}; border-color: {GOLD_SOFT}; }}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 6px 8px;
    color: {INK_SOFT};
}}
QToolButton:hover {{ background: {SURFACE_HI}; border-color: {LINE}; color: {INK_STRONG}; }}
QToolButton:checked {{ background: {GOLD_TINT}; border-color: {GOLD_SOFT}; color: {INK_STRONG}; }}
QLabel#mutedLabel {{ color: {INK_MUTED}; }}
QLabel#sectionTitle {{
    font-size: 19px;
    font-weight: 700;
    color: {INK_STRONG};
    font-family: Georgia, "Iowan Old Style", serif;
}}
QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QTableWidget, QSpinBox, QDoubleSpinBox {{
    background: {INPUT_BG};
    border: 1px solid {LINE};
    border-radius: 9px;
    color: {INK};
    padding: 8px 10px;
    min-height: 28px;
    selection-background-color: {GOLD_SOFT};
    selection-color: {INK_STRONG};
    font-family: "Segoe UI", "Inter", "Helvetica Neue", "Arial";
}}
QTextEdit:hover, QPlainTextEdit:hover, QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{
    border-color: {LINE_STRONG};
}}
QTextEdit:focus, QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {GOLD};
    background: #FFFFFF;
    padding: 7px 9px;
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background: {SURFACE};
    color: {INK_MUTED};
    border-color: {LINE_SOFT};
}}
QComboBox {{ min-height: 32px; padding: 6px 28px 6px 10px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {INK_SOFT};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {INPUT_BG};
    border: 1px solid {LINE};
    border-radius: 9px;
    color: {INK};
    selection-background-color: {GOLD_TINT};
    selection-color: {INK_STRONG};
    padding: 4px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{ padding: 7px 8px; min-height: 28px; color: {INK}; border-radius: 6px; }}
QComboBox QAbstractItemView::item:hover {{ background: {SURFACE}; }}
QComboBox QAbstractItemView::item:selected {{ background: {GOLD_TINT}; color: {INK_STRONG}; }}
QTextEdit, QPlainTextEdit {{ min-height: 60px; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 14px; background: {SURFACE}; }}
QTabBar::tab {{
    background: transparent;
    color: {INK_MUTED};
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}}
QTabBar::tab:hover {{ color: {INK_SOFT}; }}
QTabBar::tab:selected {{ color: {INK_STRONG}; border-bottom: 2px solid {GOLD}; }}
QTableWidget {{ gridline-color: {LINE_SOFT}; }}
QHeaderView::section {{ background: {SURFACE}; color: {INK_SOFT}; padding: 7px; border: none; font-weight: 600; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {LINE_STRONG}; border-radius: 5px; min-height: 34px; }}
QScrollBar::handle:vertical:hover {{ background: {GOLD_SOFT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {LINE_STRONG}; border-radius: 5px; min-width: 34px; }}
QScrollBar::handle:horizontal:hover {{ background: {GOLD_SOFT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
"""


APP_STYLESHEET = _qss()


# ─────────────────────────────────────────────────────────────────────────
# Elevación y movimiento — la profundidad y las microanimaciones que dan
# aplomo "de producto". Todo falla en silencio: el pulido nunca rompe la lógica.
# ─────────────────────────────────────────────────────────────────────────

def apply_shadow(
    widget: QWidget,
    *,
    blur: float = 26.0,
    y: float = 8.0,
    x: float = 0.0,
    alpha: int = 48,
) -> QGraphicsDropShadowEffect:
    """Sombra cálida suave para dar elevación a una superficie."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setXOffset(x)
    effect.setYOffset(y)
    effect.setColor(QColor(SHADOW_RGB[0], SHADOW_RGB[1], SHADOW_RGB[2], alpha))
    widget.setGraphicsEffect(effect)
    return effect


class _HoverLift(QObject):
    """Filtro de eventos que ELEVA una superficie al pasar el ratón.

    Anima la sombra (blur + desplazamiento) para que la tarjeta/botón parezca
    despegarse del lienzo. Movimiento sutil, ~150 ms, OutCubic."""

    def __init__(
        self,
        widget: QWidget,
        *,
        rest_blur: float,
        rest_y: float,
        rest_alpha: int,
        lift_blur: float,
        lift_y: float,
        lift_alpha: int,
        duration: int = 160,
    ):
        super().__init__(widget)
        self._w = widget
        self._rest = (rest_blur, rest_y, rest_alpha)
        self._lift = (lift_blur, lift_y, lift_alpha)
        self._duration = duration
        self._effect = apply_shadow(widget, blur=rest_blur, y=rest_y, alpha=rest_alpha)
        self._group: QParallelAnimationGroup | None = None
        widget.installEventFilter(self)

    def _animate_to(self, blur: float, y: float, alpha: int):
        try:
            if self._group is not None:
                self._group.stop()
            group = QParallelAnimationGroup(self)
            for prop, end in ((b"blurRadius", blur), (b"yOffset", y)):
                anim = QPropertyAnimation(self._effect, prop)
                anim.setDuration(self._duration)
                anim.setEndValue(end)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                group.addAnimation(anim)
            color = QColor(SHADOW_RGB[0], SHADOW_RGB[1], SHADOW_RGB[2], alpha)
            self._effect.setColor(color)
            self._group = group
            group.start()
        except Exception:  # noqa: BLE001
            pass

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        etype = event.type()
        if etype == QEvent.Type.Enter:
            self._animate_to(*self._lift)
        elif etype == QEvent.Type.Leave:
            self._animate_to(*self._rest)
        return False


def install_hover_lift(
    widget: QWidget,
    *,
    rest_blur: float = 20.0,
    rest_y: float = 6.0,
    rest_alpha: int = 38,
    lift_blur: float = 38.0,
    lift_y: float = 12.0,
    lift_alpha: int = 64,
    duration: int = 160,
) -> _HoverLift | None:
    """Instala una elevación-al-hover sobre *widget* y devuelve el filtro."""
    try:
        return _HoverLift(
            widget,
            rest_blur=rest_blur, rest_y=rest_y, rest_alpha=rest_alpha,
            lift_blur=lift_blur, lift_y=lift_y, lift_alpha=lift_alpha,
            duration=duration,
        )
    except Exception:  # noqa: BLE001
        return None


ICON_GLYPHS = {
    "settings": "⚙",
    "project": "◇",
    "creation": "✧",
    "gallery": "◌",
    "session": "☉",
    "back": "←",
    "close": "✕",
    "add": "+",
    "edit": "✎",
    "delete": "✕",
    "refresh": "↻",
    "save": "💾",
    "search": "⌕",
    "filter": "▽",
    "expand": "▾",
    "collapse": "▸",
    "worldbuilding": "🌐",
    "layers": "☰",
}


class Card(QFrame):
    """Soft bordered card used by normal-mode product UI.

    Ahora con elevación real (sombra cálida) y, opcionalmente, una leve
    elevación al pasar el ratón — el aplomo "de producto"."""

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        parent: QWidget | None = None,
        *,
        elevated: bool = True,
        hover: bool = True,
    ):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame#card {{ background: {SURFACE_HI}; border: 1px solid {LINE}; "
            f"border-radius: 16px; }}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 14, 16, 14)
        self.layout.setSpacing(8)
        if title:
            self.title = QLabel(title)
            self.title.setStyleSheet(
                f"font-size: 16px; font-weight: 700; color: {INK_STRONG}; background: transparent;"
            )
            self.title.setWordWrap(True)
            self.layout.addWidget(self.title)
        if subtitle:
            self.subtitle = QLabel(subtitle)
            self.subtitle.setObjectName("mutedLabel")
            self.subtitle.setWordWrap(True)
            self.layout.addWidget(self.subtitle)
        # BETA1-G08: la elevación de las tarjetas se consigue por CONTRASTE
        # (SURFACE_HI brillante sobre superficies más profundas) + borde, NO con
        # QGraphicsDropShadowEffect. Las tarjetas viven en scroll areas y se
        # reconstruyen al refrescar; un efecto gráfico ahí cachea el render y
        # deja menús/botones en blanco al cambiar. La estabilidad manda.
        self._elevated = bool(elevated)
        self._hover = bool(hover)

    def add_text(self, text: str, muted: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        if muted:
            label.setObjectName("mutedLabel")
        self.layout.addWidget(label)
        return label

    def add_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self.layout.addLayout(row)
        return row


class Badge(QLabel):
    """Small chip/badge for user-facing states."""

    def __init__(self, text: str, tone: str = "neutral", parent: QWidget | None = None):
        super().__init__(text, parent)
        colors = {
            "neutral": (GOLD_TINT, INK_SOFT),
            "info": ("#DDE4D6", "#566B47"),
            "success": ("#DCE8D2", "#4F6E3F"),
            "warning": ("#EFE2C3", "#8A6534"),
            "danger": ("#EFD4C9", "#8C4A3C"),
            "gold": (GOLD, "#FCF8EC"),
        }
        bg, fg = colors.get(tone, colors["neutral"])
        self.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 9px; "
            "padding: 3px 9px; font-size: 12px; font-weight: 700;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("mutedLabel")
            sub.setWordWrap(True)
            layout.addWidget(sub)


class EmptyState(Card):
    def __init__(self, title: str, message: str, parent: QWidget | None = None):
        super().__init__(title, message, parent, elevated=False)
        self.setStyleSheet(
            f"QFrame#card {{ background: {SURFACE}; border: 1px dashed {LINE_STRONG}; "
            f"border-radius: 14px; }}"
        )


class AdvancedSection(QWidget):
    """Collapsible container for technical details visible only in advanced mode."""

    def __init__(self, title: str = "Datos técnicos", parent: QWidget | None = None):
        super().__init__(parent)
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.body = QWidget()
        self.body.setVisible(False)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 6, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)
        self.toggle.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.body.setVisible(checked)
        fade_in(self.body, duration_ms=140 if checked else 90, start_opacity=0.70 if checked else 1.0)


def fade_in(widget: QWidget, *, duration_ms: int = 180, start_opacity: float = 0.0):
    """Subtle opacity transition for content that appears inside the shell.

    Presentation-only helper: no domain/persistence side effects. It intentionally
    fails closed so visual polish never breaks workflow logic.
    """
    try:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(start_opacity)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(duration_ms)
        animation.setStartValue(start_opacity)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    except Exception:
        pass


def pulse_feedback(widget: QWidget, *, duration_ms: int = 220):
    """Quick tactile feedback for successful/acknowledged actions."""
    try:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(duration_ms)
        animation.setStartValue(0.62)
        animation.setKeyValueAt(0.45, 1.0)
        animation.setEndValue(0.92)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: effect.setOpacity(1.0))
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    except Exception:
        pass


def make_scroll_area(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(content)
    return area


def enum_human(value: Any) -> str:
    raw = getattr(value, "value", value)
    text = str(raw or "—")
    return text.replace("_", " ").replace("-", " ").strip().capitalize() or "—"


def human_ref(name: str | None, kind: str | None = None) -> str:
    clean_name = (name or "Sin nombre").strip() or "Sin nombre"
    clean_kind = (kind or "").strip()
    return f"{clean_name} · {clean_kind}" if clean_kind else clean_name


def join_human(items: Iterable[Any], empty: str = "—") -> str:
    values = [str(item) for item in items if str(item)]
    return ", ".join(values) if values else empty
