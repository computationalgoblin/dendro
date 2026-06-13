"""BETA1-G04 — Vista cronológica: el árbol mirado desde el lado.

Complementaria a la vista concéntrica (mismo proyecto, otro eje):
- Eje Y descendente = tiempo (años del calendario del proyecto).
- Eras = estratos horizontales (misma estética de sombras que los anillos).
- Entidades = líneas de vida verticales (nacen, mueren o continúan).
- Hitos = nodos pequeños sobre las líneas de vida, ramificando como raíces
  hacia las entidades que afectan.
- X = columnas por anillo efectivo (mismo orden causal que la concéntrica).

SIN física (contrato G01 §7): el layout es determinista — el tiempo no se
negocia con muelles. La parte de cálculo es pura (testeable sin Qt).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from packages.ui.graph_physics.rings import (
    UNCLASSIFIED_RING_ID,
    resolve_effective_ring_id,
)

# ── Constantes de layout ──────────────────────────────────────────────────

TOP_MARGIN = 70.0
LEFT_MARGIN = 150.0       # carril de etiquetas de era
COLUMN_GAP = 56.0         # separación entre columnas de anillo
LANE_WIDTH = 92.0         # separación entre líneas de vida del mismo anillo
MIN_GAP_PX = 26.0         # alto mínimo entre dos años-ancla consecutivos
MAX_GAP_PX = 150.0        # compresión: los desiertos temporales no se estiran
PX_PER_YEAR = 7.0
BOTTOM_PAD_YEARS = 2


def _enum_value(value: Any, default: str = "") -> str:
    return str(getattr(value, "value", value) or default)


# ── Escala temporal (pura) ────────────────────────────────────────────────


class YearScale:
    """Mapa año → y, monótono creciente, comprimido por tramos.

    Los años-ancla (nacimientos, muertes, hitos, límites de era, presente)
    definen tramos; cada tramo mide ``clamp(años * PX_PER_YEAR, MIN, MAX)``.
    Años intermedios se interpolan linealmente dentro de su tramo.
    """

    def __init__(self, anchor_years: list[int]):
        anchors = sorted(set(int(y) for y in anchor_years)) or [0]
        self._years: list[int] = anchors
        self._ys: list[float] = [TOP_MARGIN]
        for previous, current in zip(anchors, anchors[1:]):
            gap_years = current - previous
            gap_px = min(max(gap_years * PX_PER_YEAR, MIN_GAP_PX), MAX_GAP_PX)
            self._ys.append(self._ys[-1] + gap_px)

    @property
    def min_year(self) -> int:
        return self._years[0]

    @property
    def max_year(self) -> int:
        return self._years[-1]

    @property
    def bottom(self) -> float:
        return self._ys[-1]

    def y(self, year: int) -> float:
        year = int(year)
        years, ys = self._years, self._ys
        if year <= years[0]:
            return ys[0] - min((years[0] - year) * PX_PER_YEAR, MAX_GAP_PX)
        if year >= years[-1]:
            return ys[-1] + min((year - years[-1]) * PX_PER_YEAR, MAX_GAP_PX)
        # Interpolación dentro del tramo
        for index in range(len(years) - 1):
            if years[index] <= year <= years[index + 1]:
                y0, y1 = ys[index], ys[index + 1]
                a, b = years[index], years[index + 1]
                if b == a:
                    return y0
                t = (year - a) / (b - a)
                return y0 + t * (y1 - y0)
        return ys[-1]


# ── Modelo de layout (puro) ───────────────────────────────────────────────


@dataclass
class EraBand:
    era_id: str
    name: str
    start_year: int
    end_year: int | None
    y0: float
    y1: float
    index: int  # para alternar sombras


@dataclass
class RingColumn:
    ring_id: str
    name: str
    x_center: float
    x_left: float
    x_right: float


@dataclass
class Lifeline:
    entity_id: str
    name: str
    ring_id: str
    is_tree: bool
    x: float
    birth_year: int
    death_year: int | None
    y_birth: float
    y_end: float
    alive: bool
    color: str = ""


@dataclass
class MilestoneMark:
    milestone_id: str
    title: str
    year: int
    x: float
    y: float
    linked_xs: list[float] = field(default_factory=list)


@dataclass
class ChronoLayout:
    eras: list[EraBand]
    columns: list[RingColumn]
    lifelines: list[Lifeline]
    milestones: list[MilestoneMark]
    width: float
    height: float
    present_year: int
    y_present: float


# ── Construcción (pura, sin Qt) ───────────────────────────────────────────


def _effective_rings(project: Any) -> tuple[dict[str, str], set[str]]:
    """entity_id → ring efectivo (C01 §4.2) y conjunto de ramas."""
    entities = list(getattr(project, "entities", []) or [])
    relations = list(getattr(project, "relations", []) or [])
    explicit: dict[str, str] = {}
    trees: set[str] = set()
    for entity in entities:
        eid = str(getattr(entity, "id", ""))
        kind = _enum_value(getattr(entity, "entity_type", None)).lower()
        if kind == "contenedor":
            trees.add(eid)
        layer_ids = list(getattr(entity, "layer_ids", []) or [])
        if layer_ids and str(layer_ids[0]):
            explicit[eid] = str(layer_ids[0])
    membership: dict[str, str] = {}
    for relation in relations:
        if _enum_value(getattr(relation, "relation_type", None)).lower() != "contiene":
            continue
        source = str(getattr(relation, "source_id", ""))
        target = str(getattr(relation, "target_id", ""))
        if source in trees and target:
            membership[target] = source
    resolved = {
        str(getattr(entity, "id", "")): resolve_effective_ring_id(
            str(getattr(entity, "id", "")),
            explicit_ring_ids=explicit,
            membership=membership,
            is_tree=frozenset(trees),
        )
        for entity in entities
    }
    return resolved, trees


def _ring_order(project: Any) -> list[tuple[str, str]]:
    """[(ring_id, nombre)] por rango causal; '__unclassified__' al final."""
    layers = list(getattr(project, "world_layers", []) or [])
    def rank(layer: Any) -> float:
        meta = getattr(layer, "metadata", {}) or {}
        try:
            return float(meta.get("causal_rank"))
        except (TypeError, ValueError):
            try:
                return float(getattr(layer, "order", 0) or 0)
            except (TypeError, ValueError):
                return 0.0
    ordered = sorted(
        (layer for layer in layers if getattr(layer, "is_visible", True)),
        key=rank,
    )
    result = [(str(getattr(layer, "id", "")), str(getattr(layer, "name", "Anillo"))) for layer in ordered]
    result.append((UNCLASSIFIED_RING_ID, "Sin anillo"))
    return result


def build_chrono_layout(project: Any) -> ChronoLayout:
    """Layout determinista de la vista cronológica (contrato G01 §7)."""
    chronology = getattr(project, "project_chronology", None)
    present_year = int(getattr(chronology, "present_year", 0) or 0)
    eras_domain = list(getattr(chronology, "eras", []) or [])
    entities = list(getattr(project, "entities", []) or [])
    milestones = list(getattr(project, "causal_milestones", []) or [])

    # 1. Años-ancla
    anchor_years: list[int] = [present_year]
    for era in eras_domain:
        anchor_years.append(int(getattr(era, "start_year", 0) or 0))
        if getattr(era, "end_year", None) is not None:
            anchor_years.append(int(era.end_year))
    for entity in entities:
        birth = getattr(entity, "birth_year", None)
        anchor_years.append(int(birth) if birth is not None else present_year)
        death = getattr(entity, "death_year", None)
        if death is not None:
            anchor_years.append(int(death))
    milestone_years: dict[str, int] = {}
    for hito in milestones:
        year = getattr(hito, "year", None)
        year = int(year) if isinstance(year, int) and not isinstance(year, bool) else present_year
        milestone_years[str(getattr(hito, "id", ""))] = year
        anchor_years.append(year)
    anchor_years.append(max(anchor_years) + BOTTOM_PAD_YEARS)
    scale = YearScale(anchor_years)

    # 2. Columnas por anillo efectivo
    effective, trees = _effective_rings(project)
    ring_ids_used = {effective.get(str(getattr(e, "id", "")), UNCLASSIFIED_RING_ID) for e in entities}
    columns: list[RingColumn] = []
    lanes_by_ring: dict[str, list[Any]] = {}
    x_cursor = LEFT_MARGIN + COLUMN_GAP
    for ring_id, ring_name in _ring_order(project):
        members = [
            entity for entity in entities
            if effective.get(str(getattr(entity, "id", "")), UNCLASSIFIED_RING_ID) == ring_id
        ]
        if not members:
            continue
        if ring_id == UNCLASSIFIED_RING_ID and ring_id not in ring_ids_used:
            continue
        members.sort(key=lambda e: (
            int(getattr(e, "birth_year", None) if getattr(e, "birth_year", None) is not None else present_year),
            str(getattr(e, "name", "")),
        ))
        lanes_by_ring[ring_id] = members
        width = max(len(members) - 1, 0) * LANE_WIDTH
        columns.append(RingColumn(
            ring_id=ring_id,
            name=ring_name,
            x_center=x_cursor + width / 2.0,
            x_left=x_cursor - LANE_WIDTH / 2.0,
            x_right=x_cursor + width + LANE_WIDTH / 2.0,
        ))
        x_cursor += width + LANE_WIDTH / 2.0 + COLUMN_GAP

    total_width = max(x_cursor + COLUMN_GAP, LEFT_MARGIN + 400.0)

    # 3. Eras como estratos
    era_bands: list[EraBand] = []
    bottom_year = scale.max_year
    sorted_eras = sorted(eras_domain, key=lambda era: (int(getattr(era, "start_year", 0) or 0), int(getattr(era, "order", 0) or 0)))
    for index, era in enumerate(sorted_eras):
        start = int(getattr(era, "start_year", 0) or 0)
        end = getattr(era, "end_year", None)
        era_bands.append(EraBand(
            era_id=str(getattr(era, "id", "")),
            name=str(getattr(era, "name", "Era")),
            start_year=start,
            end_year=int(end) if end is not None else None,
            y0=scale.y(start),
            y1=scale.y(int(end)) if end is not None else scale.y(bottom_year) + MIN_GAP_PX,
            index=index,
        ))

    # 4. Líneas de vida
    x_by_entity: dict[str, float] = {}
    lifelines: list[Lifeline] = []
    column_by_ring = {column.ring_id: column for column in columns}
    for ring_id, members in lanes_by_ring.items():
        column = column_by_ring[ring_id]
        start_x = column.x_center - (max(len(members) - 1, 0) * LANE_WIDTH) / 2.0
        for lane_index, entity in enumerate(members):
            eid = str(getattr(entity, "id", ""))
            birth = getattr(entity, "birth_year", None)
            birth = int(birth) if birth is not None else present_year
            death = getattr(entity, "death_year", None)
            alive = death is None
            end_year = present_year if alive else int(death)
            x = start_x + lane_index * LANE_WIDTH
            x_by_entity[eid] = x
            meta = getattr(entity, "custom_metadata", {}) or {}
            color = str(meta.get("_node_color", "") or meta.get("tree_color", "") or "")
            lifelines.append(Lifeline(
                entity_id=eid,
                name=str(getattr(entity, "name", "") or "Sin nombre"),
                ring_id=ring_id,
                is_tree=eid in trees,
                x=x,
                birth_year=birth,
                death_year=None if alive else int(death),
                y_birth=scale.y(birth),
                y_end=max(scale.y(end_year), scale.y(birth) + 10.0),
                alive=alive,
                color=color,
            ))

    # 5. Hitos: nodo en su año sobre la entidad principal, raíces al resto
    marks: list[MilestoneMark] = []
    for hito in milestones:
        hid = str(getattr(hito, "id", ""))
        year = milestone_years.get(hid, present_year)
        affected = [str(v) for v in (getattr(hito, "affected_entity_ids", []) or []) if str(v) in x_by_entity]
        meta = getattr(hito, "metadata", {}) or {}
        primary = str(meta.get("primary_entity_id", "") or "")
        if primary not in x_by_entity:
            primary = affected[0] if affected else ""
        x = x_by_entity.get(primary, LEFT_MARGIN + COLUMN_GAP / 2.0)
        linked = [x_by_entity[eid] for eid in affected if eid != primary][:6]
        marks.append(MilestoneMark(
            milestone_id=hid,
            title=str(getattr(hito, "title", "") or "Hito"),
            year=year,
            x=x,
            y=scale.y(year),
            linked_xs=linked,
        ))

    height = scale.bottom + 80.0
    return ChronoLayout(
        eras=era_bands,
        columns=columns,
        lifelines=lifelines,
        milestones=marks,
        width=total_width,
        height=height,
        present_year=present_year,
        y_present=scale.y(present_year),
    )


# ── Vista Qt ──────────────────────────────────────────────────────────────

try:  # la parte pura debe poder importarse sin PySide6
    from PySide6.QtCore import QPointF, QRectF, Qt, Signal
    from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QGraphicsEllipseItem,
        QGraphicsItem,
        QGraphicsPathItem,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsSimpleTextItem,
        QGraphicsView,
        QStyle,
    )
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False


if HAS_QT:

    _BG = QColor("#E6DFCD")  # BETA1-G07: alineado con la viñeta de la concéntrica
    _SHADOW = QColor(92, 90, 62)
    _INK = QColor("#504B2E")
    _MUTED = QColor("#7C806E")
    _LINE = QColor("#8A8563")
    _WHITE = QColor(255, 255, 253, 250)

    class _LifelineHead(QGraphicsEllipseItem):
        """Nodo-cabeza de la línea de vida (misma hoja blanca con halo)."""

        def __init__(self, lifeline: Lifeline, radius: float):
            super().__init__(-radius, -radius, radius * 2, radius * 2)
            self.entity_id = lifeline.entity_id
            halo = QColor(lifeline.color) if lifeline.color else QColor("#AFA77A")
            halo.setAlpha(70)
            self.setPen(QPen(halo, 5))
            self.setBrush(QBrush(_WHITE))
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.setZValue(30)

        def paint(self, painter, option, widget=None):  # noqa: N802
            option.state = QStyle.State(option.state & ~QStyle.StateFlag.State_Selected)
            super().paint(painter, option, widget)
            if self.isSelected():
                painter.setPen(QPen(QColor(_SHADOW.red(), _SHADOW.green(), _SHADOW.blue(), 66), 3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))

    class _MilestoneNode(QGraphicsEllipseItem):
        def __init__(self, mark: MilestoneMark, radius: float = 6.0):
            super().__init__(-radius, -radius, radius * 2, radius * 2)
            self.milestone_id = mark.milestone_id
            self.setPen(QPen(_LINE, 1.4))
            self.setBrush(QBrush(QColor("#F8F5EA")))
            self.setToolTip(f"{mark.title} — año {mark.year}")
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.setZValue(40)

        def paint(self, painter, option, widget=None):  # noqa: N802
            option.state = QStyle.State(option.state & ~QStyle.StateFlag.State_Selected)
            super().paint(painter, option, widget)
            if self.isSelected():
                painter.setPen(QPen(QColor(_SHADOW.red(), _SHADOW.green(), _SHADOW.blue(), 80), 2.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(self.rect().adjusted(1.5, 1.5, -1.5, -1.5))

    class ChronoCanvasView(QGraphicsView):
        """Vista cronológica del proyecto. Determinista, SIN física."""

        entityActivated = Signal(str)
        milestoneActivated = Signal(str)
        escapePressed = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setScene(QGraphicsScene(self))
            self.setRenderHints(
                QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
            )
            self.setBackgroundBrush(QBrush(_BG))
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self._space_panning = False
            self._layout: ChronoLayout | None = None
            # BETA1-G08: misma atmósfera sutil de hojas que la concéntrica.
            from hosts.DesktopHostPySide.widgets.canvas_atmosphere import CanvasAtmosphere
            self._atmosphere = CanvasAtmosphere(self, ctx=None, count=11)

        def set_atmosphere_context(self, ctx) -> None:
            self._atmosphere.set_context(ctx)

        def drawBackground(self, painter, rect):  # noqa: N802 (Qt API)
            super().drawBackground(painter, rect)
            self._atmosphere.paint(painter)

        def showEvent(self, event):  # noqa: N802 (Qt API)
            super().showEvent(event)
            self._atmosphere.start()

        def hideEvent(self, event):  # noqa: N802 (Qt API)
            self._atmosphere.stop()
            super().hideEvent(event)

        # — construcción de escena —

        def set_project(self, project: Any) -> None:
            scene = self.scene()
            scene.clear()
            if project is None:
                self._layout = None
                return
            layout = build_chrono_layout(project)
            self._layout = layout

            # Estratos de era (sombras alternas, sin contorno — estética F)
            for band in layout.eras:
                rect = QGraphicsRectItem(0, band.y0, layout.width, max(band.y1 - band.y0, MIN_GAP_PX))
                alpha = 8 if band.index % 2 == 0 else 18
                rect.setBrush(QBrush(QColor(_SHADOW.red(), _SHADOW.green(), _SHADOW.blue(), alpha)))
                rect.setPen(QPen(Qt.PenStyle.NoPen))
                rect.setZValue(-30)
                scene.addItem(rect)
                label = QGraphicsSimpleTextItem(band.name)
                label.setBrush(QBrush(_MUTED))
                font = QFont("Georgia")
                font.setPointSize(11)
                font.setItalic(True)
                label.setFont(font)
                label.setPos(14, band.y0 + 8)
                label.setZValue(-10)
                scene.addItem(label)
                years_text = f"{band.start_year} → {band.end_year if band.end_year is not None else '…'}"
                years = QGraphicsSimpleTextItem(years_text)
                years.setBrush(QBrush(QColor(_MUTED.red(), _MUTED.green(), _MUTED.blue(), 160)))
                small = QFont("Georgia")
                small.setPointSize(8)
                years.setFont(small)
                years.setPos(14, band.y0 + 28)
                years.setZValue(-10)
                scene.addItem(years)

            # Cabeceras de columna (anillos — el lector conserva el mapa mental)
            for column in layout.columns:
                header = QGraphicsSimpleTextItem(column.name)
                header.setBrush(QBrush(_MUTED))
                font = QFont("Georgia")
                font.setPointSize(9)
                header.setFont(font)
                header.setPos(column.x_center - header.boundingRect().width() / 2.0, TOP_MARGIN - 46)
                scene.addItem(header)

            # Línea del presente
            present_pen = QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 90), 1, Qt.PenStyle.DashLine)
            scene.addLine(0, layout.y_present, layout.width, layout.y_present, present_pen)
            present_label = QGraphicsSimpleTextItem(f"presente · {layout.present_year}")
            present_label.setBrush(QBrush(QColor(_MUTED.red(), _MUTED.green(), _MUTED.blue(), 190)))
            tiny = QFont("Georgia")
            tiny.setPointSize(8)
            tiny.setItalic(True)
            present_label.setFont(tiny)
            present_label.setPos(layout.width - present_label.boundingRect().width() - 16, layout.y_present - 16)
            scene.addItem(present_label)

            # Líneas de vida
            for lifeline in layout.lifelines:
                width = 3.4 if lifeline.is_tree else 2.2
                pen = QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 200), width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                line = scene.addLine(lifeline.x, lifeline.y_birth, lifeline.x, lifeline.y_end, pen)
                line.setZValue(10)
                if lifeline.alive:
                    # Continúa: trazo que se desvanece bajo el presente
                    fade = QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 60), width, Qt.PenStyle.DotLine)
                    scene.addLine(lifeline.x, lifeline.y_end, lifeline.x, lifeline.y_end + 26, fade).setZValue(10)
                else:
                    # Remate sutil de muerte
                    cap = QPen(QColor(_LINE.red(), _LINE.green(), _LINE.blue(), 150), 2)
                    scene.addLine(lifeline.x - 6, lifeline.y_end, lifeline.x + 6, lifeline.y_end, cap).setZValue(10)
                head = _LifelineHead(lifeline, 8.0 if lifeline.is_tree else 6.5)
                head.setPos(lifeline.x, lifeline.y_birth)
                scene.addItem(head)
                name = QGraphicsSimpleTextItem(lifeline.name)
                name.setBrush(QBrush(_INK))
                font = QFont("Georgia")
                font.setPointSize(9)
                if lifeline.is_tree:
                    font.setBold(True)
                name.setFont(font)
                name.setPos(lifeline.x + 11, lifeline.y_birth - 7)
                name.setZValue(31)
                scene.addItem(name)

            # Hitos: nodo + raíces orgánicas hacia las entidades afectadas
            root_pen = QPen(QColor(_SHADOW.red(), _SHADOW.green(), _SHADOW.blue(), 80), 1.4)
            for mark in layout.milestones:
                for target_x in mark.linked_xs:
                    path = QPainterPath(QPointF(mark.x, mark.y))
                    dx = target_x - mark.x
                    path.cubicTo(
                        QPointF(mark.x + dx * 0.25, mark.y + 18),
                        QPointF(mark.x + dx * 0.75, mark.y + 18),
                        QPointF(target_x, mark.y),
                    )
                    root = QGraphicsPathItem(path)
                    root.setPen(root_pen)
                    root.setBrush(Qt.BrushStyle.NoBrush)
                    root.setZValue(20)
                    scene.addItem(root)
                node = _MilestoneNode(mark)
                node.setPos(mark.x, mark.y)
                scene.addItem(node)

            rect = QRectF(0, 0, layout.width, layout.height)
            scene.setSceneRect(rect.adjusted(-60, -60, 60, 60))

        # — interacción (coherente con la concéntrica: zoom/pan/Space) —

        def wheelEvent(self, event):  # noqa: N802
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            current = self.transform().m11()
            if 0.12 < current * factor < 6.0:
                self.scale(factor, factor)

        def keyPressEvent(self, event):  # noqa: N802
            if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
                self._space_panning = True
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                event.accept()
                return
            if event.key() == Qt.Key.Key_Escape:
                self.scene().clearSelection()
                self.escapePressed.emit()
                event.accept()
                return
            super().keyPressEvent(event)

        def keyReleaseEvent(self, event):  # noqa: N802
            if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
                self._space_panning = False
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                event.accept()
                return
            super().keyReleaseEvent(event)

        def mouseDoubleClickEvent(self, event):  # noqa: N802
            item = self.itemAt(event.position().toPoint())
            while item is not None:
                if isinstance(item, _MilestoneNode):
                    self.milestoneActivated.emit(item.milestone_id)
                    event.accept()
                    return
                if isinstance(item, _LifelineHead):
                    self.entityActivated.emit(item.entity_id)
                    event.accept()
                    return
                item = item.parentItem()
            super().mouseDoubleClickEvent(event)

        def fit_all(self) -> None:
            if self.scene().items():
                self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
                if self.transform().m11() > 1.0:
                    self.resetTransform()


__all__ = [
    "ChronoLayout",
    "EraBand",
    "Lifeline",
    "MilestoneMark",
    "RingColumn",
    "YearScale",
    "build_chrono_layout",
]
if HAS_QT:
    __all__.append("ChronoCanvasView")
