"""Tarjeta flotante de previsualización al hover (BETA2-HOVER-01).

Reutilizable por las tres vistas de lienzo (Foco, cronología, mapa): al posar el
ratón sobre una entidad / hito / rama / anillo aparece esta tarjeta con retrato +
nombre + meta + descripción breve ENTERA. No es interactiva (no intercepta el
ratón) y se posiciona CLAMPEADA dentro del viewport para no cortarse; puede
esquivar un rectángulo (p. ej. el conector del Foco) para no taparlo.

Se compone con QLabels en un layout: el ``wordWrap`` del brief da el auto-tamaño,
así "mostrar la descripción entera" no necesita medir a mano.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, QRect, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets import icons, portrait_cache
from hosts.DesktopHostPySide.widgets.design_system import (
    ENTITY_KIND_PALETTE,
    FONT_SERIF,
    GOLD_SOFT,
    INK,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    POPUP_BG,
)

_LOG = logging.getLogger(__name__)
_CARD_W = 300  # ancho fijo (el alto lo da el brief con wordWrap)
_PORTRAIT = 64


@dataclass
class HoverContent:
    """Datos de una previsualización. ``avoid_rect``/``anchor_rect`` en coords de viewport."""

    title: str = ""
    meta: str = ""
    brief: str = ""
    kind: str = "entidad"  # entidad | hito | rama | anillo
    entity_type: str = ""  # para el glifo de respaldo (hoja/rama)
    accent: str = ""  # color de acento (rama/anillo) para el bloque de respaldo
    image_path: str = ""
    image_crop: Any = None
    assets_root: Any = None
    anchor_rect: Any = None  # QRect opcional del item (si None, se usa el cursor)
    avoid_rect: Any = None  # QRect a NO tapar si es posible (conector del Foco)

    def key(self) -> tuple:
        return (self.kind, self.title, self.meta, self.brief, self.image_path)


def _rounded(pix: QPixmap, side: int, radius: float) -> QPixmap:
    out = QPixmap(side, side)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(0.0, 0.0, float(side), float(side), radius, radius)
    painter.setClipPath(path)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    scaled = pix.scaled(
        side,
        side,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return out


def _fallback_portrait(content: HoverContent, side: int) -> QPixmap:
    out = QPixmap(side, side)
    out.fill(Qt.GlobalColor.transparent)
    base = content.accent or ENTITY_KIND_PALETTE.get(str(content.entity_type), INK_SOFT)
    color = QColor(base)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    block = QColor(color)
    block.setAlphaF(0.24)
    path = QPainterPath()
    path.addRoundedRect(0.0, 0.0, float(side), float(side), 8.0, 8.0)
    painter.fillPath(path, QBrush(block))
    # Glifo rama/hoja solo cuando hay un tipo de entidad; hitos/anillos = bloque liso.
    glyph_type = content.entity_type or ("contenedor" if content.kind == "rama" else "")
    if glyph_type:
        gsize = int(side * 0.5)
        glyph = icons.entity_glyph_pixmap(glyph_type, size=gsize, color=color.name())
        painter.drawPixmap(int((side - gsize) / 2), int((side - gsize) / 2), glyph)
    painter.end()
    return out


class HoverPreviewCard(QFrame):
    """Tarjeta flotante no interactiva: retrato + nombre + meta + brief entero."""

    def __init__(self, parent: QWidget | None = None) -> None:
        # Ventana top-level e INDEPENDIENTE del viewport (el controller la crea con
        # parent=None): un hijo —incluso ventana top-level PROPIETARIA del viewport—
        # re-dispara el artefacto de backing-store raster que blanquea los ítems
        # translúcidos del QGraphicsView al mostrarla/ocultarla. Como ventana propia
        # sin padre no se compone en el viewport ni ensucia su backing-store.
        # Click-through y sin robar foco.
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        super().__init__(parent, flags)
        self.setObjectName("hoverPreviewCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedWidth(_CARD_W)
        self.setStyleSheet(
            f"QFrame#hoverPreviewCard {{ background: {POPUP_BG}; border: 1px solid {GOLD_SOFT}; "
            "border-radius: 14px; } "
            "QLabel { background: transparent; border: none; }"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(10)
        head.setContentsMargins(0, 0, 0, 0)
        self._portrait = QLabel()
        self._portrait.setFixedSize(_PORTRAIT, _PORTRAIT)
        head.addWidget(self._portrait, 0, Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel()
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"color: {INK_STRONG}; font-family: {FONT_SERIF}; font-size: 15px; font-weight: 700;"
        )
        self._meta = QLabel()
        self._meta.setWordWrap(True)
        self._meta.setStyleSheet(f"color: {INK_MUTED}; font-size: 11px;")
        text_col.addWidget(self._title)
        text_col.addWidget(self._meta)
        text_col.addStretch(1)
        head.addLayout(text_col, 1)
        outer.addLayout(head)

        self._brief = QLabel()
        self._brief.setWordWrap(True)
        self._brief.setStyleSheet(f"color: {INK}; font-family: {FONT_SERIF}; font-size: 13px;")
        outer.addWidget(self._brief)

    def set_content(self, content: HoverContent) -> None:
        self._title.setText(content.title or "Sin título")
        self._meta.setText(content.meta or "")
        self._meta.setVisible(bool(content.meta))
        self._brief.setText(content.brief or "Sin descripción breve.")
        self._portrait.setPixmap(self._render_portrait(content))
        self._resize_to_content()

    def _resize_to_content(self) -> None:
        """Ajusta el ALTO al contenido envuelto. ``adjustSize()`` no aplica
        ``heightForWidth`` a un QLabel con ``wordWrap`` a ancho fijo (subestima el
        alto y el brief se corta); usamos ``heightForWidth`` explícito."""
        self.setFixedWidth(_CARD_W)
        layout = self.layout()
        if layout is not None:
            layout.activate()
        height = self.heightForWidth(_CARD_W)
        if height <= 0:
            height = self.sizeHint().height()
        self.resize(_CARD_W, height)

    def _render_portrait(self, content: HoverContent) -> QPixmap:
        pix = None
        if content.image_path:
            path = portrait_cache.resolve_stored(content.assets_root, content.image_path)
            pix = portrait_cache.portrait_pixmap(path, content.image_crop, _PORTRAIT)
        if pix is not None:
            return _rounded(pix, _PORTRAIT, 8.0)
        return _fallback_portrait(content, _PORTRAIT)

    def place(self, anchor: QRect, bounds: QRect, avoid: QRect | None = None) -> None:
        """Coloca la tarjeta al lado del ``anchor``, entera dentro de ``bounds``
        (la geometría disponible de la pantalla, coords globales) y, si puede, sin
        solapar ``avoid``. El alto ya lo fijó ``set_content``; no lo recalcula."""
        w, h = self.width(), self.height()
        gap = 12
        candidates = [
            (anchor.right() + gap, anchor.top()),  # derecha
            (anchor.left() - gap - w, anchor.top()),  # izquierda
            (anchor.left(), anchor.bottom() + gap),  # abajo
            (anchor.left(), anchor.top() - gap - h),  # arriba
        ]
        best = None
        best_score = None
        for x, y in candidates:
            cx = max(bounds.left(), min(int(x), bounds.right() - w))
            cy = max(bounds.top(), min(int(y), bounds.bottom() - h))
            rect = QRect(cx, cy, w, h)
            moved = abs(cx - int(x)) + abs(cy - int(y))
            overlap = 0
            if avoid is not None:
                inter = rect.intersected(avoid)
                if inter.isValid():
                    overlap = inter.width() * inter.height()
            score = overlap * 1000 + moved  # esquivar el conector manda; luego, menos clamp
            if best_score is None or score < best_score:
                best_score = score
                best = rect
        self.move(best.topLeft())

    def show_for(
        self, anchor: QRect, bounds: QRect, content: HoverContent, avoid: QRect | None = None
    ) -> None:
        self.set_content(content)
        self.place(anchor, bounds, avoid=avoid)
        self.show()
        self.raise_()


class HoverPreviewController(QObject):
    """Gestiona el hover de una vista: al posar el ratón (tras un breve retardo)
    resuelve el contenido bajo el cursor y muestra la ``HoverPreviewCard``.

    ``resolver(view_pos: QPoint) -> HoverContent | None``. La tarjeta se ancla al
    ``anchor_rect`` del contenido (o a un rect alrededor del cursor) y esquiva su
    ``avoid_rect`` si lo trae.
    """

    def __init__(
        self,
        view: Any,
        resolver: Callable[[Any], HoverContent | None],
        *,
        delay_ms: int = 250,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent or view)
        self._view = view
        self._resolver = resolver
        # BETA2-HOVER (fix parpadeo): la tarjeta NO se parenta al viewport. Aunque
        # sea ventana top-level, un hijo-PROPIETARIO del viewport re-dispara el
        # artefacto de backing-store raster que blanquea los ítems translúcidos al
        # mostrarla/ocultarla (chips fantasma, pills de «Año N», bandas de era) — y
        # un repintado síncrono NO lo cura (solo reconstruir la escena, que el hover
        # no hace). Sin padre = ventana independiente que jamás ensucia el
        # backing-store del viewport. Se ata al ciclo de vida de la vista con deleteLater.
        self._card = HoverPreviewCard(None)
        self._card.hide()
        try:
            view.destroyed.connect(self._card.deleteLater)
        except (RuntimeError, AttributeError):
            pass
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(delay_ms)
        self._timer.timeout.connect(self._on_timeout)
        self._pending_pos = None
        self._current_key: tuple | None = None
        view.viewport().setMouseTracking(True)
        view.viewport().installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 (API Qt)
        et = event.type()
        if et == QEvent.Type.MouseMove:
            # Solo hover pasivo: si hay un botón pulsado (pan/arrastre) no se muestra.
            buttons = event.buttons() if hasattr(event, "buttons") else Qt.MouseButton.NoButton
            if buttons != Qt.MouseButton.NoButton:
                self._hide()
                return False
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self._pending_pos = pos
            self._timer.start()
        elif et in (
            QEvent.Type.Leave,
            QEvent.Type.Wheel,
            QEvent.Type.MouseButtonPress,
        ):
            self._hide()
        return False

    def _on_timeout(self) -> None:
        pos = self._pending_pos
        if pos is None:
            self._hide()
            return
        try:
            content = self._resolver(pos)
        except Exception:
            # No tragar mudo: un fallo del resolver (p. ej. un hit-test que
            # espera QPointF y recibe QPoint) escondía la tarjeta sin rastro.
            _LOG.exception("hover resolver falló")
            content = None
        if content is None:
            self._hide()
            return
        # La tarjeta es una ventana top-level → posicionamos en coords GLOBALES y
        # clampeamos a la pantalla (no al rect del viewport).
        anchor_local = content.anchor_rect or QRect(pos.x() - 10, pos.y() - 10, 20, 20)
        anchor = self._to_global(anchor_local)
        avoid = self._to_global(content.avoid_rect) if content.avoid_rect is not None else None
        bounds = self._screen_bounds(anchor)
        self._card.show_for(anchor, bounds, content, avoid=avoid)
        self._current_key = content.key()

    def _to_global(self, rect: QRect) -> QRect:
        gtl = self._view.viewport().mapToGlobal(rect.topLeft())
        return QRect(gtl.x(), gtl.y(), rect.width(), rect.height())

    @staticmethod
    def _screen_bounds(anchor: QRect) -> QRect:
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        if screen is not None:
            return screen.availableGeometry()
        return QRect(0, 0, 1920, 1080)

    def _hide(self) -> None:
        self._timer.stop()
        self._card.hide()
        self._current_key = None

    def hide(self) -> None:
        self._hide()

    def card(self) -> HoverPreviewCard:
        return self._card
