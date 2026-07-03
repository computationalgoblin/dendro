"""Lienzo del Modo Foco: zonas Raíces / Entorno / Brotes en torno al centro.

Layout DETERMINISTA por bandas (sin física libre): Raíces arriba, Entorno en
las columnas laterales, Brotes abajo; el centro queda reservado para la tarjeta
o formulario de la entidad en foco (un widget real que FocoView superpone,
patrón de overlays de la casa). Pintura a mano — PROHIBIDO QGraphicsEffect en
elementos dinámicos (regla del repo).

Interacción (spec BETA2-FOCO):
- click simple o doble en satélite ⇒ centrar (``satelliteActivated``);
- Ctrl+click ⇒ multiselección resaltada (``selectionChanged``), el centro
  sigue siendo uno;
- flechas ⇒ ←/→ vecinas del Entorno, ↑ rama contenedora y luego Raíces,
  ↓ Brotes; centran directamente, sin Enter; sin destino ⇒ no-op.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsView,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    CANVAS,
    ENTITY_KIND_PALETTE,
    GOLD,
    INK,
    INK_MUTED,
    INK_SOFT,
    LINE_SOFT,
)

_NODE_RADIUS = 24.0
_LABEL_WIDTH = 128.0
_ZONE_KEYS = ("raices", "entorno", "brotes")


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
    ) -> None:
        super().__init__()
        self.entity_id = entity_id
        self.display_name = name
        self.entity_type = entity_type
        self.is_ghost = is_ghost
        self.zone = zone
        self.reason = reason
        self.highlighted = False  # multiselección Ctrl
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, False)

    def boundingRect(self) -> QRectF:  # noqa: N802 (API Qt)
        return QRectF(-_LABEL_WIDTH / 2, -_NODE_RADIUS - 6, _LABEL_WIDTH, _NODE_RADIUS * 2 + 30)

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
        painter.setOpacity(0.62 if self.is_ghost else 1.0)
        painter.setPen(QPen(QColor(INK)))
        font = QFont()
        font.setPointSizeF(8.5)
        painter.setFont(font)
        label = self.display_name if len(self.display_name) <= 22 else self.display_name[:21] + "…"
        rect = QRectF(-_LABEL_WIDTH / 2, _NODE_RADIUS + 3, _LABEL_WIDTH, 22)
        painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)

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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setBackgroundBrush(QColor(CANVAS))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._center_id = ""
        self._zone_meta: dict[str, list[dict]] = {key: [] for key in _ZONE_KEYS}
        self._items: dict[str, FocoSatelliteItem] = {}
        self._selected: list[str] = []
        # FOCO-13: semillas IA germinando por zona: cid -> (zone, title).
        self._seed_meta: dict[str, tuple[str, str]] = {}
        self._seed_items: dict[str, FocoSeedItem] = {}

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def set_zones(self, center_id: str, zones: dict[str, list[dict]]) -> None:
        """Reconstruye el lienzo para un centro.

        ``zones`` mapea zona → lista ORDENADA de dicts con
        ``entity_id/name/entity_type/is_ghost/reason`` (el orden es el de
        ``foco_zones.classify_neighbors`` y gobierna la navegación por flechas).
        """
        if center_id != self._center_id:
            self._seed_meta = {}
        self._center_id = center_id
        self._zone_meta = {key: list(zones.get(key, [])) for key in _ZONE_KEYS}
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
        self._relayout()

    def zone_ids(self, zone: str) -> list[str]:
        return [meta["entity_id"] for meta in self._zone_meta.get(zone, [])]

    def container_ids(self) -> list[str]:
        """Ramas contenedoras del centro (viven en Entorno con reason='container')."""
        return [
            meta["entity_id"]
            for meta in self._zone_meta.get("entorno", [])
            if meta.get("reason") == "container"
        ]

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
        center = QPointF(width / 2.0, height / 2.0)

        def _spread(count: int, span: float, offset: float) -> list[float]:
            if count <= 0:
                return []
            step = span / (count + 1)
            return [offset + step * (index + 1) for index in range(count)]

        # FOCO-13: las semillas ocupan slots al FINAL de su zona (tras las
        # entidades) — germinan en su sitio y lo aceptado permanece ahí.
        seeds_by_zone: dict[str, list[tuple[str, str]]] = {key: [] for key in _ZONE_KEYS}
        for candidate_id, (zone, title) in self._seed_meta.items():
            seeds_by_zone[zone].append((candidate_id, title))

        placements: list[tuple[dict | None, tuple[str, str] | None, QPointF]] = []

        def _band(zone: str, y_pos: float) -> None:
            entities = self._zone_meta[zone]
            seeds = seeds_by_zone[zone]
            xs = _spread(len(entities) + len(seeds), width * 0.76, width * 0.12)
            for meta, x in zip(entities, xs):
                placements.append((meta, None, QPointF(x, y_pos)))
            for seed, x in zip(seeds, xs[len(entities) :]):
                placements.append((None, seed, QPointF(x, y_pos)))

        _band("raices", height * 0.13)
        _band("brotes", height * 0.87)
        entorno = self._zone_meta["entorno"]
        entorno_seeds = seeds_by_zone["entorno"]
        combined: list[tuple[dict | None, tuple[str, str] | None]] = [
            (meta, None) for meta in entorno
        ] + [(None, seed) for seed in entorno_seeds]
        left = combined[0::2]
        right = combined[1::2]
        for (meta, seed), y in zip(left, _spread(len(left), height * 0.56, height * 0.22)):
            placements.append((meta, seed, QPointF(width * 0.09, y)))
        for (meta, seed), y in zip(right, _spread(len(right), height * 0.56, height * 0.22)):
            placements.append((meta, seed, QPointF(width * 0.91, y)))

        pen = QPen(QColor(LINE_SOFT))
        pen.setWidthF(1.0)
        for meta, seed, position in placements:
            # Línea sutil hacia el centro, detrás del elemento.
            direction = center - position
            trimmed = position + direction * 0.42
            line = self._scene.addLine(position.x(), position.y(), trimmed.x(), trimmed.y(), pen)
            line.setZValue(-1)
            if seed is not None:
                candidate_id, title = seed
                zone = self._seed_meta[candidate_id][0]
                seed_item = FocoSeedItem(candidate_id, title, zone)
                seed_item.setPos(position)
                self._scene.addItem(seed_item)
                self._seed_items[candidate_id] = seed_item
                continue
            item = FocoSatelliteItem(
                meta["entity_id"],
                meta.get("name", ""),
                meta.get("entity_type", "nota"),
                is_ghost=bool(meta.get("is_ghost")),
                zone=meta.get("zone", "entorno"),
                reason=meta.get("reason", ""),
            )
            item.highlighted = meta["entity_id"] in self._selected
            item.setPos(position)
            self._scene.addItem(item)
            self._items[meta["entity_id"]] = item

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if any(self._zone_meta.values()) or self._seed_meta:
            selected = list(self._selected)
            self._rebuild_scene()
            self._selected = selected

    # ------------------------------------------------------------------
    # Interacción
    # ------------------------------------------------------------------

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

    def _arrow_target(self, key: int) -> str:
        entorno = self.zone_ids("entorno")
        if key == Qt.Key.Key_Right:
            return entorno[0] if entorno else ""
        if key == Qt.Key.Key_Left:
            return entorno[-1] if entorno else ""
        if key == Qt.Key.Key_Up:
            containers = self.container_ids()
            if containers:
                return containers[0]
            raices = self.zone_ids("raices")
            return raices[0] if raices else ""
        if key == Qt.Key.Key_Down:
            brotes = self.zone_ids("brotes")
            return brotes[0] if brotes else ""
        return ""

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            target = self._arrow_target(key)
            if target:
                self.satelliteActivated.emit(target)
            event.accept()  # sin destino ⇒ no-op, jamás algo destructivo
            return
        super().keyPressEvent(event)
