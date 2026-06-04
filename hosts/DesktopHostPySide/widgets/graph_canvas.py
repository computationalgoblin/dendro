"""Graph canvas for B31-T03/B31-T06.

Visual graph derived from the active project. The graph is a view over existing
entities and relations; relation creation is emitted as an intent and executed
outside the canvas through application services.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.design_system import EmptyState, enum_human


_NODE_COLORS = {
    "personaje": "#7C9BFF",
    "lugar": "#7EC8A5",
    "organizacion": "#DCA35F",
    "faccion": "#D9908F",
    "objeto": "#C9A5FF",
    "evento": "#E0C46C",
    "concepto": "#9BB4C7",
    "contenedor": "#D0D8E0",
}

_EDGE_COLORS = {
    "es_aliado_de": "#78B891",
    "es_amigo_de": "#78B891",
    "es_enemigo_de": "#D46A6A",
    "es_rival_de": "#D46A6A",
    "esta_en_conflicto_con": "#D46A6A",
    "traiciono": "#D46A6A",
    "pertenece_a": "#7C9BFF",
    "contiene": "#7EC8A5",
    "esta_ubicado_en": "#7EC8A5",
    "esta_en": "#7EC8A5",
    "esta_relacionado_con": "#A4AEC0",
    "es_familiar_de": "#C9A5FF",
    "ama_a": "#D9908F",
    "es_mentor_de": "#7C9BFF",
    "depende_de": "#DCA35F",
    "busca": "#E0C46C",
    "protege": "#78B891",
    "oculta": "#9BB4C7",
    "sospecha": "#DCA35F",
    "gobierna": "#DCA35F",
    "sirve_a": "#7EC8A5",
    "conoce": "#9BB4C7",
    "controla": "#DCA35F",
    "posee": "#C9A5FF",
    "simboliza": "#9BB4C7",
    "faccion": "#D9908F",
}

_STATUS_COLORS = {
    "canonico": "#6CCB8E",
    "canon": "#6CCB8E",
    "borrador": "#E0C46C",
    "propuesto": "#DCA35F",
    "archivado": "#8993A5",
}

_VISIBILITY_COLORS = {
    "oculto": "#D46A6A",
    "secreto": "#D46A6A",
    "privado": "#D46A6A",
    "publico": "#6CCB8E",
    "publico_mundo": "#6CCB8E",
}


_CONTAINER_COLOR = "#E8E2D2"
_CONTAINER_HEADER_COLOR = "#BDB6A2"
_CONTAINER_PADDING = 44.0
_CONTAINER_HEADER_HEIGHT = 48.0
_CONTAINER_MIN_WIDTH = 280.0
_CONTAINER_MIN_HEIGHT = 200.0
_CONTAINER_CHILD_SPACING = 52.0


@dataclass(frozen=True)
class _NodeView:
    entity: Any
    entity_id: str
    name: str
    kind: str
    subtitle: str
    canon: str
    visibility: str
    proposed: bool = False


@dataclass(frozen=True)
class _EdgeView:
    relation: Any
    relation_id: str
    source_id: str
    target_id: str
    kind: str
    label: str
    direction: str = "unidireccional"
    color: str = ""
    proposed: bool = False


def _enum_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _entity_view(entity: Any) -> _NodeView:
    kind = _enum_value(getattr(entity, "entity_type", None), "entidad")
    subtitle = (
        getattr(entity, "brief_description", None)
        or getattr(entity, "brief", None)
        or getattr(entity, "description", None)
        or "Sin descripción breve"
    )
    return _NodeView(
        entity=entity,
        entity_id=str(getattr(entity, "id", "")),
        name=str(getattr(entity, "name", "Sin nombre")),
        kind=kind,
        subtitle=str(subtitle),
        canon=_enum_value(getattr(entity, "canon_state", None), ""),
        visibility=_enum_value(getattr(entity, "visibility_state", None), ""),
    )


def _relation_view(relation: Any) -> _EdgeView:
    kind = _enum_value(getattr(relation, "relation_type", None), "relación")
    label = enum_human(kind)
    direction = _enum_value(getattr(relation, "direction", None), "unidireccional")
    meta = dict(getattr(relation, "custom_metadata", {}) or {})
    color = meta.get("_edge_color", "")
    return _EdgeView(
        relation=relation,
        relation_id=str(getattr(relation, "id", "")),
        source_id=str(getattr(relation, "source_id", "")),
        target_id=str(getattr(relation, "target_id", "")),
        kind=kind,
        label=label,
        direction=direction,
        color=color,
    )


def _candidate_is_pending_ai(candidate: Any) -> bool:
    source = str(getattr(candidate, "source", "")).lower()
    state = _enum_value(getattr(candidate, "state", None), "")
    return source in {"ia", "ai"} and state in {"pendiente", "requiere_revision"}


def _candidate_node_view(candidate: Any) -> _NodeView | None:
    data = dict(getattr(candidate, "proposed_data", {}) or {})
    name = data.get("name") or getattr(candidate, "title", "")
    if not name:
        return None
    kind = str(data.get("entity_type") or data.get("type") or "concepto")
    return _NodeView(
        entity=candidate,
        entity_id=f"cand_node_{getattr(candidate, 'id', '')}",
        name=str(name),
        kind=kind,
        subtitle="Sugerencia IA · no canon",
        canon="propuesto",
        visibility="privado",
        proposed=True,
    )


def _candidate_edge_view(candidate: Any, known_entity_ids: set[str]) -> _EdgeView | None:
    data = dict(getattr(candidate, "proposed_data", {}) or {})
    source_id = str(data.get("source_id") or "")
    target_id = str(data.get("target_id") or "")
    if not source_id or not target_id or source_id not in known_entity_ids or target_id not in known_entity_ids:
        return None
    kind = str(data.get("relation_type") or "esta_relacionado_con")
    return _EdgeView(
        relation=candidate,
        relation_id=f"cand_rel_{getattr(candidate, 'id', '')}",
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        label=f"IA · {enum_human(kind)}",
        proposed=True,
    )


def _fit_text(text: str, max_chars: int) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


class GraphNodeItem(QGraphicsEllipseItem):
    """Visual node item; stores full entity ID internally, never shows it."""

    def __init__(self, node: _NodeView, *, x: float, y: float, radius: float = 72.0):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.node = node
        self.radius = radius
        self._coherence_selected = False
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(2)

        color = QColor(_NODE_COLORS.get(node.kind.lower(), "#8EA4C8"))
        self._normal_pen = QPen(QColor("#DCA35F" if node.proposed else "#F7F1E8"), 2.6 if node.proposed else 2.0)
        if node.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self._highlight_pen = QPen(QColor("#EBCB8B"), 4.0)
        self._selected_pen = QPen(QColor("#5B8DEF"), 5.0)
        self.setBrush(QBrush(color.lighter(112)))
        self.setPen(self._normal_pen)

        title = QGraphicsSimpleTextItem(_fit_text(node.name, 22), self)
        title.setBrush(QBrush(QColor("#111827")))
        title.setScale(1.08)
        title_rect = title.boundingRect()
        title.setPos(-title_rect.width() / 2, -25)

        subtitle = QGraphicsSimpleTextItem(_fit_text(enum_human(node.kind), 24), self)
        subtitle.setBrush(QBrush(QColor("#374151")))
        subtitle_rect = subtitle.boundingRect()
        subtitle.setPos(-subtitle_rect.width() / 2, -4)

        note = QGraphicsSimpleTextItem(_fit_text(node.subtitle, 30), self)
        note.setBrush(QBrush(QColor("#4B5563")))
        note.setScale(0.82)
        note_rect = note.boundingRect()
        note.setPos(-note_rect.width() * 0.41, 18)

        self._status_dot = QGraphicsEllipseItem(-radius + 12, -radius + 12, 14, 14, self)
        self._status_dot.setBrush(QBrush(QColor(_STATUS_COLORS.get(node.canon.lower(), "#A4AEC0"))))
        self._status_dot.setPen(QPen(QColor("#F7F1E8"), 1.2))

        visibility_key = node.visibility.lower()
        if visibility_key in _VISIBILITY_COLORS and visibility_key not in {"publico", "publico_mundo"}:
            self._visibility_dot = QGraphicsEllipseItem(radius - 26, -radius + 12, 14, 14, self)
            self._visibility_dot.setBrush(QBrush(QColor(_VISIBILITY_COLORS[visibility_key])))
            self._visibility_dot.setPen(QPen(QColor("#F7F1E8"), 1.2))

    def set_drag_highlight(self, enabled: bool):
        if self._coherence_selected and not enabled:
            self.setPen(self._selected_pen)
            return
        self.setPen(self._highlight_pen if enabled else self._normal_pen)

    def set_coherence_selected(self, enabled: bool):
        self._coherence_selected = bool(enabled)
        self.setPen(self._selected_pen if enabled else self._normal_pen)

    def itemChange(self, change, value):
        return super().itemChange(change, value)


class GraphTreeItem(QGraphicsRectItem):
    """Visual tree-container item for ``contenedor`` entities.

    Renders as a rounded rectangle with a header bar that displays the
    container name and type.  Child entities (linked via ``contiene``
    relations) are positioned inside the rectangle.  The container
    auto-resizes to encompass its children with padding.

    Shares the same interaction contract as ``GraphNodeItem``:
    movable, selectable, drag-highlight, coherence-selection, and
    exposes ``node`` for entity-id lookups.
    """

    def __init__(self, node: _NodeView, *, x: float, y: float, width: float = _CONTAINER_MIN_WIDTH, height: float = _CONTAINER_MIN_HEIGHT):
        super().__init__(-width / 2, -height / 2, width, height)
        self.node = node
        self._half_w = width / 2
        self._half_h = height / 2
        self._coherence_selected = False
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(0)  # Behind regular nodes (z=2)

        # Pens
        self._normal_pen = QPen(QColor("#DCA35F" if node.proposed else "#A4AEC0"), 2.0 if not node.proposed else 2.6)
        if node.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self._highlight_pen = QPen(QColor("#EBCB8B"), 3.5)
        self._selected_pen = QPen(QColor("#5B8DEF"), 4.0)

        # Background fill — semi-transparent warm tone
        bg_color = QColor(_CONTAINER_COLOR)
        bg_color.setAlpha(160)
        self.setBrush(QBrush(bg_color))
        self.setPen(self._normal_pen)

        # Header bar (child rect at top)
        header_rect = QRectF(-width / 2, -height / 2, width, _CONTAINER_HEADER_HEIGHT)
        self._header_item = QGraphicsRectItem(header_rect, self)
        header_bg = QColor(_CONTAINER_HEADER_COLOR)
        header_bg.setAlpha(200)
        self._header_item.setBrush(QBrush(header_bg))
        self._header_item.setPen(QPen(Qt.PenStyle.NoPen))

        # Title text in header
        title = QGraphicsSimpleTextItem(_fit_text(node.name, 28), self)
        title.setBrush(QBrush(QColor("#2D2A1E")))
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        title_rect = title.boundingRect()
        title.setPos(-width / 2 + 10, -height / 2 + (_CONTAINER_HEADER_HEIGHT - title_rect.height()) / 2)

        # Subtitle (entity type)
        subtitle = QGraphicsSimpleTextItem(_fit_text(enum_human(node.kind), 20), self)
        subtitle.setBrush(QBrush(QColor("#5C5A3E")))
        subtitle.setFont(QFont("", 9))
        subtitle_rect = subtitle.boundingRect()
        subtitle.setPos(
            -width / 2 + 10,
            -height / 2 + _CONTAINER_HEADER_HEIGHT + 4,
        )

        # Status dot (top-right corner)
        self._status_dot = QGraphicsEllipseItem(
            width / 2 - 22,
            -height / 2 + 8,
            14, 14,
            self,
        )
        self._status_dot.setBrush(QBrush(QColor(_STATUS_COLORS.get(node.canon.lower(), "#A4AEC0"))))
        self._status_dot.setPen(QPen(QColor("#F7F1E8"), 1.2))

        # Visibility indicator
        visibility_key = node.visibility.lower()
        if visibility_key in _VISIBILITY_COLORS and visibility_key not in {"publico", "publico_mundo", "publico_mundo"}:
            self._visibility_dot = QGraphicsEllipseItem(
                width / 2 - 40,
                -height / 2 + 8,
                14, 14,
                self,
            )
            self._visibility_dot.setBrush(QBrush(QColor(_VISIBILITY_COLORS[visibility_key])))
            self._visibility_dot.setPen(QPen(QColor("#F7F1E8"), 1.2))

        # Brief description label
        brief = _fit_text(node.subtitle, 50)
        if brief:
            brief_item = QGraphicsSimpleTextItem(brief, self)
            brief_item.setBrush(QBrush(QColor("#6B7280")))
            brief_item.setFont(QFont("", 8))
            brief_item.setPos(
                -width / 2 + 10,
                -height / 2 + _CONTAINER_HEADER_HEIGHT + 18,
            )

        # Track children for resizing
        self._child_nodes: list[GraphNodeItem] = []

    # ------------------------------------------------------------------
    # Public API (mirrors GraphNodeItem)
    # ------------------------------------------------------------------

    def add_child_node(self, child: GraphNodeItem):
        """Register a child GraphNodeItem positioned inside this container."""
        self._child_nodes.append(child)

    def child_node_count(self) -> int:
        return len(self._child_nodes)

    def resize_to_fit_children(self):
        """Expand the rectangle so all children fit with padding."""
        if not self._child_nodes:
            return
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for child in self._child_nodes:
            cx = child.pos().x() - self.pos().x()
            cy = child.pos().y() - self.pos().y()
            cr = child.radius
            min_x = min(min_x, cx - cr)
            min_y = min(min_y, cy - cr)
            max_x = max(max_x, cx + cr)
            max_y = max(max_y, cy + cr)
        # Add padding and header space
        min_x -= _CONTAINER_PADDING
        min_y -= _CONTAINER_PADDING + _CONTAINER_HEADER_HEIGHT + 20  # extra space for subtitle/brief
        max_x += _CONTAINER_PADDING
        max_y += _CONTAINER_PADDING
        w = max(_CONTAINER_MIN_WIDTH, max_x - min_x)
        h = max(_CONTAINER_MIN_HEIGHT, max_y - min_y)
        self._half_w = w / 2
        self._half_h = h / 2
        self.setRect(min_x, min_y, w, h)
        # Update header bar
        self._header_item.setRect(QRectF(min_x, min_y, w, _CONTAINER_HEADER_HEIGHT))
        # Update status dot position
        self._status_dot.setRect(max_x - 18, min_y + 8, 14, 14)
        if hasattr(self, "_visibility_dot"):
            self._visibility_dot.setRect(max_x - 36, min_y + 8, 14, 14)

    @property
    def radius(self) -> float:  # noqa: D401 — compatibility with GraphNodeItem.radius
        """Effective 'radius' for edge shortening (half the shorter side)."""
        return min(self._half_w, self._half_h)

    def set_drag_highlight(self, enabled: bool):
        if self._coherence_selected and not enabled:
            self.setPen(self._selected_pen)
            return
        self.setPen(self._highlight_pen if enabled else self._normal_pen)

    def set_coherence_selected(self, enabled: bool):
        self._coherence_selected = bool(enabled)
        self.setPen(self._selected_pen if enabled else self._normal_pen)

    def paint(self, painter: QPainter, option, widget=None):
        """Override to draw rounded rectangle."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRoundedRect(self.rect(), 12.0, 12.0)

    def itemChange(self, change, value):
        # When the container moves, reposition child nodes accordingly
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self._child_nodes:
            delta = value - self._previous_pos if hasattr(self, "_previous_pos") else QPointF(0, 0)
            for child in self._child_nodes:
                child.setPos(child.pos() + delta)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            self._previous_pos = self.pos()
        return super().itemChange(change, value)


class GraphEdgeItem(QGraphicsPathItem):
    """Selectable relation edge derived from a domain relation.

    Draws arrowheads for directed edges and positions the handle
    near the source (directed) or at the center (bidirectional).
    """

    _ARROW_SIZE = 12.0

    def __init__(self, edge: _EdgeView, source: GraphNodeItem | GraphTreeItem, target: GraphNodeItem | GraphTreeItem):
        super().__init__()
        self.edge = edge
        self.source = source
        self.target = target
        self._is_bidirectional = edge.direction == "bidireccional"
        self._coherence_selected = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(3)  # Above container (z=0) and nodes (z=2) for clickability

        # Resolve colour: stored colour > type colour > default
        base_color = edge.color or _EDGE_COLORS.get(edge.kind.lower(), "#A4AEC0")
        color = QColor("#DCA35F" if edge.proposed else base_color)

        self._normal_pen = QPen(color, 2.6 if edge.proposed else 2.2)
        if edge.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self._normal_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._selected_pen = QPen(color.lighter(135), 4.0)
        self._selected_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(self._normal_pen)
        self._color = color

        # Label
        self.label_item = QGraphicsSimpleTextItem(_fit_text(edge.label, 28), self)
        self.label_item.setBrush(QBrush(QColor("#6B7280")))
        self.label_item.setScale(0.86)

        # Handle (bolita)
        self.handle_item = QGraphicsEllipseItem(-5, -5, 10, 10, self)
        self.handle_item.setBrush(QBrush(QColor("#D08770")))
        self.handle_item.setPen(QPen(QColor("#F7F1E8"), 1.2))
        self.handle_item.setToolTip("Abrir relación")
        self.handle_item.setAcceptHoverEvents(True)
        self.handle_item.setCursor(Qt.CursorShape.PointingHandCursor)

        # Arrowhead polygons (drawn as child items)
        self._arrow_fwd = QGraphicsPathItem(self)
        self._arrow_fwd.setPen(QPen(color, 1.0))
        self._arrow_fwd.setBrush(QBrush(color))
        self._arrow_fwd.setZValue(2)
        if self._is_bidirectional:
            self._arrow_bwd = QGraphicsPathItem(self)
            self._arrow_bwd.setPen(QPen(color, 1.0))
            self._arrow_bwd.setBrush(QBrush(color))
            self._arrow_bwd.setZValue(2)
        else:
            self._arrow_bwd = None

        self.update_path()

    @staticmethod
    def _make_arrowhead(tip: QPointF, angle: float, size: float) -> QPainterPath:
        """Create a filled triangular arrowhead pointing at *tip*."""
        p1 = QPointF(
            tip.x() - size * math.cos(angle - math.pi / 6),
            tip.y() - size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            tip.x() - size * math.cos(angle + math.pi / 6),
            tip.y() - size * math.sin(angle + math.pi / 6),
        )
        path = QPainterPath(tip)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        return path

    def update_path(self):
        start = self.source.scenePos()
        end = self.target.scenePos()

        # Shorten the line slightly so the arrowhead doesn't overlap the node circle
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        dist = math.hypot(dx, dy) or 1.0
        shorten = min(self.source.radius + 4, dist * 0.15)

        start_adj = QPointF(
            start.x() + (dx / dist) * shorten,
            start.y() + (dy / dist) * shorten,
        )
        end_adj = QPointF(
            end.x() - (dx / dist) * shorten,
            end.y() - (dy / dist) * shorten,
        )

        # Bezier curve
        ctrl_offset = QPointF(-dy * 0.12, dx * 0.12)
        c1 = QPointF(
            start_adj.x() + dx * 0.45 + ctrl_offset.x(),
            start_adj.y() + dy * 0.45 + ctrl_offset.y(),
        )
        c2 = QPointF(
            start_adj.x() + dx * 0.55 + ctrl_offset.x(),
            start_adj.y() + dy * 0.55 + ctrl_offset.y(),
        )
        path = QPainterPath(start_adj)
        path.cubicTo(c1, c2, end_adj)
        self.setPath(path)

        # Arrowhead at target (always for directed; for bidir too)
        angle_at_end = math.atan2(
            end_adj.y() - c2.y(),
            end_adj.x() - c2.x(),
        )
        self._arrow_fwd.setPath(self._make_arrowhead(end_adj, angle_at_end, self._ARROW_SIZE))

        # Arrowhead at source (bidirectional only)
        if self._arrow_bwd is not None:
            angle_at_start = math.atan2(
                start_adj.y() - c1.y(),
                start_adj.x() - c1.x(),
            )
            self._arrow_bwd.setPath(self._make_arrowhead(start_adj, angle_at_start, self._ARROW_SIZE))

        # Label at ~45% (so it doesn't overlap arrows)
        label_pt = path.pointAtPercent(0.45)
        rect = self.label_item.boundingRect()
        self.label_item.setPos(label_pt.x() - rect.width() * 0.43, label_pt.y() - 18)

        # Handle: centered for bidirectional, near source (25%) for directed
        if self._is_bidirectional:
            handle_pt = path.pointAtPercent(0.5)
        else:
            handle_pt = path.pointAtPercent(0.25)
        self.handle_item.setPos(handle_pt)

    def set_coherence_selected(self, enabled: bool):
        self._coherence_selected = bool(enabled)
        self.setPen(self._selected_pen if enabled else self._normal_pen)

    def mousePressEvent(self, event):
        self.setPen(self._selected_pen)
        super().mousePressEvent(event)


class GraphCanvasView(QGraphicsView):
    """Interactive view: pan/zoom with selectable nodes and edges."""

    entitySelected = Signal(str)
    relationSelected = Signal(str)
    relationCreateRequested = Signal(str, str)
    graphSelectionChanged = Signal(list, list)
    nodeAssignToTreeRequested = Signal(str, str)  # entity_id, tree_entity_id

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(QBrush(QColor("#F7F1E8")))
        self.scene_obj = QGraphicsScene(self)
        self.scene_obj.setSceneRect(QRectF(-1600, -1100, 3200, 2200))
        self.setScene(self.scene_obj)
        self._nodes: dict[str, GraphNodeItem] = {}
        self._trees: dict[str, GraphTreeItem] = {}
        self._edges: list[GraphEdgeItem] = []
        self._membership: dict[str, str] = {}  # entity_id -> tree_entity_id
        self._pending_source: GraphNodeItem | None = None
        self._drag_source: GraphNodeItem | None = None
        self._drag_target: GraphNodeItem | None = None
        self._drag_origin_view_pos = QPointF()
        self._drag_line: QGraphicsLineItem | None = None
        self._selected_entity_ids: set[str] = set()
        self._selected_relation_ids: set[str] = set()
        # Alt+Drag state for assigning nodes to tree containers
        self._alt_source: GraphNodeItem | None = None
        self._alt_tree_target: GraphTreeItem | None = None
        self._alt_line: QGraphicsLineItem | None = None
        self._alt_origin_view_pos = QPointF()

    def selected_entity_ids(self) -> list[str]:
        return list(self._selected_entity_ids)

    def selected_relation_ids(self) -> list[str]:
        return list(self._selected_relation_ids)

    def selection_payload(self) -> tuple[list[str], list[str]]:
        return self.selected_entity_ids(), self.selected_relation_ids()

    def _emit_selection_changed(self):
        self.graphSelectionChanged.emit(self.selected_entity_ids(), self.selected_relation_ids())

    def clear_selection(self, *, emit: bool = True):
        for item in self._nodes.values():
            item.set_coherence_selected(False)
        for item in self._trees.values():
            item.set_coherence_selected(False)
        for item in self._edges:
            item.set_coherence_selected(False)
        self._selected_entity_ids.clear()
        self._selected_relation_ids.clear()
        if emit:
            self._emit_selection_changed()

    def wheelEvent(self, event):
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        self.scale(factor, factor)

    def _item_node_at(self, view_pos) -> GraphNodeItem | GraphTreeItem | None:
        """Find a GraphNodeItem or GraphTreeItem under *view_pos*, ignoring drag overlays."""
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if isinstance(check, (GraphNodeItem, GraphTreeItem)):
                    return check
                check = check.parentItem()
        return None

    def _item_edge_at(self, view_pos) -> GraphEdgeItem | None:
        """Find a GraphEdgeItem under *view_pos*, ignoring drag overlays."""
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if isinstance(check, GraphEdgeItem):
                    return check
                check = check.parentItem()
        return None

    def _set_single_node_selection(self, node: GraphNodeItem):
        self.clear_selection(emit=False)
        self._selected_entity_ids.add(node.node.entity_id)
        node.set_coherence_selected(True)
        self._emit_selection_changed()

    def _set_single_edge_selection(self, edge: GraphEdgeItem):
        self.clear_selection(emit=False)
        self._selected_relation_ids.add(edge.edge.relation_id)
        edge.set_coherence_selected(True)
        self._emit_selection_changed()

    def _toggle_node_selection(self, node: GraphNodeItem):
        entity_id = node.node.entity_id
        if entity_id in self._selected_entity_ids:
            self._selected_entity_ids.remove(entity_id)
            node.set_coherence_selected(False)
        else:
            self._selected_entity_ids.add(entity_id)
            node.set_coherence_selected(True)
        self._emit_selection_changed()

    def _toggle_edge_selection(self, edge: GraphEdgeItem):
        relation_id = edge.edge.relation_id
        if relation_id in self._selected_relation_ids:
            self._selected_relation_ids.remove(relation_id)
            edge.set_coherence_selected(False)
        else:
            self._selected_relation_ids.add(relation_id)
            edge.set_coherence_selected(True)
        self._emit_selection_changed()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            node = self._item_node_at(event.position())

            # Alt+Click on a node or container: start tree-assignment drag
            if alt and node is not None and isinstance(node, (GraphNodeItem, GraphTreeItem)):
                self._alt_source = node
                self._alt_origin_view_pos = event.position()
                event.accept()
                return

            if node is not None:
                if ctrl:
                    self._toggle_node_selection(node)
                    event.accept()
                    return
                self._set_single_node_selection(node)
                self._pending_source = node
                self._drag_origin_view_pos = event.position()
                self.entitySelected.emit(node.node.entity_id)
                event.accept()
                return
            edge = self._item_edge_at(event.position())
            if edge is not None:
                if ctrl:
                    self._toggle_edge_selection(edge)
                    event.accept()
                    return
                self._set_single_edge_selection(edge)
                self.relationSelected.emit(edge.edge.relation_id)
                event.accept()
                return
            self.clear_selection()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Alt-drag: moving node into tree container
        if self._alt_source is not None and self._alt_line is None:
            delta = event.position() - self._alt_origin_view_pos
            if abs(delta.x()) + abs(delta.y()) > 10:
                self._start_alt_drag(self._alt_source)
        if self._alt_line is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            tree_target = self._item_tree_at(event.position())
            self._update_alt_drag(scene_pos, tree_target)
            event.accept()
            return

        if self._pending_source is not None and self._drag_source is None:
            delta = event.position() - self._drag_origin_view_pos
            if abs(delta.x()) + abs(delta.y()) > 10:
                self._start_relation_drag(self._pending_source)
        if self._drag_source is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._update_relation_drag(scene_pos, self._item_node_at(event.position()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # Alt-drag release: assign node to tree
        if self._alt_line is not None:
            source_item = self._alt_source
            target_tree = self._item_tree_at(event.position())
            self._finish_alt_drag()
            if target_tree is not None and source_item is not None:
                self.nodeAssignToTreeRequested.emit(
                    source_item.node.entity_id, target_tree.node.entity_id
                )
            event.accept()
            return

        if self._drag_source is not None:
            source = self._drag_source
            target = self._item_node_at(event.position())
            self._finish_relation_drag(target)
            if target is not None and target is not source:
                self.relationCreateRequested.emit(source.node.entity_id, target.node.entity_id)
            event.accept()
            return
        self._pending_source = None
        self._alt_source = None
        super().mouseReleaseEvent(event)

    def _start_relation_drag(self, source: GraphNodeItem | GraphTreeItem):
        self._drag_source = source
        self._drag_target = None
        line = QGraphicsLineItem()
        pen = QPen(QColor("#D08770"), 2.5, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line.setPen(pen)
        line.setZValue(3)
        self._drag_line = line
        self.scene_obj.addItem(line)
        source.set_drag_highlight(True)

    def _update_relation_drag(self, scene_pos: QPointF, target: GraphNodeItem | GraphTreeItem | None):
        if self._drag_source is None or self._drag_line is None:
            return
        start = self._drag_source.scenePos()
        self._drag_line.setLine(QLineF(start, scene_pos))
        if target is self._drag_source:
            target = None
        if target is not self._drag_target:
            if self._drag_target is not None:
                self._drag_target.set_drag_highlight(False)
            self._drag_target = target
            if self._drag_target is not None:
                self._drag_target.set_drag_highlight(True)

    def _finish_relation_drag(self, target: GraphNodeItem | GraphTreeItem | None):
        if self._drag_source is not None:
            self._drag_source.set_drag_highlight(False)
        if self._drag_target is not None:
            self._drag_target.set_drag_highlight(False)
        if self._drag_line is not None:
            self.scene_obj.removeItem(self._drag_line)
            self._drag_line = None
        self._pending_source = None
        self._drag_source = None
        self._drag_target = None

    def _item_tree_at(self, view_pos) -> GraphTreeItem | None:
        """Find a GraphTreeItem under *view_pos*."""
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if isinstance(check, GraphTreeItem):
                    return check
                check = check.parentItem()
        return None

    def _start_alt_drag(self, source: GraphNodeItem):
        line = QGraphicsLineItem()
        pen = QPen(QColor("#5B8DEF"), 2.5, Qt.PenStyle.DashDotLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line.setPen(pen)
        line.setZValue(3)
        self._alt_line = line
        self.scene_obj.addItem(line)

    def _update_alt_drag(self, scene_pos: QPointF, target: GraphTreeItem | None):
        if self._alt_source is None or self._alt_line is None:
            return
        start = self._alt_source.scenePos()
        self._alt_line.setLine(QLineF(start, scene_pos))
        if target is not self._alt_tree_target:
            if self._alt_tree_target is not None:
                self._alt_tree_target.set_drag_highlight(False)
            self._alt_tree_target = target
            if self._alt_tree_target is not None:
                self._alt_tree_target.set_drag_highlight(True)

    def _finish_alt_drag(self):
        if self._alt_tree_target is not None:
            self._alt_tree_target.set_drag_highlight(False)
        if self._alt_line is not None:
            self.scene_obj.removeItem(self._alt_line)
            self._alt_line = None
        self._alt_source = None
        self._alt_tree_target = None

    def would_create_cycle(self, child_id: str, parent_tree_id: str) -> bool:
        """Check if adding child_id to parent_tree_id would create a cycle."""
        if child_id == parent_tree_id:
            return True
        current = parent_tree_id
        visited = set()
        while current in self._membership:
            if current == child_id:
                return True
            if current in visited:
                break
            visited.add(current)
            current = self._membership[current]
        return False

    def tree_container_for(self, entity_id: str) -> str | None:
        """Return the tree entity_id that contains entity_id, or None."""
        return self._membership.get(entity_id)

    def clear_graph(self):
        self.clear_selection(emit=False)
        self.scene_obj.clear()
        self._nodes.clear()
        self._trees.clear()
        self._edges.clear()
        self._emit_selection_changed()

    def set_graph(self, nodes: list[_NodeView], edges: list[_EdgeView]):
        self.clear_graph()
        if not nodes:
            return

        # ── Separate containers from regular nodes ──
        container_nodes: list[_NodeView] = []
        regular_nodes: list[_NodeView] = []
        for node in nodes:
            if node.kind.lower() == "contenedor":
                container_nodes.append(node)
            else:
                regular_nodes.append(node)

        # ── Build a map of "contiene" relations: container_id -> set of child_ids ──
        contains_map: dict[str, set[str]] = {}
        contained_set: set[str] = set()  # all child entity IDs
        for edge in edges:
            if edge.kind.lower() == "contiene":
                contains_map.setdefault(edge.source_id, set()).add(edge.target_id)
                contained_set.add(edge.target_id)

        # ── Layout parameters ──
        # Non-contained, non-container nodes arranged in a circle
        free_nodes = [n for n in regular_nodes if n.entity_id not in contained_set]
        radius = max(220, min(620, 80 * max(len(free_nodes), len(container_nodes))))
        center = QPointF(0, 0)

        # ── Create regular (non-container) node items ──
        for idx, node in enumerate(regular_nodes):
            angle = (2 * math.pi * idx) / max(1, len(regular_nodes))
            ring = radius if len(regular_nodes) > 1 else 0
            x = center.x() + math.cos(angle) * ring
            y = center.y() + math.sin(angle) * ring * 0.72
            item = GraphNodeItem(node, x=x, y=y)
            self.scene_obj.addItem(item)
            self._nodes[node.entity_id] = item

        # ── Create container (tree) items ──
        for idx, cnode in enumerate(container_nodes):
            # Position containers in a separate ring further out
            c_angle = (2 * math.pi * idx) / max(1, len(container_nodes)) + math.pi / len(container_nodes)
            c_ring = radius * 1.6 if len(container_nodes) > 1 else 0
            cx = center.x() + math.cos(c_angle) * c_ring
            cy = center.y() + math.sin(c_angle) * c_ring * 0.72
            tree = GraphTreeItem(cnode, x=cx, y=cy)
            self.scene_obj.addItem(tree)
            self._trees[cnode.entity_id] = tree
            # Also register in _nodes so edges can find it
            self._nodes[cnode.entity_id] = tree  # type: ignore[assignment]

            # ── Position child entities inside the container ──
            child_ids = contains_map.get(cnode.entity_id, set())
            # Include both regular nodes AND other containers as children
            all_children = [n for n in (regular_nodes + container_nodes) if n.entity_id in child_ids and n.entity_id != cnode.entity_id]
            # But skip containers that are themselves parents (avoid double placement)
            child_nodes = [n for n in all_children if n.entity_id not in contains_map or n.kind.lower() != "contenedor"]
            container_children = [n for n in all_children if n.kind.lower() == "contenedor"]
            if child_nodes:
                child_radius = max(90, min(200, 60 * len(child_nodes)))
                for ci, child in enumerate(child_nodes):
                    child_item = self._nodes.get(child.entity_id)
                    if child_item is None:
                        continue
                    # Reposition child inside the container
                    ca = (2 * math.pi * ci) / max(1, len(child_nodes))
                    child_x = cx + math.cos(ca) * child_radius
                    child_y = cy + math.sin(ca) * child_radius * 0.7 + _CONTAINER_HEADER_HEIGHT
                    child_item.setPos(child_x, child_y)
                    tree.add_child_node(child_item)  # type: ignore[arg-type]

                # Resize container to fit children
                tree.resize_to_fit_children()

            # Position nested containers inside this parent
            if container_children:
                nested_offset = tree.rect().height() / 2 - 40
                for nci, nc in enumerate(container_children):
                    nc_item = self._trees.get(nc.entity_id) or self._nodes.get(nc.entity_id)
                    if nc_item is None:
                        continue
                    nc_item.setPos(cx + (nci - len(container_children) / 2) * 100, cy + nested_offset)
                    tree.add_child_node(nc_item)  # type: ignore[arg-type]
                if child_nodes:
                    tree.resize_to_fit_children()

        # ── Create edge items ──
        for edge in edges:
            # Skip "contiene" edges — they are rendered by the container visual
            if edge.kind.lower() == "contiene":
                continue
            source = self._nodes.get(edge.source_id)
            target = self._nodes.get(edge.target_id)
            if not source or not target:
                continue
            item = GraphEdgeItem(edge, source, target)
            self.scene_obj.addItem(item)
            self._edges.append(item)
        self.fitInView(self.scene_obj.itemsBoundingRect().adjusted(-140, -140, 140, 140), Qt.AspectRatioMode.KeepAspectRatio)

    def focus_entity(self, entity_id: str):
        item = self._nodes.get(entity_id) or self._trees.get(entity_id)
        if item is None:
            return
        self.centerOn(item)
        item.setSelected(True)


class GraphCanvasWidget(QWidget):
    """B31-T03 graph-first Creation entry."""

    entitySelected = Signal(str)
    relationSelected = Signal(str)
    relationCreateRequested = Signal(str, str)
    graphSelectionChanged = Signal(list, list)
    nodeAssignToTreeRequested = Signal(str, str)

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.ai_controller = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # No header — the graph takes all available space

        self.empty = EmptyState("Grafo narrativo", "Abre un proyecto o crea entidades para ver el lienzo.")
        self.empty.setStyleSheet("background: #F7F1E8;")
        layout.addWidget(self.empty)

        self.canvas = GraphCanvasView()
        self.canvas.entitySelected.connect(self._entity_selected)
        self.canvas.relationSelected.connect(self._relation_selected)
        self.canvas.relationCreateRequested.connect(self.relationCreateRequested.emit)
        self.canvas.graphSelectionChanged.connect(self.graphSelectionChanged.emit)
        self.canvas.nodeAssignToTreeRequested.connect(self.nodeAssignToTreeRequested.emit)
        layout.addWidget(self.canvas, 1)
        self.canvas.setVisible(False)

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def set_ai_controller(self, ai_controller):
        self.ai_controller = ai_controller

    def selected_entity_ids(self) -> list[str]:
        return self.canvas.selected_entity_ids()

    def selected_relation_ids(self) -> list[str]:
        return self.canvas.selected_relation_ids()

    def clear_selection(self):
        self.canvas.clear_selection()

    def run_graph_ai_action(self, action_type: str):
        if self.ai_controller is None:
            return
        project = self._project()
        entity_ids = [getattr(entity, "id", "") for entity in getattr(project, "entities", []) or [] if getattr(entity, "id", "")]
        relation_ids = [getattr(relation, "id", "") for relation in getattr(project, "relations", []) or [] if getattr(relation, "id", "")]
        self.ai_controller.graph_action(action_type, entity_ids=entity_ids, relation_ids=relation_ids)
        self.refresh()

    def _entity_selected(self, entity_id: str):
        self.ctx.selected_entity_id = entity_id
        self.entitySelected.emit(entity_id)
        if self._advanced_mode:
            self.ctx.log("info", f"Nodo seleccionado: {entity_id}")
        else:
            self.ctx.log("info", "Nodo seleccionado")

    def _relation_selected(self, relation_id: str):
        setattr(self.ctx, "selected_relation_id", relation_id)
        self.relationSelected.emit(relation_id)
        if self._advanced_mode:
            self.ctx.log("info", f"Relación seleccionada: {relation_id}")
        else:
            self.ctx.log("info", "Relación seleccionada")

    def _fit_all(self):
        rect = self.canvas.scene_obj.itemsBoundingRect()
        if rect.isValid() and not rect.isEmpty():
            self.canvas.fitInView(rect.adjusted(-140, -140, 140, 140), Qt.AspectRatioMode.KeepAspectRatio)

    def refresh(self):
        project = self._project()
        if project is None:
            self.canvas.clear_graph()
            self.canvas.setVisible(False)
            self.empty.setVisible(True)
            return
        entities = [_entity_view(entity) for entity in (getattr(project, "entities", []) or [])]
        relations = [_relation_view(relation) for relation in (getattr(project, "relations", []) or [])]
        known_entity_ids = {node.entity_id for node in entities}
        proposed_nodes = []
        proposed_edges = []
        for candidate in getattr(project, "candidates", []) or []:
            if not _candidate_is_pending_ai(candidate):
                continue
            edge = _candidate_edge_view(candidate, known_entity_ids)
            if edge is not None:
                proposed_edges.append(edge)
                continue
            node = _candidate_node_view(candidate)
            if node is not None:
                proposed_nodes.append(node)
        entities.extend(proposed_nodes)
        relations.extend(proposed_edges)
        if not entities:
            self.canvas.clear_graph()
            self.canvas.setVisible(False)
            self.empty.setVisible(True)
            return
        self.empty.setVisible(False)
        self.canvas.setVisible(True)
        self.canvas.set_graph(entities, relations)

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
