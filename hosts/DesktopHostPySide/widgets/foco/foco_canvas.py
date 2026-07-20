"""Lienzo del Modo Foco: navegación por anillos en torno al centro.

Layout DETERMINISTA por bandas (sin física libre) organizado por POSICIÓN DE
ANILLO (BETA2-FOCO-25/28): relacionadas en anillos SUPERIORES en la BANDA
SUPERIOR (Raíces, sub-bandas apiladas — la más superior arriba del todo), en
anillos INFERIORES en la BANDA INFERIOR (Brotes, en espejo), del MISMO anillo en
la BANDA DERECHA (Entorno) junto con las compañeras de rama. Los ítems de banda
son chips compactos (glifo rama/hoja + nombre) que se despliegan al pasar el
ratón (descripción breve + conector con el centro). La rama contenedora envuelve
el centro como marco; y una RULETA de dos tarjetas plegadas tenues flanquea el
centro (la anterior a la izquierda, la siguiente a la derecha) para rotar por el
anillo con ←/→. El centro queda reservado para la tarjeta/formulario (widget real
que FocoView superpone). Pintura a mano — PROHIBIDO QGraphicsEffect en dinámicos.

Interacción (spec BETA2-FOCO-25):
- click simple o doble en satélite ⇒ centrar (``satelliteActivated``);
- Ctrl+click ⇒ multiselección resaltada (``selectionChanged``), el centro
  sigue siendo uno;
- ← / → ⇒ rotar cíclicamente por el anillo actual (anterior / siguiente);
- Shift+↑ / Shift+↓ ⇒ saltar al anillo superior / inferior (relacionada más
  cercana, o entidad cualquiera del anillo adyacente);
- centran directamente, sin Enter; sin destino ⇒ no-op.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsView,
)

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.canvas_atmosphere import CanvasAtmosphere
from hosts.DesktopHostPySide.widgets.design_system import (
    ENTITY_KIND_PALETTE,
    GOLD,
    GOLD_SOFT,
    INK,
    INK_MUTED,
    INK_SOFT,
    LINE_SOFT,
    SAGE,
    SURFACE_HI,
    canvas_vignette_brush,
)

_NODE_RADIUS = 24.0
_LABEL_WIDTH = 128.0
_ZONE_KEYS = ("raices", "entorno", "brotes")
# FOCO-30: chip de banda = tarjeta con RETRATO + nombre (colapsado); al desplegar
# crece a lo largo del banner (ancho arriba/abajo, alto a la derecha).
_BAND_CHIP_W = 76.0
_BAND_CHIP_H = 88.0
_BAND_PORTRAIT = 56.0  # retrato cuadrado dentro del chip colapsado
# FOCO-30: tarjeta plegada de la ruleta (retrato cuadrado 1:1 del crop del usuario).
_ROULETTE_CARD_W = 112.0
_ROULETTE_CARD_H = 150.0
# FOCO-30: miniaturas de hermanos en el borde del marco contenedor.
_FRAME_THUMB_SIZE = 30.0
_FRAME_THUMB_MAX = 7

# FOCO-25: cabeceras que explican qué contiene cada zona del lienzo por anillos.
_ZONE_CAPTIONS = {
    "raices": "RAÍCES · anillos superiores",
    "brotes": "BROTES · anillos inferiores",
    "entorno": "ENTORNO",
    "rotacion": "ROTAR ANILLO  ← →",
}


class FocoContainerFrame(QGraphicsObject):
    """FOCO-22: la rama contenedora ENVUELVE al centro como marco clicable.

    Marco redondeado alrededor del hueco central con el nombre de la rama en
    el borde superior; si hay más ancestras, breadcrumb «Abuela › Madre» a la
    derecha. Click ⇒ centrar la contenedora inmediata.
    """

    def __init__(self, container_id: str, name: str, breadcrumb: str = "") -> None:
        super().__init__()
        self.container_id = container_id
        self.display_name = name
        self.breadcrumb = breadcrumb
        self._rect = QRectF(0, 0, 10, 10)
        # FOCO-30: hermanos (misma rama) como miniaturas en el borde del marco.
        self._member_thumbs: list[dict] = []
        self._thumb_rects: list[tuple[QRectF, str]] = []
        # UI2-21: pulso savia cuando esta rama se está regando.
        self._watering_pulse = False
        self._watering_phase = 0.0
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(-2)  # detrás de satélites y conectores
        self.setToolTip(f"Rama contenedora: {name} — click para centrarla")

    def set_frame_rect(self, rect: QRectF) -> None:
        self.prepareGeometryChange()
        self._rect = QRectF(rect)
        self._recompute_thumb_rects()
        self.update()

    def set_member_thumbs(self, members: list[dict]) -> None:
        """FOCO-30: miniaturas de los hermanos (misma rama) en el borde del marco."""
        self.prepareGeometryChange()
        self._member_thumbs = [m for m in (members or []) if m.get("entity_id")]
        self._recompute_thumb_rects()
        self.update()

    def _recompute_thumb_rects(self) -> None:
        self._thumb_rects = []
        members = self._member_thumbs
        if not members:
            return
        size = _FRAME_THUMB_SIZE
        gap = 6.0
        shown = members[: _FRAME_THUMB_MAX - 1] if len(members) > _FRAME_THUMB_MAX else members
        slots = len(shown) + (1 if len(members) > _FRAME_THUMB_MAX else 0)
        total = slots * size + (slots - 1) * gap
        x = self._rect.center().x() - total / 2.0
        y = self._rect.bottom() + 6.0
        for member in shown:
            self._thumb_rects.append((QRectF(x, y, size, size), str(member["entity_id"])))
            x += size + gap
        if len(members) > _FRAME_THUMB_MAX:
            # Chip «+K» que centra la rama para ver el resto en su estantería.
            self._thumb_rects.append((QRectF(x, y, size, size), "__more__"))

    def _thumb_pixmap(self, member: dict, side: float):
        image_path = str(member.get("image_path", "") or "")
        if not image_path:
            return None
        from hosts.DesktopHostPySide.widgets import portrait_cache

        scene = self.scene()
        assets_root = getattr(scene, "_portrait_assets_root", None) if scene is not None else None
        resolved = portrait_cache.resolve_stored(assets_root, image_path)
        return portrait_cache.portrait_pixmap(resolved, member.get("image_crop"), int(side))

    def set_watering_pulse(self, on: bool) -> None:
        if self._watering_pulse == bool(on):
            return
        self._watering_pulse = bool(on)
        self.update()

    def set_watering_phase(self, phase: float) -> None:
        self._watering_phase = float(phase)
        if self._watering_pulse:
            self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802 (API Qt)
        # UI2-21: margen extra para el anillo savia pulsante; FOCO-30: franja de
        # miniaturas de hermanos bajo el borde inferior.
        bottom_extra = (_FRAME_THUMB_SIZE + 14.0) if self._member_thumbs else 10.0
        return self._rect.adjusted(-10, -16, 10, bottom_extra)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # UI2-21: anillo savia — esta rama se está regando AHORA (mismo lenguaje
        # que el Mapa). Se pinta por FUERA del marco para que se vea latir.
        if self._watering_pulse:
            wave = abs(math.sin(self._watering_phase))
            sap = QColor(SAGE)
            sap.setAlpha(int(120 + 120 * wave))
            grow = 3.0 + 5.0 * wave
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(sap, 3.0))
            painter.drawRoundedRect(self._rect.adjusted(-grow, -grow, grow, grow), 18.0, 18.0)
        pen = QPen(QColor(GOLD_SOFT))
        pen.setWidthF(1.6)
        painter.setPen(pen)
        fill = QColor(SURFACE_HI)
        fill.setAlphaF(0.35)
        painter.setBrush(fill)
        painter.drawRoundedRect(self._rect, 18.0, 18.0)
        # Pestaña con el nombre en el borde superior.
        font = QFont()
        font.setPointSizeF(8.5)
        font.setBold(True)
        painter.setFont(font)
        label = f"⌂ {self.display_name}"
        metrics = painter.fontMetrics()
        tab_width = metrics.horizontalAdvance(label) + 22
        tab = QRectF(self._rect.x() + 18, self._rect.y() - 11, tab_width, 20)
        painter.setBrush(QColor(SURFACE_HI))
        painter.drawRoundedRect(tab, 9.0, 9.0)
        painter.setPen(QPen(QColor(INK_SOFT)))
        painter.drawText(tab, Qt.AlignmentFlag.AlignCenter, label)
        if self.breadcrumb:
            crumb_font = QFont()
            crumb_font.setPointSizeF(7.5)
            painter.setFont(crumb_font)
            painter.setPen(QPen(QColor(INK_MUTED)))
            crumb_rect = QRectF(
                tab.right() + 8, self._rect.y() - 11, self._rect.width() - tab_width - 44, 20
            )
            # FOCO-26: el texto llega COMPLETO del llamador («dentro de X» o
            # «también en Y» para co-madres) — se pinta tal cual.
            painter.drawText(
                crumb_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.breadcrumb,
            )
        # FOCO-30: miniaturas de los hermanos (misma rama) en el borde inferior.
        self._paint_member_thumbs(painter)

    def _paint_member_thumbs(self, painter: QPainter) -> None:
        if not self._thumb_rects:
            return
        by_id = {str(m["entity_id"]): m for m in self._member_thumbs}
        more = len(self._member_thumbs) - (len(self._thumb_rects) - 1)
        for rect, member_id in self._thumb_rects:
            if member_id == "__more__":
                painter.setPen(QPen(QColor(GOLD_SOFT), 1.2))
                painter.setBrush(QColor(SURFACE_HI))
                painter.drawRoundedRect(rect, 7.0, 7.0)
                mf = QFont()
                mf.setPointSizeF(8.0)
                mf.setBold(True)
                painter.setFont(mf)
                painter.setPen(QPen(QColor(INK_SOFT)))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"+{max(1, more)}")
                continue
            member = by_id.get(member_id, {})
            color = QColor(ENTITY_KIND_PALETTE.get(str(member.get("entity_type", "")), INK_SOFT))
            portrait = self._thumb_pixmap(member, rect.width())
            if portrait is not None:
                clip = QPainterPath()
                clip.addRoundedRect(rect, 7.0, 7.0)
                painter.save()
                painter.setClipPath(clip)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.drawPixmap(rect, portrait, QRectF(portrait.rect()))
                painter.restore()
                painter.setPen(QPen(QColor(255, 255, 255, 220), 1.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect, 7.0, 7.0)
            else:
                block = QColor(color)
                block.setAlphaF(0.28)
                painter.setBrush(block)
                painter.setPen(QPen(QColor(GOLD_SOFT), 1.0))
                painter.drawRoundedRect(rect, 7.0, 7.0)
                glyph = icons.entity_glyph_pixmap(
                    member.get("entity_type", ""), size=16, color=color.name()
                )
                painter.drawPixmap(
                    QRectF(rect.center().x() - 8, rect.center().y() - 8, 16, 16),
                    glyph,
                    QRectF(glyph.rect()),
                )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        scene = self.scene()
        views = scene.views() if scene is not None else []
        target = self.container_id
        # FOCO-30: click en una miniatura de hermano ⇒ centrar ese hermano; «+K»
        # ⇒ centrar la rama (para ver el resto en su estantería).
        for rect, member_id in self._thumb_rects:
            if rect.contains(event.pos()):
                target = self.container_id if member_id == "__more__" else member_id
                break
        if views and isinstance(views[0], FocoCanvas):
            views[0].satelliteActivated.emit(target)
        event.accept()


class FocoSatelliteItem(QGraphicsObject):
    """Vecina en segundo plano: círculo por tipo + nombre. Fantasma = translúcido."""

    def __init__(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        *,
        is_ghost: bool = False,
        zone: str = "entorno",
        reason: str = "",
        image_path: str = "",
        image_crop: tuple | None = None,
    ) -> None:
        super().__init__()
        self.entity_id = entity_id
        self.display_name = name
        self.entity_type = entity_type
        self.is_ghost = is_ghost
        self.zone = zone
        self.reason = reason
        # BETA2-IMG: retrato de la vecina (ruta + encuadre); los fantasmas
        # conservan su render translúcido sin foto.
        self.image_path = str(image_path or "")
        self.image_crop = image_crop
        self.highlighted = False  # multiselección Ctrl
        # UI2-21: pulso savia cuando esta vecina (hoja o rama) se está regando.
        self._watering_pulse = False
        self._watering_phase = 0.0
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, False)

    def set_watering_pulse(self, on: bool) -> None:
        if self._watering_pulse == bool(on):
            return
        self._watering_pulse = bool(on)
        self.update()

    def set_watering_phase(self, phase: float) -> None:
        self._watering_phase = float(phase)
        if self._watering_pulse:
            self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802 (API Qt)
        # UI2-21: margen superior extra para el anillo savia pulsante.
        return QRectF(-_LABEL_WIDTH / 2, -_NODE_RADIUS - 12, _LABEL_WIDTH, _NODE_RADIUS * 2 + 36)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802
        color = QColor(ENTITY_KIND_PALETTE.get(str(self.entity_type), INK_SOFT))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(0.42 if self.is_ghost else 1.0)
        if self.highlighted:
            halo = QPen(QColor(GOLD))
            halo.setWidthF(3.0)
            painter.setPen(halo)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), _NODE_RADIUS + 5, _NODE_RADIUS + 5)
        if self.is_ghost:
            pen = QPen(QColor(INK_MUTED))
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidthF(1.4)
        else:
            pen = QPen(color.darker(125))
            pen.setWidthF(1.6)
        painter.setPen(pen)
        fill = QColor(color)
        fill.setAlphaF(0.18 if self.is_ghost else 0.30)
        painter.setBrush(fill)
        painter.drawEllipse(QPointF(0, 0), _NODE_RADIUS, _NODE_RADIUS)
        # BETA2-IMG: retrato en miniatura recortado por el círculo, con aro
        # blanco sutil. Los fantasmas quedan sin foto (translúcidos, como hoy).
        if self.image_path and not self.is_ghost:
            portrait = self._portrait_pixmap()
            if portrait is not None:
                clip = QPainterPath()
                clip.addEllipse(QPointF(0, 0), _NODE_RADIUS, _NODE_RADIUS)
                painter.save()
                painter.setClipPath(clip)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                target = QRectF(-_NODE_RADIUS, -_NODE_RADIUS, _NODE_RADIUS * 2, _NODE_RADIUS * 2)
                painter.drawPixmap(target, portrait, QRectF(portrait.rect()))
                painter.restore()
                ring = QPen(QColor(255, 255, 255, 235))
                ring.setWidthF(1.2)
                painter.setPen(ring)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(0, 0), _NODE_RADIUS, _NODE_RADIUS)
        painter.setOpacity(0.62 if self.is_ghost else 1.0)
        painter.setPen(QPen(QColor(INK)))
        font = QFont()
        font.setPointSizeF(8.5)
        painter.setFont(font)
        label = self.display_name if len(self.display_name) <= 22 else self.display_name[:21] + "…"
        rect = QRectF(-_LABEL_WIDTH / 2, _NODE_RADIUS + 3, _LABEL_WIDTH, 22)
        painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)
        # UI2-21: anillo savia — esta entidad se está regando AHORA (mismo
        # lenguaje que el Mapa); notorio también para satélites no centrados.
        if self._watering_pulse:
            wave = abs(math.sin(self._watering_phase))
            sap = QColor(SAGE)
            sap.setAlpha(int(120 + 120 * wave))
            grow = 5.0 + 3.0 * wave
            painter.setOpacity(1.0)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(sap, 3.0))
            painter.drawEllipse(QPointF(0, 0), _NODE_RADIUS + grow, _NODE_RADIUS + grow)

    def _portrait_pixmap(self):
        """BETA2-IMG: pixmap cacheado del retrato (la raíz vive en la escena)."""
        from hosts.DesktopHostPySide.widgets import portrait_cache

        scene = self.scene()
        assets_root = getattr(scene, "_portrait_assets_root", None) if scene is not None else None
        resolved = portrait_cache.resolve_stored(assets_root, self.image_path)
        return portrait_cache.portrait_pixmap(resolved, self.image_crop, _NODE_RADIUS * 2)

    def _canvas(self) -> "FocoCanvas | None":
        scene = self.scene()
        views = scene.views() if scene is not None else []
        return views[0] if views and isinstance(views[0], FocoCanvas) else None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        canvas = self._canvas()
        if canvas is not None:
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            canvas._on_item_clicked(self.entity_id, ctrl=ctrl)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        # Doble click = mismo efecto que click en Foco (spec).
        canvas = self._canvas()
        if canvas is not None:
            canvas._on_item_clicked(self.entity_id, ctrl=False)
        event.accept()


class FocoBandItem(QGraphicsObject):
    """FOCO-30: relacionada en una banda de borde — tarjeta con RETRATO + nombre y
    mini-glifo rama/hoja en la esquina. Al pasar el ratón se DESPLIEGA (retrato +
    nombre + tipo + descripción completa + anillo) creciendo A LO LARGO del banner
    (ancho arriba/abajo, alto a la derecha), empujando a las demás y SIN tapar el
    conector (crece alejándose del centro). Click ⇒ centrar.
    """

    def __init__(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        *,
        is_ghost: bool = False,
        zone: str = "entorno",
        brief: str = "",
        link_label: str = "",
        image_path: str = "",
        image_crop: tuple | None = None,
        ring_name: str = "",
        nature: str = "",
        band: str = "top",
    ) -> None:
        super().__init__()
        self.entity_id = entity_id
        self.display_name = name
        self.entity_type = entity_type
        self.is_ghost = is_ghost
        self.zone = zone
        self.brief = str(brief or "")
        self.link_label = str(link_label or "")
        self.image_path = str(image_path or "")
        self.image_crop = image_crop
        self.ring_name = str(ring_name or "")
        self.nature = str(nature or "")
        self.band = band  # "top" | "bottom" | "right"
        self.band_index = 0
        self.highlighted = False  # multiselección Ctrl
        # UI2-21: pulso savia cuando esta vecina se está regando (misma API).
        self._watering_pulse = False
        self._watering_phase = 0.0
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptHoverEvents(True)  # FOCO-30: hover ⇒ desplegar + conector
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, False)

    def set_watering_pulse(self, on: bool) -> None:
        if self._watering_pulse == bool(on):
            return
        self._watering_pulse = bool(on)
        self.update()

    def set_watering_phase(self, phase: float) -> None:
        self._watering_phase = float(phase)
        if self._watering_pulse:
            self.update()

    def _chip_rect(self) -> QRectF:
        """Rect del chip (tamaño FIJO). BETA2-HOVER-02: el chip ya no se expande al
        hover; el detalle (retrato + descripción entera) se muestra en la tarjeta
        flotante ``HoverPreviewCard``, que se posiciona clampeada al viewport y sin
        tapar el conector."""
        return QRectF(-_BAND_CHIP_W / 2, -_BAND_CHIP_H / 2, _BAND_CHIP_W, _BAND_CHIP_H)

    def boundingRect(self) -> QRectF:  # noqa: N802 (API Qt)
        return self._chip_rect().adjusted(-8, -8, 8, 8)

    def _portrait_pixmap(self, side: float):
        """BETA2-IMG: retrato cuadrado cacheado (o None si no hay foto / fantasma)."""
        if not self.image_path or self.is_ghost:
            return None
        from hosts.DesktopHostPySide.widgets import portrait_cache

        scene = self.scene()
        assets_root = getattr(scene, "_portrait_assets_root", None) if scene is not None else None
        resolved = portrait_cache.resolve_stored(assets_root, self.image_path)
        return portrait_cache.portrait_pixmap(resolved, self.image_crop, int(side))

    def _type_label(self) -> str:
        text = str(self.entity_type or "").replace("_", " ").strip()
        return text[:1].upper() + text[1:] if text else ""

    def _draw_portrait(self, painter: QPainter, rect: QRectF) -> None:
        """Retrato cuadrado recortado (o bloque de color + glifo si no hay foto) con
        mini-glifo rama/hoja en la esquina (mismo para rama y hoja: solo indica especie)."""
        color = QColor(ENTITY_KIND_PALETTE.get(str(self.entity_type), INK_SOFT))
        portrait = self._portrait_pixmap(rect.width())
        if portrait is not None:
            clip = QPainterPath()
            clip.addRoundedRect(rect, 7.0, 7.0)
            painter.save()
            painter.setClipPath(clip)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(rect, portrait, QRectF(portrait.rect()))
            painter.restore()
        else:
            block = QColor(color)
            block.setAlphaF(0.20 if self.is_ghost else 0.24)
            painter.setBrush(block)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 7.0, 7.0)
            gsize = max(16.0, rect.width() * 0.5)
            g = icons.entity_glyph_pixmap(self.entity_type, size=int(gsize), color=color.name())
            painter.drawPixmap(
                QRectF(rect.center().x() - gsize / 2, rect.center().y() - gsize / 2, gsize, gsize),
                g,
                QRectF(g.rect()),
            )
        # Mini-glifo rama/hoja en la esquina superior izquierda del retrato.
        badge = icons.entity_glyph_pixmap(self.entity_type, size=12, color=INK_SOFT)
        painter.drawPixmap(
            QRectF(rect.left() + 2, rect.top() + 2, 12, 12), badge, QRectF(badge.rect())
        )

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(0.55 if self.is_ghost else 1.0)
        rect = self._chip_rect()
        fill = QColor(SURFACE_HI)
        fill.setAlphaF(0.85)
        painter.setBrush(fill)
        if self.highlighted:
            painter.setPen(QPen(QColor(GOLD), 2.0))
        elif self.is_ghost:
            dash = QPen(QColor(INK_MUTED))
            dash.setStyle(Qt.PenStyle.DashLine)
            dash.setWidthF(1.2)
            painter.setPen(dash)
        else:
            painter.setPen(QPen(QColor(LINE_SOFT), 1.0))
        painter.drawRoundedRect(rect, 10.0, 10.0)
        painter.save()
        painter.setClipRect(rect)  # nada se sale del chip
        self._paint_collapsed(painter, rect)
        painter.restore()
        # UI2-21: anillo savia — riego en curso, notorio también para no centrados.
        if self._watering_pulse:
            wave = abs(math.sin(self._watering_phase))
            sap = QColor(SAGE)
            sap.setAlpha(int(120 + 120 * wave))
            grow = 3.0 + 4.0 * wave
            painter.setOpacity(1.0)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(sap, 2.5))
            painter.drawRoundedRect(rect.adjusted(-grow, -grow, grow, grow), 12.0, 12.0)

    def _paint_collapsed(self, painter: QPainter, rect: QRectF) -> None:
        pr = QRectF(-_BAND_PORTRAIT / 2, rect.top() + 6, _BAND_PORTRAIT, _BAND_PORTRAIT)
        self._draw_portrait(painter, pr)
        painter.setOpacity(0.75 if self.is_ghost else 1.0)
        painter.setPen(QPen(QColor(INK)))
        font = QFont()
        font.setPointSizeF(8.0)
        painter.setFont(font)
        name_rect = QRectF(
            rect.left() + 4, pr.bottom() + 2, rect.width() - 8, rect.bottom() - pr.bottom() - 4
        )
        elided = painter.fontMetrics().elidedText(
            self.display_name, Qt.TextElideMode.ElideRight, int(name_rect.width())
        )
        painter.drawText(
            name_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, elided
        )

    def _canvas(self) -> "FocoCanvas | None":
        scene = self.scene()
        views = scene.views() if scene is not None else []
        return views[0] if views and isinstance(views[0], FocoCanvas) else None

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        # BETA2-HOVER-02: el chip ya no se expande; el hover solo dibuja el conector
        # "Está relacionado con". El detalle va en la tarjeta flotante (controller).
        self.setZValue(6.0)
        canvas = self._canvas()
        if canvas is not None:
            canvas._show_band_connector(self.entity_id)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self.setZValue(0.0)
        canvas = self._canvas()
        if canvas is not None:
            canvas._hide_band_connector()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        canvas = self._canvas()
        if canvas is not None:
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            canvas._on_item_clicked(self.entity_id, ctrl=ctrl)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        canvas = self._canvas()
        if canvas is not None:
            canvas._on_item_clicked(self.entity_id, ctrl=False)
        event.accept()


class FocoRouletteCard(QGraphicsObject):
    """FOCO-28: tarjeta PLEGADA tenue de un vecino de rotación del anillo (la
    anterior a la izquierda, la siguiente a la derecha). Imagen + nombre +
    descripción breve a baja opacidad; click ⇒ centrarla (igual que ←/→).
    """

    def __init__(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        *,
        brief: str = "",
        image_path: str = "",
        image_crop: tuple | None = None,
        direction_label: str = "",
    ) -> None:
        super().__init__()
        self.entity_id = entity_id
        self.display_name = name
        self.entity_type = entity_type
        self.brief = str(brief or "")
        self.image_path = str(image_path or "")
        self.image_crop = image_crop
        self.direction_label = str(direction_label or "")
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setOpacity(0.62)  # FOCO-28: tenue, en segundo plano
        tip = f"{self.direction_label} · {name}".strip(" ·")
        self.setToolTip(tip)

    def boundingRect(self) -> QRectF:  # noqa: N802 (API Qt)
        w = _ROULETTE_CARD_W
        h = _ROULETTE_CARD_H
        return QRectF(-w / 2, -h / 2 - 16, w, h + 20)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = _ROULETTE_CARD_W
        h = _ROULETTE_CARD_H
        card = QRectF(-w / 2, -h / 2, w, h)
        painter.setBrush(QColor(SURFACE_HI))
        painter.setPen(QPen(QColor(GOLD_SOFT), 1.2))
        painter.drawRoundedRect(card, 12.0, 12.0)
        # Etiqueta de dirección (← anterior / siguiente →) sobre la tarjeta (fuera del clip).
        if self.direction_label:
            dir_font = QFont()
            dir_font.setPointSizeF(7.0)
            dir_font.setBold(True)
            painter.setFont(dir_font)
            painter.setPen(QPen(QColor(INK_MUTED)))
            painter.drawText(
                QRectF(-w / 2, -h / 2 - 15, w, 13),
                Qt.AlignmentFlag.AlignCenter,
                self.direction_label,
            )
        painter.save()
        painter.setClipRect(card)  # FOCO-30: nada (ni el brief) se sale de la tarjeta
        # Retrato CUADRADO (el crop del usuario se ve 1:1, sin distorsión): el pixmap
        # de portrait_cache ya es cuadrado, así que un destino cuadrado no lo estira.
        side = w - 16
        img_rect = QRectF(-side / 2, -h / 2 + 8, side, side)
        color = QColor(ENTITY_KIND_PALETTE.get(str(self.entity_type), INK_SOFT))
        portrait = self._portrait_pixmap(side)
        if portrait is not None:
            clip = QPainterPath()
            clip.addRoundedRect(img_rect, 8.0, 8.0)
            painter.save()
            painter.setClipPath(clip)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(img_rect, portrait, QRectF(portrait.rect()))
            painter.restore()
        else:
            block = QColor(color)
            block.setAlphaF(0.22)
            painter.setBrush(block)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(img_rect, 8.0, 8.0)
            glyph = icons.entity_glyph_pixmap(self.entity_type, size=30, color=color.name())
            painter.drawPixmap(
                QRectF(img_rect.center().x() - 15, img_rect.center().y() - 15, 30, 30),
                glyph,
                QRectF(glyph.rect()),
            )
        # Insignia rama/hoja en la esquina superior izquierda.
        badge = icons.entity_glyph_pixmap(self.entity_type, size=13, color=INK_SOFT)
        painter.drawPixmap(QRectF(-w / 2 + 7, -h / 2 + 7, 13, 13), badge, QRectF(badge.rect()))
        # Nombre.
        painter.setPen(QPen(QColor(INK)))
        name_font = QFont()
        name_font.setPointSizeF(8.5)
        name_font.setBold(True)
        painter.setFont(name_font)
        name_rect = QRectF(-w / 2 + 8, img_rect.bottom() + 3, w - 16, 15)
        elided = painter.fontMetrics().elidedText(
            self.display_name, Qt.TextElideMode.ElideRight, int(name_rect.width())
        )
        painter.drawText(
            name_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, elided
        )
        # Descripción breve (elidida por líneas, clip garantiza que no desborde).
        if self.brief:
            brief_font = QFont()
            brief_font.setPointSizeF(7.0)
            painter.setFont(brief_font)
            painter.setPen(QPen(QColor(INK_MUTED)))
            brief_rect = QRectF(-w / 2 + 8, name_rect.bottom() + 1, w - 16, h / 2 - 8)
            flags = (
                int(Qt.TextFlag.TextWordWrap)
                | int(Qt.AlignmentFlag.AlignHCenter)
                | int(Qt.AlignmentFlag.AlignTop)
            )
            painter.drawText(brief_rect, flags, self.brief)
        painter.restore()

    def _portrait_pixmap(self, side: float):
        if not self.image_path:
            return None
        from hosts.DesktopHostPySide.widgets import portrait_cache

        scene = self.scene()
        assets_root = getattr(scene, "_portrait_assets_root", None) if scene is not None else None
        resolved = portrait_cache.resolve_stored(assets_root, self.image_path)
        return portrait_cache.portrait_pixmap(resolved, self.image_crop, int(side))

    def _canvas(self) -> "FocoCanvas | None":
        scene = self.scene()
        views = scene.views() if scene is not None else []
        return views[0] if views and isinstance(views[0], FocoCanvas) else None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        canvas = self._canvas()
        if canvas is not None:
            canvas.satelliteActivated.emit(self.entity_id)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.mousePressEvent(event)


class FocoSeedItem(QGraphicsObject):
    """Semilla IA germinando en su zona (FOCO-13).

    Visual PROPIO — distinta del satélite (sólido) y del fantasma (translúcido
    discontinuo): brote con acento dorado y anillo de germinación punteado.
    Click ⇒ abre la revisión (aceptar/rechazar por el flujo humano existente).
    """

    is_seed = True

    def __init__(self, candidate_id: str, title: str, zone: str) -> None:
        super().__init__()
        self.candidate_id = candidate_id
        self.title = title
        self.zone = zone
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Semilla IA: {title} — click para revisar")

    def boundingRect(self) -> QRectF:  # noqa: N802 (API Qt)
        return QRectF(-_LABEL_WIDTH / 2, -22, _LABEL_WIDTH, 52)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        germination = QPen(QColor(GOLD))
        germination.setStyle(Qt.PenStyle.DotLine)
        germination.setWidthF(1.6)
        painter.setPen(germination)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, 0), 15.0, 15.0)
        painter.setPen(QPen(QColor(GOLD), 2.0))
        gold_fill = QColor(GOLD)
        gold_fill.setAlphaF(0.35)
        painter.setBrush(gold_fill)
        painter.drawEllipse(QPointF(0, 2), 6.5, 6.5)
        # Brote: tallo + hoja hacia arriba (acento IA).
        painter.drawLine(QPointF(0, -4), QPointF(0, -12))
        painter.drawArc(QRectF(-8, -16, 8, 8), 0 * 16, 180 * 16)
        painter.setPen(QPen(QColor(INK)))
        font = QFont()
        font.setPointSizeF(8.0)
        font.setItalic(True)
        painter.setFont(font)
        label = self.title if len(self.title) <= 20 else self.title[:19] + "…"
        painter.drawText(
            QRectF(-_LABEL_WIDTH / 2, 17, _LABEL_WIDTH, 16),
            Qt.AlignmentFlag.AlignHCenter,
            label,
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        scene = self.scene()
        views = scene.views() if scene is not None else []
        if views and isinstance(views[0], FocoCanvas):
            views[0].seedClicked.emit(self.candidate_id)
        event.accept()


class FocoCanvas(QGraphicsView):
    """Vista de zonas con layout por slots. El centro es un hueco reservado."""

    satelliteActivated = Signal(str)  # noqa: N815 — centra al click/flecha (convención Qt)
    selectionChanged = Signal(list)  # noqa: N815 — multiselección Ctrl (convención Qt)
    seedClicked = Signal(str)  # noqa: N815 — Semilla IA ⇒ abrir revisión (convención Qt)
    # BETA2-CLEANUP-PANELES: click en la píldora del anillo ⇒ abrir el panel de
    # anillo (edición) del anillo actual. Sin argumentos: la vista resuelve el id.
    ringBannerClicked = Signal()  # noqa: N815 — convención Qt de señales

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        # BETA2-HOVER-07: repintado completo del viewport (como la cronología).
        # En modo Minimal, mostrar/ocultar el conector al hover dejaba los chips
        # a baja opacidad (fantasmas) sin repintar (en blanco).
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # PULIDO-07: viñeta cálida compartida con Mapa/Cronología (fondo
        # uniforme entre modos); _relayout la recentra al tamaño real.
        self.setBackgroundBrush(canvas_vignette_brush(0.0, 0.0, 1500.0))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._center_id = ""
        self._zone_meta: dict[str, list[dict]] = {key: [] for key in _ZONE_KEYS}
        self._items: dict[str, FocoBandItem] = {}
        self._selected: list[str] = []
        # FOCO-28: conector transitorio (línea + rótulo) al pasar el ratón por un
        # ítem de banda; se destruye con la escena (anular refs en _rebuild_scene).
        self._band_connector = None
        self._band_connector_label = None
        # FOCO-30: posición en escena de las tarjetas de ruleta (no entran en
        # _items) para que la transición direccional funcione al rotar el anillo.
        self._roulette_pos: dict[str, QPointF] = {}
        # FOCO-30: pistas planas de banda + scroll por rueda + banda con hover.
        self._band_tracks: dict[str, list["FocoBandItem"]] = {"top": [], "bottom": [], "right": []}
        self._band_scroll: dict[str, float] = {"top": 0.0, "bottom": 0.0, "right": 0.0}
        # BETA2-HOVER-02: tarjeta flotante de previsualización al posar el ratón
        # sobre un chip de banda (retrato + descripción entera, sin cortarse).
        from hosts.DesktopHostPySide.widgets.hover_preview_card import HoverPreviewController

        self._hover_preview = HoverPreviewController(self, self._hover_content_at)
        # UI2-21: pulso savia de la entidad que se está regando AHORA (satélite
        # o marco de rama); "" lo apaga. Notorio para CUALQUIER entidad.
        self._watering_active_id = ""
        self._watering_phase = 0.0
        self._watering_timer = QTimer(self)
        self._watering_timer.setInterval(60)
        self._watering_timer.timeout.connect(self._watering_tick)
        # FOCO-13: semillas IA germinando por zona: cid -> (zone, title).
        self._seed_meta: dict[str, tuple[str, str]] = {}
        self._seed_items: dict[str, FocoSeedItem] = {}
        # FOCO-22: cadena de contención (la inmediata primero) → marco.
        self._container_meta: list[dict] = []
        self._container_frame: FocoContainerFrame | None = None
        # FOCO-25: marcos concéntricos de la cadena (la inmediata la primera).
        self._container_frames: list[FocoContainerFrame] = []
        # FOCO-25: compañeras de rama (extensión derecha), previsualización de
        # rotación (prev/next) y destinos de navegación por teclado.
        self._branch_mates: list[dict] = []
        self._previews: dict[str, dict] = {}
        self._nav_targets: dict[str, str] = {}
        # FOCO-26: píldora del anillo del foco («Anillo: X (i/N)»).
        self._ring_label = ""
        # BETA2-CLEANUP-PANELES: rect (coords de viewport) de la píldora para
        # hit-test en mousePressEvent; vacío cuando no hay píldora dibujada.
        self._ring_pill_rect: QRectF = QRectF()
        # UI2-09: atmósfera de hojas compartida con Mapa/Cronología, con
        # ráfaga direccional al recentrar (gust). Se pinta bajo las bandas.
        self._atmosphere = CanvasAtmosphere(self, ctx=None, count=11)

    def set_atmosphere_context(self, ctx) -> None:
        """UI2-09: respeta el movimiento reducido (gate de animación del ctx)."""
        self._atmosphere.set_context(ctx)

    def showEvent(self, event) -> None:  # noqa: N802 (API Qt)
        super().showEvent(event)
        self._atmosphere.start()

    def hideEvent(self, event) -> None:  # noqa: N802 (API Qt)
        super().hideEvent(event)
        self._atmosphere.stop()

    def set_ring_label(self, text: str) -> None:
        """FOCO-26: fija la píldora del anillo del centro (esquina de rotación)."""
        self._ring_label = str(text or "")
        self.viewport().update()

    def set_assets_root(self, path) -> None:
        """BETA2-IMG: carpeta de assets del proyecto para los retratos.

        None = proyecto sin guardar (solo rutas legacy absolutas). Los items
        la leen desde la escena en su paint().
        """
        from pathlib import Path as _Path

        self._scene._portrait_assets_root = _Path(path) if path else None
        self.viewport().update()

    def _hover_content_at(self, view_pos):
        """BETA2-HOVER-02: resolver de la tarjeta flotante — chip de banda bajo el
        cursor → contenido (retrato + nombre + meta + descripción ENTERA), anclado
        al chip y esquivando el conector."""
        from hosts.DesktopHostPySide.widgets.hover_preview_card import HoverContent

        item = self.itemAt(view_pos)
        while item is not None and not isinstance(item, FocoBandItem):
            item = item.parentItem()
        if item is None or item.is_ghost:
            return None
        meta = " · ".join(b for b in (item._type_label(), item.ring_name, item.nature) if b)
        anchor = self.mapFromScene(item.sceneBoundingRect()).boundingRect()
        hole = self.center_hole_rect()
        connector = QRectF(item.scenePos(), hole.center()).normalized()
        avoid = self.mapFromScene(connector).boundingRect()
        return HoverContent(
            title=item.display_name,
            meta=meta,
            brief=item.brief,
            kind="entidad",
            entity_type=item.entity_type,
            image_path=item.image_path,
            image_crop=item.image_crop,
            assets_root=getattr(self._scene, "_portrait_assets_root", None),
            anchor_rect=anchor,
            avoid_rect=avoid,
        )

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def set_zones(
        self,
        center_id: str,
        zones: dict[str, list[dict]],
        containers: list[dict] | None = None,
        *,
        branch_mates: list[dict] | None = None,
        previews: dict[str, dict] | None = None,
        nav_targets: dict[str, str] | None = None,
    ) -> None:
        """Reconstruye el lienzo para un centro.

        ``zones`` mapea zona → lista ORDENADA de dicts con
        ``entity_id/name/entity_type/is_ghost/reason`` (+ ``ring_id``/``rank``
        para agrupar en sub-bandas y ``link_label`` para el rótulo del conector).
        ``containers`` es la cadena de contención (la inmediata primero): marco
        envolvente. ``branch_mates`` = compañeras de la rama directa (extensión
        derecha). ``previews`` = ``{"prev": dict, "next": dict}`` de rotación (se
        dibujan a la izquierda). ``nav_targets`` = ids de destino por tecla
        (``prev``/``next``/``up``/``down``) para ←/→ y Shift+↑/↓.
        """
        if center_id != self._center_id:
            self._seed_meta = {}
        self._center_id = center_id
        self._zone_meta = {key: list(zones.get(key, [])) for key in _ZONE_KEYS}
        self._container_meta = list(containers or [])
        self._branch_mates = list(branch_mates or [])
        self._previews = dict(previews or {})
        self._nav_targets = dict(nav_targets or {})
        self._selected = []
        self._rebuild_scene()
        self.selectionChanged.emit([])

    # -- Semillas IA (FOCO-13) ------------------------------------------

    def sync_seeds(self, seeds: list[tuple[str, str, str]]) -> None:
        """Sincroniza las semillas visibles: lista de (candidate_id, zone, title).

        Las de zona "drawer" NO llegan aquí (van como tarjeta al panel de riego).
        """
        self._seed_meta = {
            str(candidate_id): (zone if zone in _ZONE_KEYS else "entorno", str(title))
            for candidate_id, zone, title in seeds
        }
        self._rebuild_scene()

    def seed_ids(self) -> list[str]:
        return list(self._seed_meta.keys())

    def seeds_in_zone(self, zone: str) -> list[str]:
        return [cid for cid, (seed_zone, _t) in self._seed_meta.items() if seed_zone == zone]

    def bloom_seed(self, candidate_id: str) -> None:
        """Aceptada: la semilla deja el lienzo; lo aceptado aparece en su zona
        al reconstruirse el vecindario (el centro NO cambia — spec)."""
        self._seed_meta.pop(str(candidate_id), None)
        self._rebuild_scene()

    def wither_seed(self, candidate_id: str) -> None:
        self._seed_meta.pop(str(candidate_id), None)
        self._rebuild_scene()

    def _rebuild_scene(self) -> None:
        self._items.clear()
        self._seed_items.clear()
        self._scene.clear()
        # FOCO-28: scene.clear() destruye el conector transitorio; anular refs.
        self._band_connector = None
        self._band_connector_label = None
        # FOCO-30: se reconstruyen las pistas y las posiciones de ruleta.
        self._roulette_pos = {}
        self._band_tracks = {"top": [], "bottom": [], "right": []}
        self._relayout()
        # UI2-21: la reconstrucción destruye los items; re-aplica el pulso savia
        # si el riego seguía activo (los satélites/marcos son nuevos).
        if self._watering_active_id:
            item = self._watering_item(self._watering_active_id)
            if item is not None:
                item.set_watering_pulse(True)
                item.set_watering_phase(self._watering_phase)

    def _watering_item(self, entity_id: str):
        """UI2-21: satélite o marco de rama cuyo id coincide (o None)."""
        if not entity_id:
            return None
        item = self._items.get(entity_id)
        if item is not None:
            return item
        for frame in self._container_frames:
            if frame.container_id == entity_id:
                return frame
        return None

    def set_watering_active(self, entity_id: str) -> None:
        """UI2-21: enciende el pulso savia en la entidad que se está regando
        (satélite o marco de rama); "" lo apaga. Como el anillo savia del Mapa,
        para que desde el Foco se distinga SIEMPRE qué se está regando."""
        entity_id = str(entity_id or "")
        if entity_id == self._watering_active_id:
            return
        previous = self._watering_item(self._watering_active_id)
        if previous is not None:
            previous.set_watering_pulse(False)
        self._watering_active_id = entity_id
        self._watering_phase = 0.0
        item = self._watering_item(entity_id)
        if item is not None:
            item.set_watering_pulse(True)
            if not self._watering_timer.isActive():
                self._watering_timer.start()
        elif self._watering_timer.isActive():
            self._watering_timer.stop()

    def _watering_tick(self) -> None:
        item = self._watering_item(self._watering_active_id)
        if item is None:
            self._watering_timer.stop()
            return
        self._watering_phase += 0.12
        item.set_watering_phase(self._watering_phase)

    def zone_ids(self, zone: str) -> list[str]:
        return [meta["entity_id"] for meta in self._zone_meta.get(zone, [])]

    def container_ids(self) -> list[str]:
        """Cadena de contención del centro (FOCO-22: la inmediata primero)."""
        return [meta["entity_id"] for meta in self._container_meta]

    def selected_ids(self) -> list[str]:
        return list(self._selected)

    def center_hole_rect(self) -> QRectF:
        """Rect central reservado (coordenadas del viewport) para la tarjeta real."""
        width = max(1, self.viewport().width())
        height = max(1, self.viewport().height())
        return QRectF(width * 0.24, height * 0.26, width * 0.52, height * 0.48)

    # ------------------------------------------------------------------
    # Layout determinista por bandas
    # ------------------------------------------------------------------

    def _relayout(self) -> None:
        width = max(720, self.viewport().width())
        height = max(500, self.viewport().height())
        self._scene.setSceneRect(0, 0, width, height)
        # PULIDO-07: viñeta centrada en el corazón del lienzo (las bandas de
        # anillos, más oscuras, se pintan encima y conservan su lectura).
        self.setBackgroundBrush(
            canvas_vignette_brush(width / 2.0, height / 2.0, max(width, height, 600.0) * 0.75)
        )
        # Hueco central en coordenadas de la ESCENA (con el mismo clamp 720×500 que
        # el resto del layout): coincide con center_hole_rect() en viewports reales
        # y mantiene coherentes bandas, ruleta y marcos aun en viewports diminutos.
        hole = QRectF(width * 0.24, height * 0.26, width * 0.52, height * 0.48)

        def _spread(count: int, span: float, offset: float) -> list[float]:
            if count <= 0:
                return []
            step = span / (count + 1)
            return [offset + step * (index + 1) for index in range(count)]

        # FOCO-13: las semillas ocupan slots al FINAL de su zona.
        seeds_by_zone: dict[str, list[tuple[str, str]]] = {key: [] for key in _ZONE_KEYS}
        for candidate_id, (zone, title) in self._seed_meta.items():
            seeds_by_zone.get(zone, seeds_by_zone["entorno"]).append((candidate_id, title))

        def _add_seed_item(seed: tuple[str, str], pos: QPointF) -> None:
            candidate_id, title = seed
            zone = self._seed_meta[candidate_id][0]
            seed_item = FocoSeedItem(candidate_id, title, zone)
            seed_item.setPos(pos)
            self._scene.addItem(seed_item)
            self._seed_items[candidate_id] = seed_item

        def _make_band_item(meta: dict, band: str) -> FocoBandItem:
            item = FocoBandItem(
                meta["entity_id"],
                meta.get("name", ""),
                meta.get("entity_type", "nota"),
                is_ghost=bool(meta.get("is_ghost")),
                zone=meta.get("zone", "entorno"),
                brief=meta.get("brief", ""),
                link_label=meta.get("link_label", ""),
                image_path=meta.get("image_path", ""),
                image_crop=meta.get("image_crop"),
                ring_name=meta.get("ring_name", ""),
                nature=meta.get("nature", ""),
                band=band,
            )
            item.highlighted = meta["entity_id"] in self._selected
            self._scene.addItem(item)
            self._items[meta["entity_id"]] = item
            return item

        # FOCO-30: PISTAS de banda planas (una por banda), ordenadas por el payload
        # (rango→nombre). Se retira el apilado por sub-anillos: el empuje al desplegar
        # y el scroll por rueda necesitan una pista 1D. La contención NO va a bandas
        # (la muestra la estantería de la tarjeta + el marco).
        self._band_tracks["top"] = [_make_band_item(m, "top") for m in self._zone_meta["raices"]]
        self._band_tracks["bottom"] = [
            _make_band_item(m, "bottom") for m in self._zone_meta["brotes"]
        ]
        self._band_tracks["right"] = [
            _make_band_item(m, "right") for m in self._zone_meta["entorno"]
        ]
        for band, items in self._band_tracks.items():
            for index, item in enumerate(items):
                item.band_index = index
            self._layout_band(band)

        # Semillas IA por zona: cluster fijo en la esquina de la banda (fuera de la
        # pista scrollable; pocas por definición).
        for zone, at_right in (("raices", False), ("brotes", False), ("entorno", True)):
            seeds = seeds_by_zone[zone]
            if not seeds:
                continue
            if at_right:
                for seed, y in zip(seeds, _spread(len(seeds), height * 0.14, height * 0.04)):
                    _add_seed_item(seed, QPointF(width - _BAND_CHIP_W / 2 - 16, y))
            else:
                y = height * 0.05 if zone == "raices" else height * 0.95
                for seed, x in zip(seeds, _spread(len(seeds), width * 0.30, width * 0.05)):
                    _add_seed_item(seed, QPointF(x, y))

        # FOCO-25/30: marcos CONCÉNTRICOS de la cadena de ramas alrededor del centro;
        # los HERMANOS (misma rama) se muestran como miniaturas en el borde del marco
        # inmediato (ya no en el banner derecho).
        self._container_frame = None
        self._container_frames = []
        frame_left = hole.left()
        frame_right = hole.right()
        if self._container_meta:
            levels = self._container_meta[:3]
            deeper = " › ".join(str(m.get("name", "")) for m in self._container_meta[3:5])
            for index, level_meta in enumerate(levels):
                grow_x = 26.0 + 22.0 * index
                grow_y = 22.0 + 24.0 * index
                rect = hole.adjusted(-grow_x, -grow_y, grow_x, grow_y)
                frame_left = min(frame_left, rect.left())
                frame_right = max(frame_right, rect.right())
                note = ""
                also_in = str(level_meta.get("also_in", "") or "")
                if index == 0 and also_in:
                    note = f"también en {also_in}"
                elif index == len(levels) - 1 and deeper:
                    note = f"dentro de {deeper}"
                frame = FocoContainerFrame(
                    str(level_meta.get("entity_id", "")),
                    str(level_meta.get("name", "")),
                    note,
                )
                frame.set_frame_rect(rect)
                frame.setZValue(-2.0 - 0.1 * index)  # la interna gana el click
                self._scene.addItem(frame)
                self._container_frames.append(frame)
            self._container_frame = self._container_frames[0]
            self._container_frame.set_member_thumbs(list(self._branch_mates))

        # RULETA — tarjetas plegadas tenues flanqueando el centro (la anterior a
        # la izquierda, la siguiente a la derecha), justo fuera del marco. Se registra
        # su posición para la transición direccional al rotar (FOCO-30).
        gap = 16.0
        card_half = _ROULETTE_CARD_W / 2.0
        cy = hole.center().y()
        prev_meta = self._previews.get("prev")
        next_meta = self._previews.get("next")
        if prev_meta:
            cx = max(card_half + 6.0, frame_left - gap - card_half)
            self._add_roulette_card(prev_meta, QPointF(cx, cy))
        if next_meta:
            cx = min(width - card_half - 6.0, frame_right + gap + card_half)
            self._add_roulette_card(next_meta, QPointF(cx, cy))

    def _add_roulette_card(self, meta: dict, pos: QPointF) -> None:
        """FOCO-28/30: añade una tarjeta plegada de rotación en ``pos`` (no entra en
        ``_items``: es previsualización). Registra su posición para la transición."""
        card = FocoRouletteCard(
            meta["entity_id"],
            meta.get("name", ""),
            meta.get("entity_type", "nota"),
            brief=meta.get("brief", ""),
            image_path=meta.get("image_path", ""),
            image_crop=meta.get("image_crop"),
            direction_label=meta.get("link_label", ""),
        )
        card.setPos(pos)
        self._scene.addItem(card)
        self._roulette_pos[str(meta["entity_id"])] = QPointF(pos)

    def scene_pos_for(self, entity_id: str) -> QPointF | None:
        """FOCO-30: posición en escena de una entidad visible — chip de banda o, si
        no, tarjeta de ruleta (para la transición direccional al rotar el anillo)."""
        item = self._items.get(entity_id)
        if item is not None:
            return item.pos()
        return self._roulette_pos.get(entity_id)

    # ------------------------------------------------------------------
    # FOCO-30: pistas de banda planas — empuje al desplegar + scroll por rueda
    # ------------------------------------------------------------------

    def _band_metrics(self, band: str) -> tuple[float, float]:
        """(slot, track) por banda: paso entre chips y longitud útil de la pista."""
        width = max(720, self.viewport().width())
        height = max(500, self.viewport().height())
        if band == "right":
            return _BAND_CHIP_H + 14.0, height * 0.62
        return _BAND_CHIP_W + 16.0, width * 0.82

    def _clamp_band_scroll(self, band: str) -> float:
        items = self._band_tracks.get(band, [])
        slot, track = self._band_metrics(band)
        content = len(items) * slot
        low = min(0.0, track - content)
        return max(low, min(0.0, self._band_scroll.get(band, 0.0)))

    def _layout_band(self, band: str) -> None:
        """Coloca los chips de una banda en su pista 1D: base + scroll. BETA2-HOVER-02:
        los chips ya no se expanden, así que no hay empuje de vecinas."""
        items = self._band_tracks.get(band, [])
        if not items:
            return
        width = max(720, self.viewport().width())
        height = max(500, self.viewport().height())
        slot, track = self._band_metrics(band)
        content = len(items) * slot
        self._band_scroll[band] = self._clamp_band_scroll(band)
        horizontal = band in ("top", "bottom")
        if horizontal:
            start = (
                (width - content) / 2.0
                if content <= track
                else width * 0.09 + self._band_scroll[band]
            )
            cross = height * 0.12 if band == "top" else height * 0.88
        else:
            start = (
                (height - content) / 2.0
                if content <= track
                else height * 0.19 + self._band_scroll[band]
            )
            cross = width - _BAND_CHIP_W / 2.0 - 16.0
        for i, item in enumerate(items):
            along = start + i * slot + slot / 2.0
            item.setPos(QPointF(along, cross) if horizontal else QPointF(cross, along))

    def wheelEvent(self, event) -> None:  # noqa: N802
        """FOCO-30: si el cursor está sobre una banda llena, la rueda la desplaza."""
        pos = event.position()
        width = max(1, self.viewport().width())
        height = max(1, self.viewport().height())
        band = None
        if pos.y() < height * 0.24:
            band = "top"
        elif pos.y() > height * 0.76:
            band = "bottom"
        elif pos.x() > width * 0.86:
            band = "right"
        if band is None or not self._band_tracks.get(band):
            super().wheelEvent(event)
            return
        delta = event.angleDelta()
        step = float(delta.y()) if band == "right" else float(delta.x() or delta.y())
        self._band_scroll[band] = self._clamp_band_scroll(band) + step * 0.5
        self._band_scroll[band] = self._clamp_band_scroll(band)
        self._layout_band(band)
        event.accept()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if any(self._zone_meta.values()) or self._seed_meta or self._container_meta:
            selected = list(self._selected)
            self._rebuild_scene()
            self._selected = selected

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawBackground(painter, rect)
        # UI2-09: hojas al fondo (bajo las bandas translúcidas de UI2-01),
        # como en el resto de lienzos de Creación.
        self._atmosphere.paint(painter)
        # BETA2-CLEANUP-PANELES: por defecto sin píldora clicable; se fija abajo
        # solo si realmente se dibuja.
        self._ring_pill_rect = QRectF()
        # FOCO-22: cabeceras de zona — el lienzo se explica a sí mismo.
        if not self._center_id:
            return
        width = max(1, self.viewport().width())
        height = max(1, self.viewport().height())
        painter.save()
        # FOCO-25: TODO el cromo de fondo se pinta en coordenadas del VIEWPORT
        # (resetTransform) — una sola vez y anclado a la ventana, sin duplicados
        # por desalineación escena↔viewport.
        painter.resetTransform()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # UI2-01: franjas de Raíces (superior) y Brotes (inferior) en el tono
        # del borde de la viñeta común, translúcidas — la misma luz que el
        # fondo del Mapa/Cronología, delimitadas por una línea dorada sutil.
        band = QColor("#CFC4A8")
        band.setAlpha(80)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(band)
        painter.drawRect(QRectF(0, 0, width, height * 0.24))
        painter.drawRect(QRectF(0, height * 0.76, width, height * 0.24))
        # FOCO-28: tercera franja — BANDA DERECHA (entorno), entre las de arriba
        # y abajo, para que las tres bandas se lean como tales.
        painter.drawRect(QRectF(width * 0.86, height * 0.24, width * 0.14, height * 0.52))
        edge = QColor(GOLD_SOFT)
        edge.setAlpha(70)
        painter.setPen(QPen(edge, 1.0))
        painter.drawLine(QPointF(0, height * 0.24), QPointF(width, height * 0.24))
        painter.drawLine(QPointF(0, height * 0.76), QPointF(width, height * 0.76))
        painter.drawLine(QPointF(width * 0.86, height * 0.24), QPointF(width * 0.86, height * 0.76))
        caption_font = QFont()
        caption_font.setPointSizeF(7.5)
        caption_font.setBold(True)
        caption_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        painter.setFont(caption_font)
        painter.setPen(QPen(QColor(INK_MUTED)))
        # FOCO-28: las tres bandas se rotulan en su esquina — RAÍCES arriba,
        # BROTES abajo, ENTORNO en el borde derecho. Las píldoras de modo ya no
        # flotan aquí (viven en el banner superior); el rail de herramientas
        # sigue a la izquierda (x=72), así que los rótulos van a la DERECHA.
        painter.drawText(
            QRectF(width - 292, 8, 280, 16),
            Qt.AlignmentFlag.AlignRight,
            _ZONE_CAPTIONS["raices"],
        )
        painter.drawText(
            QRectF(width - 292, height - 22, 280, 16),
            Qt.AlignmentFlag.AlignRight,
            _ZONE_CAPTIONS["brotes"],
        )
        painter.drawText(
            QRectF(width - 158, height * 0.255, 146, 14),
            Qt.AlignmentFlag.AlignRight,
            _ZONE_CAPTIONS["entorno"],
        )
        # FOCO-26/28: píldora del anillo del foco, en la esquina inferior izquierda
        # (libre tras retirar el botón «◀ volver»).
        if self._ring_label:
            pill_font = QFont()
            pill_font.setPointSizeF(7.5)
            pill_font.setBold(True)
            painter.setFont(pill_font)
            metrics = painter.fontMetrics()
            text = f"◉ {self._ring_label}"
            pill_width = metrics.horizontalAdvance(text) + 20
            pill = QRectF(16, height - 26, pill_width, 18)
            # BETA2-CLEANUP-PANELES: guarda el rect para el hit-test del click.
            self._ring_pill_rect = QRectF(pill)
            painter.setPen(QPen(QColor(GOLD_SOFT)))
            painter.setBrush(QColor(SURFACE_HI))
            painter.drawRoundedRect(pill, 9.0, 9.0)
            painter.setPen(QPen(QColor(INK_SOFT)))
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    # ------------------------------------------------------------------
    # Interacción
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 (API Qt)
        # BETA2-CLEANUP-PANELES: la píldora del anillo (chrome pintado en el
        # fondo, coords de viewport) es clicable → abre el panel de anillo. El
        # resto de clics siguen su curso normal (ítems de escena, selección).
        if not self._ring_pill_rect.isEmpty():
            pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
            if self._ring_pill_rect.contains(pos):
                self.ringBannerClicked.emit()
                event.accept()
                return
        super().mousePressEvent(event)

    def _hole_edge_point(self, hole: QRectF, pos: QPointF) -> QPointF:
        """FOCO-28: punto del borde del hueco central en la dirección de ``pos``."""
        center = hole.center()
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        if dx == 0 and dy == 0:
            return center
        scales = []
        if dx != 0:
            scales.append((hole.width() / 2.0) / abs(dx))
        if dy != 0:
            scales.append((hole.height() / 2.0) / abs(dy))
        scale = min(scales) if scales else 0.0
        return QPointF(center.x() + dx * scale, center.y() + dy * scale)

    def _show_band_connector(self, entity_id: str) -> None:
        """FOCO-28: traza línea + rótulo del vínculo desde el ítem de banda al
        centro (solo al hover). Sustituye a los conectores siempre-dibujados."""
        self._hide_band_connector()
        item = self._items.get(entity_id)
        if item is None:
            return
        hole = self.center_hole_rect()
        pos = item.pos()
        edge = self._hole_edge_point(hole, pos)
        pen = QPen(QColor(GOLD_SOFT))
        pen.setWidthF(1.4)
        line = self._scene.addLine(pos.x(), pos.y(), edge.x(), edge.y(), pen)
        line.setZValue(-1)
        self._band_connector = line
        link_label = str(getattr(item, "link_label", "") or "")
        if link_label:
            label_font = QFont()
            label_font.setPointSizeF(7.0)
            text_item = self._scene.addSimpleText(link_label, label_font)
            text_item.setBrush(QColor(INK_MUTED))
            mid = QPointF((pos.x() + edge.x()) / 2.0, (pos.y() + edge.y()) / 2.0)
            rect = text_item.boundingRect()
            text_item.setPos(mid.x() - rect.width() / 2.0, mid.y() - rect.height() - 1.0)
            text_item.setZValue(-1)
            self._band_connector_label = text_item
        # BETA2-HOVER-07: fuerza el repintado para recomponer los chips fantasma.
        self.viewport().update()

    def _hide_band_connector(self) -> None:
        """FOCO-28: retira la línea y el rótulo transitorios (si existen)."""
        removed = False
        for attr in ("_band_connector", "_band_connector_label"):
            obj = getattr(self, attr, None)
            if obj is not None:
                try:
                    self._scene.removeItem(obj)
                except (RuntimeError, ValueError):
                    pass
                setattr(self, attr, None)
                removed = True
        # BETA2-HOVER-07: al retirar el conector, repinta para no dejar rastro ni
        # blanquear los chips a baja opacidad bajo el área afectada.
        if removed:
            self.viewport().update()

    def _on_item_clicked(self, entity_id: str, *, ctrl: bool) -> None:
        if ctrl:
            if entity_id in self._selected:
                self._selected.remove(entity_id)
            else:
                self._selected.append(entity_id)
            for item_id, item in self._items.items():
                item.highlighted = item_id in self._selected
                item.update()
            self.selectionChanged.emit(list(self._selected))
            return
        self.satelliteActivated.emit(entity_id)

    def _arrow_target(self, key: int, *, shift: bool) -> str:
        """FOCO-25: ←/→ rotan el anillo; ↑/↓ rama↔miembros; Shift+↑/↓ saltan de anillo."""
        if key == Qt.Key.Key_Left and not shift:
            return self._nav_targets.get("prev", "")
        if key == Qt.Key.Key_Right and not shift:
            return self._nav_targets.get("next", "")
        if key == Qt.Key.Key_Up:
            return self._nav_targets.get("up" if shift else "container", "")
        if key == Qt.Key.Key_Down:
            return self._nav_targets.get("down" if shift else "member", "")
        return ""

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            target = self._arrow_target(key, shift=shift)
            if target:
                self.satelliteActivated.emit(target)
            event.accept()  # sin destino ⇒ no-op, jamás algo destructivo
            return
        super().keyPressEvent(event)
