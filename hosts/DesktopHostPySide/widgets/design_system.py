"""Minimal desktop design-system widgets for B27.5 UX redesign.

These widgets are intentionally presentation-only. They do not import persistence
or infrastructure and do not mutate domain objects directly.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
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
SAGE_DEEP   = "#546243"  # verde profundo (reservado; aún sin uso)

# Sombra cálida base (RGB) — las sombras nunca son grises neutros aquí
SHADOW_RGB  = (52, 47, 28)


# ─────────────────────────────────────────────────────────────────────────
# Cimientos del sistema (BETA1-UX01) — tokens transversales que dan
# COHESIÓN y APLOMO. Principios:
#   · Una sola voz de oro para la acción (nunca arcoíris).
#   · Profundidad por capas cálidas, nunca gris neutro.
#   · Movimiento "expresivo pero elegante": notable, pero al servicio de la calma.
#   · Radios coherentes: pocas medidas, repetidas con disciplina.
# ─────────────────────────────────────────────────────────────────────────

# Escala de radios (cohesión de formas)
RADIUS_SM   = 9    # chips, celdas, controles pequeños
RADIUS_MD   = 12   # botones, inputs, combos
RADIUS_LG   = 16   # tarjetas, cajones
RADIUS_PILL = 999  # botones-cápsula

# Espaciado: escala 4-pt única (en vez de valores mágicos dispersos por widget).
# Úsala para márgenes, padding y spacing de layouts. El ritmo espacial consistente
# es el factor invisible que más "ordena" una UI.
SPACE_XS  = 4   # micro: separación interna de chips, gaps mínimos
SPACE_SM  = 8   # estándar entre controles afines
SPACE_MD  = 12  # entre grupos dentro de un bloque
SPACE_LG  = 16  # márgenes de tarjeta/panel, separación de secciones
SPACE_XL  = 24  # aire entre secciones mayores
SPACE_2XL = 32  # respiración de cabeceras / zonas vacías

# Animación: cadencia única de los widgets que repintan por timer (~25 fps, barato).
# Una sola fuente del FPS en vez de "40" duplicado por widget.
TICK_INTERVAL = 40  # ms entre fotogramas de animaciones pintadas a mano

# Paleta cálida por tipo de entidad (BETA1-UX05): única fuente para nodos del grafo
# y paneles de detalle (antes duplicada idéntica en cada widget). Tonos botánicos
# coherentes con el pergamino, NUNCA azules/púrpuras fríos.
ENTITY_KIND_PALETTE: dict[str, str] = {
    "personaje": "#C07B53",      # terracota — calidez humana
    "lugar": "#7E9568",          # salvia — tierra y lugar
    "localizacion": "#7E9568",   # alias de lugar
    "organizacion": "#B28A3C",   # oro-oliva — institución
    "faccion": "#A65C54",        # granate-arcilla — conflicto
    "objeto": "#937083",         # ciruela apagada — reliquia
    "evento": "#C8A24C",         # miel — momento
    "concepto": "#8E8A6A",       # oliva-piedra — idea
    "contenedor": "#A89878",     # madera clara — rama
    "nota": "#9A8E72",           # piedra cálida — nota
}
_ENTITY_KIND_DEFAULT = "#9A8E72"  # piedra cálida (neutro de la propia gama)


def entity_kind_color(kind: str | None, default: str = _ENTITY_KIND_DEFAULT) -> str:
    """Color cálido del tipo de entidad (clave normalizada en minúsculas)."""
    return ENTITY_KIND_PALETTE.get(str(kind or "").lower(), default)


# Paleta cálida por tipo de relación (BETA1-UX05): única fuente para los arcos del
# grafo y el panel de detalle. Familias por significado: vínculo (salvia), conflicto
# (granate), contención/lugar (oliva), jerarquía (oro-oliva), afecto/familia
# (terracota/rosa), causalidad (ciruela apagada). NUNCA azules/púrpuras fríos.
RELATION_KIND_PALETTE: dict[str, str] = {
    "es_aliado_de": "#7E9568",
    "es_amigo_de": "#7E9568",
    "protege": "#7E9568",
    "es_enemigo_de": "#A65C54",
    "es_rival_de": "#A65C54",
    "esta_en_conflicto_con": "#A65C54",
    "traiciono": "#A65C54",
    "contradice": "#A65C54",
    "pertenece_a": "#B28A3C",
    "es_mentor_de": "#B28A3C",
    "depende_de": "#B28A3C",
    "sospecha": "#B28A3C",
    "gobierna": "#B28A3C",
    "controla": "#B28A3C",
    "contiene": "#94A06F",
    "esta_ubicado_en": "#94A06F",
    "esta_en": "#94A06F",
    "sirve_a": "#94A06F",
    "es_familiar_de": "#C07B53",
    "ama_a": "#BD7E73",
    "posee": "#C07B53",
    "busca": "#C8A24C",
    "oculta": "#8E8A6A",
    "conoce": "#8E8A6A",
    "simboliza": "#8E8A6A",
    "esta_relacionado_con": "#9A8E72",
    "deriva_de": "#8A6B7C",
    "condiciona": "#8A6B7C",
    "explica": "#8A6B7C",
    "produce_consecuencia_en": "#8A6B7C",
    "faccion": "#A65C54",
}
_RELATION_KIND_DEFAULT = "#9A8E72"  # piedra cálida (neutro de la propia gama)


def relation_kind_color(rel_type: str | None, default: str = _RELATION_KIND_DEFAULT) -> str:
    """Color cálido del tipo de relación (clave normalizada en minúsculas)."""
    return RELATION_KIND_PALETTE.get(str(rel_type or "").lower(), default)


# Tipografía: familias + jerarquía nombrada (en vez de font-size sueltos por widget).
# Serif (Georgia) para contenido editorial; sans (Segoe UI) para controles/datos.
FONT_SERIF = '"Georgia", "Iowan Old Style", "Palatino Linotype", serif'
FONT_SANS = '"Segoe UI", "Inter", "Helvetica Neue", "Arial", sans-serif'

TYPE_H1_PX = 19       # título de sección
TYPE_H2_PX = 16       # título de tarjeta/panel
TYPE_BODY_PX = 13     # cuerpo del sistema
TYPE_LABEL_PX = 12    # etiquetas/chips
TYPE_CAPTION_PX = 11  # subtítulos muted / pies

WEIGHT_BOLD = 700
WEIGHT_SEMIBOLD = 600

_TYPE_ROLES: dict[str, tuple[int, QFont.Weight]] = {
    "h1": (TYPE_H1_PX, QFont.Weight.Bold),
    "h2": (TYPE_H2_PX, QFont.Weight.Bold),
    "body": (TYPE_BODY_PX, QFont.Weight.Normal),
    "label": (TYPE_LABEL_PX, QFont.Weight.DemiBold),
    "caption": (TYPE_CAPTION_PX, QFont.Weight.Normal),
}


def relative_luminance(hex_color: str) -> float:
    """Luminancia relativa WCAG 2.x de un color #RRGGBB (0=negro, 1=blanco)."""
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """Ratio de contraste WCAG entre dos colores (1.0 = igual, 21 = blanco/negro)."""
    la, lb = relative_luminance(hex_a), relative_luminance(hex_b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def role_font(role: str = "body", *, serif: bool = True) -> QFont:
    """QFont para un rol tipográfico nombrado (h1/h2/body/label/caption).

    Para widgets que fijan fuente por código; el QSS global sigue usando el stack
    completo de familias. Rol desconocido → body."""
    size, weight = _TYPE_ROLES.get(role, _TYPE_ROLES["body"])
    font = QFont()
    font.setFamily("Georgia" if serif else "Segoe UI")
    font.setPixelSize(size)
    font.setWeight(weight)
    return font

# Movimiento: tres niveles + curvas con carácter
MOTION_FAST     = 150   # micro-feedback: hover, foco, press
MOTION_BASE     = 220   # transición estándar: aparición de contenido/paneles
MOTION_SLOW     = 360   # presencia: entradas/salidas con carácter
EASING_STD      = QEasingCurve.Type.OutCubic        # asentamiento natural
EASING_ENTER    = QEasingCurve.Type.OutQuint        # entrada con empuje y calma
EASING_EMPHASIS = QEasingCurve.Type.InOutCubic      # énfasis simétrico

# Elevación canvas-safe — sombra cálida PINTADA A MANO (QPainter), nunca
# QGraphicsDropShadowEffect (cachea el render y deja zonas en blanco; lección G08).
# nivel -> (radio_difuminado_px, desplazamiento_y_px, alpha_máximo)
ELEVATION: dict[int, tuple[int, int, int]] = {
    0: (0, 0, 0),
    1: (16, 3, 34),
    2: (26, 7, 46),
    3: (42, 13, 58),
}


def paint_soft_shadow(painter, rect, *, radius: float = RADIUS_MD, level: int = 2) -> None:
    """Pinta una sombra cálida y suave bajo *rect* (QRectF/QRect), sin efectos gráficos.

    Apta para el canvas (QPainter directo): emula el difuminado con capas de
    rectángulos redondeados de alpha decreciente. Presentation-only: falla en
    silencio para que el pulido nunca rompa el render.
    """
    try:
        blur, dy, alpha = ELEVATION.get(level, ELEVATION[2])
        if alpha <= 0 or painter is None or rect is None:
            return
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        base = QRectF(rect)
        layers = 6
        for i in range(layers, 0, -1):
            t = i / layers
            grow = blur * t
            a = int(alpha * (1.0 - t) ** 1.6)
            if a <= 0:
                continue
            painter.setBrush(QColor(SHADOW_RGB[0], SHADOW_RGB[1], SHADOW_RGB[2], a))
            r = base.adjusted(-grow, -grow + dy, grow, grow + dy)
            painter.drawRoundedRect(r, radius + grow, radius + grow)
        painter.restore()
    except Exception:  # noqa: BLE001 - el pulido nunca rompe el render
        pass


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
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {SURFACE_HI}, stop:1 {SURFACE});
    border: 1px solid {LINE};
    border-radius: {RADIUS_MD}px;
    padding: 8px 14px;
    color: {INK_SOFT};
    font-weight: 600;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {INPUT_BG}, stop:1 {SURFACE_HI});
    border-color: {GOLD_SOFT};
    color: {INK_STRONG};
}}
QPushButton:focus {{ border: 2px solid {GOLD}; padding: 7px 13px; }}
QPushButton:pressed {{ background: {WELL}; padding-top: 9px; padding-bottom: 7px; }}
QPushButton:disabled {{ background: {SURFACE}; color: {INK_MUTED}; border-color: {LINE_SOFT}; }}
QPushButton#primaryButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {GOLD}, stop:1 {GOLD_DEEP});
    border: 1px solid {GOLD_DEEP};
    border-radius: {RADIUS_MD}px;
    color: #FCF8EC;
    font-weight: 700;
    padding: 9px 16px;
}}
QPushButton#primaryButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {GOLD_DEEP}, stop:1 #5E5427);
    border-color: {GOLD_DEEP};
}}
QPushButton#primaryButton:pressed {{ background: #5E5427; }}
QPushButton#primaryButton:disabled {{ background: #E3D8B8; color: {INK_SOFT}; border: 1px solid {LINE_STRONG}; }}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    padding: 6px 8px;
    color: {INK_SOFT};
}}
QToolButton:hover {{ background: {SURFACE_HI}; border-color: {LINE}; color: {INK_STRONG}; }}
QToolButton:checked {{ background: {GOLD_TINT}; border-color: {GOLD_SOFT}; color: {INK_STRONG}; }}
QToolButton:focus {{ border-color: {GOLD}; }}
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
    border-radius: {RADIUS_MD}px;
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
    border-radius: {RADIUS_MD}px;
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
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: {RADIUS_LG}px; background: {SURFACE}; }}
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
    """Sombra cálida suave para dar elevación a una superficie ESTÁTICA.

    AVISO (G08): NO usar en widgets dinámicos, dentro de scroll areas o sobre el
    canvas — QGraphicsDropShadowEffect cachea el render y deja zonas en blanco al
    refrescar. Para esos casos usa ``paint_soft_shadow`` (pintada) o elevación por
    contraste (Card). Para realce-al-hover usa ``install_hover_lift`` (canvas-safe).
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setXOffset(x)
    effect.setYOffset(y)
    effect.setColor(QColor(SHADOW_RGB[0], SHADOW_RGB[1], SHADOW_RGB[2], alpha))
    widget.setGraphicsEffect(effect)
    return effect


class _HoverLift(QObject):
    """Filtro de eventos que REALZA una superficie al pasar el ratón, CANVAS-SAFE.

    En vez de proyectar sombra con QGraphicsDropShadowEffect (que cachea el render
    y deja zonas en blanco en widgets dinámicos; lección G08), resalta el borde por
    contraste — la elevación canon del repo. Una regla QSS sin selector aplica al
    propio widget, así que ``base + 'border: ...'`` funciona sobre cualquier
    superficie sin tocar su selector con objectName. Falla en silencio."""

    def __init__(self, widget: QWidget, *, hover_border: str = GOLD_SOFT):
        super().__init__(widget)
        self._w = widget
        self._base = widget.styleSheet() or ""
        self._hover = f"{self._base}\nborder: 1px solid {hover_border};"
        widget.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        try:
            etype = event.type()
            if etype == QEvent.Type.Enter:
                self._w.setStyleSheet(self._hover)
            elif etype == QEvent.Type.Leave:
                self._w.setStyleSheet(self._base)
        except Exception:  # noqa: BLE001 - el pulido nunca rompe la UI
            pass
        return False


def install_hover_lift(
    widget: QWidget,
    *,
    hover_border: str = GOLD_SOFT,
    **_legacy: object,
) -> _HoverLift | None:
    """Instala un realce-al-hover CANVAS-SAFE (contraste de borde) y lo devuelve.

    Sustituye al antiguo realce por sombra (QGraphicsDropShadowEffect, prohibido en
    widgets dinámicos). Acepta y descarta kwargs legados (blur/alpha/duration) para
    no romper llamadas existentes."""
    try:
        return _HoverLift(widget, hover_border=hover_border)
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
            f"border-radius: {RADIUS_LG}px; }}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(SPACE_LG, 14, SPACE_LG, 14)
        self.layout.setSpacing(SPACE_SM)
        if title:
            self.title = QLabel(title)
            self.title.setStyleSheet(
                f"font-size: {TYPE_H2_PX}px; font-weight: {WEIGHT_BOLD}; "
                f"color: {INK_STRONG}; background: transparent;"
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
        row.setSpacing(SPACE_SM)
        self.layout.addLayout(row)
        return row

    def add_flow_row(self) -> "FlowLayout":
        """Fila que envuelve sus hijos cuando no caben (badges, botones de acción).

        Evita el desbordamiento horizontal de la tarjeta en paneles estrechos.
        """
        row = FlowLayout(spacing=SPACE_SM)
        self.layout.addLayout(row)
        return row


class FlowLayout(QLayout):
    """Layout que coloca los hijos en fila y los ENVUELVE a la siguiente línea
    cuando no caben en el ancho disponible.

    Necesario en las tarjetas: con un QHBoxLayout, una fila de badges o de varios
    botones impone un ancho mínimo igual a la suma de sus hijos y se pierde hacia
    la derecha en paneles estrechos. Con FlowLayout el ancho mínimo es el del hijo
    más ancho, así que la tarjeta cabe a cualquier anchura.
    """

    def __init__(self, parent: QWidget | None = None, spacing: int = 8):
        super().__init__(parent)
        self._items: list[Any] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item):  # noqa: N802 (API Qt)
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):  # noqa: N802
        return self.minimumSize()

    def minimumSize(self):  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x, y, line_height = rect.x(), rect.y(), 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


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
            f"background: {bg}; color: {fg}; border-radius: {RADIUS_SM}px; "
            "padding: 3px 9px; font-size: 12px; font-weight: 700;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACE_XS)
        layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        # BETA1-UX07: regla dorada corta bajo el título — jerarquía editorial
        # cálida, coherente con el acento de oro del sistema.
        accent = QFrame()
        accent.setFixedSize(30, 2)
        accent.setStyleSheet(f"background: {GOLD_SOFT}; border: none; border-radius: 1px;")
        layout.addWidget(accent)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("mutedLabel")
            sub.setWordWrap(True)
            layout.addWidget(sub)


class EmptyState(Card):
    """Estado vacío que GUÍA: título + mensaje y, opcionalmente, una acción sugerida.

    Con ``action_text`` + ``on_action`` añade un botón primario centrado para que la
    pantalla/lista vacía invite a actuar ("Crea tu primera entidad") en vez de
    quedar en blanco."""

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
        *,
        action_text: str | None = None,
        on_action=None,
    ):
        super().__init__(title, message, parent, elevated=False)
        self.setStyleSheet(
            f"QFrame#card {{ background: {SURFACE}; border: 1px dashed {LINE_STRONG}; "
            f"border-radius: {RADIUS_LG}px; }}"
        )
        self.action_button: QPushButton | None = None
        if action_text and callable(on_action):
            button = QPushButton(action_text)
            button.setObjectName("primaryButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(on_action)
            row = self.add_row()
            row.addStretch(1)
            row.addWidget(button)
            row.addStretch(1)
            self.action_button = button


class PanelScaffold(QWidget):
    """Estructura común de los paneles de cajón.

    Unifica jerarquía y márgenes: cabecera (``SectionHeader`` + badge opcional),
    ``body`` (QVBoxLayout para el contenido) con márgenes-token, y una barra de
    acciones inferior opcional (secundarios a la izquierda, primario a la derecha).
    Construir paneles a partir de esto, en vez de a mano, mantiene coherentes TODOS
    los cajones. Sin graphics effect (canvas-safe)."""

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        *,
        badge: str | None = None,
        badge_tone: str = "neutral",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        self._outer.setSpacing(SPACE_MD)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(SPACE_SM)
        self.header = SectionHeader(title, subtitle)
        header_row.addWidget(self.header, 1)
        if badge:
            header_row.addWidget(
                Badge(badge, tone=badge_tone), 0, Qt.AlignmentFlag.AlignTop
            )
        self._outer.addLayout(header_row)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(SPACE_MD)
        self._outer.addLayout(self.body, 1)

        self._action_bar: QHBoxLayout | None = None

    def add_widget(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout: QLayout) -> QLayout:
        self.body.addLayout(layout)
        return layout

    def add_stretch(self) -> None:
        self.body.addStretch(1)

    def add_action_bar(self) -> QHBoxLayout:
        """Crea (una vez) la fila de acciones al pie del panel y la devuelve.

        Añade tú los botones: los secundarios primero, luego ``addStretch()`` y
        el primario, para el patrón estándar (primario a la derecha)."""
        if self._action_bar is None:
            self._action_bar = QHBoxLayout()
            self._action_bar.setContentsMargins(0, 0, 0, 0)
            self._action_bar.setSpacing(SPACE_SM)
            self._outer.addLayout(self._action_bar)
        return self._action_bar


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
        # BETA1-UX feedback: desplegar Y plegar con movimiento (antes el cierre
        # era instantáneo). Anima la altura del cuerpo con los tokens comunes.
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        body = self.body
        anim = QPropertyAnimation(body, b"maximumHeight", self)
        anim.setDuration(MOTION_BASE)
        if checked:
            body.setVisible(True)
            body.setMaximumHeight(0)
            target = max(body.sizeHint().height(), body.layout().sizeHint().height(), 1)
            anim.setStartValue(0)
            anim.setEndValue(target)
            anim.setEasingCurve(EASING_ENTER)
            anim.finished.connect(lambda: body.setMaximumHeight(16777215))
            fade_in(body, duration_ms=MOTION_BASE, start_opacity=0.4)
        else:
            anim.setStartValue(max(body.height(), 1))
            anim.setEndValue(0)
            anim.setEasingCurve(EASING_STD)
            anim.finished.connect(lambda: body.setVisible(False))
        self._anim = anim
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def fade_in(widget: QWidget, *, duration_ms: int = MOTION_BASE, start_opacity: float = 0.0):
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
        animation.setEasingCurve(EASING_STD)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    except Exception:
        pass


def fade_out(widget: QWidget, *, duration_ms: int = MOTION_BASE, on_done=None):
    """Desvanece *widget* de opaco a transparente y, al terminar, llama on_done.

    Pensado para velos/overlays PLANOS (sin hijos interactivos) — p. ej. la
    transición entre vistas. NO usar sobre widgets con menús/botones dinámicos
    (los efectos de opacidad los vacían; lección conocida). Falla en silencio."""
    try:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(1.0)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(duration_ms)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(EASING_STD)
        if on_done is not None:
            animation.finished.connect(on_done)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    except Exception:
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass


def pulse_feedback(widget: QWidget, *, duration_ms: int = MOTION_BASE):
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
        animation.setEasingCurve(EASING_STD)
        animation.finished.connect(lambda: effect.setOpacity(1.0))
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    except Exception:
        pass


class BusyIndicator(QWidget):
    """Indicador de actividad orgánico, canvas-safe.

    Un arco dorado que gira mientras una operación asíncrona está en curso. Pensado
    para puntos SIN metáfora de semilla (cálculo de vista previa, jobs IA en vuelo).
    Usa el patrón establecido (QTimer ~40fps + paintEvent), nunca QGraphicsEffect
    (que vacía widgets dinámicos; lección G08). Oculto y parado por defecto: no
    consume CPU hasta que se llama a ``start()``.
    """

    def __init__(
        self,
        *,
        diameter: int = 18,
        period_ms: int = 900,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._diameter = max(8, int(diameter))
        self._period_ms = max(120, int(period_ms))
        self._angle = 0.0  # grados
        self._running = False
        self.setFixedSize(self._diameter + 4, self._diameter + 4)
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL)  # cadencia única del design system
        self._timer.timeout.connect(self._tick)
        self.hide()

    # ── API ──────────────────────────────────────────────────────────────
    def set_period_ms(self, period_ms: int) -> None:
        """Duración de una vuelta completa (ms). El caller la deriva de
        ``animation_duration()`` para respetar la intensidad del usuario."""
        self._period_ms = max(120, int(period_ms))

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._running = False
        self._timer.stop()
        self.hide()

    def is_running(self) -> bool:
        return self._running

    # ── animación ────────────────────────────────────────────────────────
    def _tick(self) -> None:
        # Grados por tick = 360 * (intervalo / periodo). Avance constante y suave.
        self._angle = (self._angle + 360.0 * (self._timer.interval() / self._period_ms)) % 360.0
        self.update()

    def hideEvent(self, event):  # noqa: N802 (Qt signature)
        # Parar el timer al ocultar evita consumir CPU en vano.
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):  # noqa: N802 (Qt signature)
        if self._running and not self._timer.isActive():
            self._timer.start()
        super().showEvent(event)

    def paintEvent(self, _event):  # noqa: N802
        if not self._running:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        m = 2.0
        arc_rect = QRectF(m, m, rect.width() - 2 * m, rect.height() - 2 * m)
        pen = QPen(QColor(GOLD), 2.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        # Pista tenue de fondo (anillo completo) para dar cuerpo sin ruido.
        track = QPen(QColor(GOLD_SOFT), 2.0)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        track_col = QColor(GOLD_SOFT)
        track_col.setAlpha(70)
        track.setColor(track_col)
        painter.setPen(track)
        painter.drawArc(arc_rect, 0, 360 * 16)
        # Arco activo: 270° que giran. Qt mide en 1/16 de grado, sentido antihorario.
        painter.setPen(pen)
        start_angle = int(-self._angle * 16)
        painter.drawArc(arc_rect, start_angle, 270 * 16)


def make_scroll_area(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(content)
    return area


# ─────────────────────────────────────────────────────────────────────────
# Guard de rueda del ratón (BETA1-UX feedback): dentro de los cajones, la rueda
# sobre un combo/spin/slider NO debe cambiar su valor (el usuario solo quiere
# desplazar el menú). Redirige la rueda al QScrollArea ancestro y bloquea el
# cambio salvo que el control tenga el foco explícito (click).
# ─────────────────────────────────────────────────────────────────────────

_WHEEL_GUARDED_TYPES = (QComboBox, QAbstractSpinBox, QSlider)


class _WheelGuard(QObject):
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            # Buscar el QScrollArea ancestro y desplazarlo en su lugar.
            node = obj.parent()
            while node is not None and not isinstance(node, QScrollArea):
                node = node.parent()
            if isinstance(node, QScrollArea):
                bar = node.verticalScrollBar()
                try:
                    bar.setValue(bar.value() - event.angleDelta().y())
                except Exception:  # noqa: BLE001
                    pass
            return True  # consumir: el valor del control no cambia
        return False


# Filtro compartido (sin estado): un único objeto basta para todos los controles.
_WHEEL_GUARD = _WheelGuard()


def install_wheel_guard(container: QWidget) -> None:
    """Protege todos los combos/spin/slider descendientes de *container* contra
    cambios accidentales por rueda. Idempotente y tolerante a fallos."""
    try:
        for tipo in _WHEEL_GUARDED_TYPES:
            for child in container.findChildren(tipo):
                child.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # la rueda no enfoca
                child.installEventFilter(_WHEEL_GUARD)
    except Exception:  # noqa: BLE001 - el pulido nunca rompe la UI
        pass


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
