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
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.design_system import EmptyState, SectionHeader, enum_human


_NODE_COLORS = {
    "personaje": "#7C9BFF",
    "lugar": "#7EC8A5",
    "organizacion": "#DCA35F",
    "faccion": "#D9908F",
    "objeto": "#C9A5FF",
    "evento": "#E0C46C",
    "concepto": "#9BB4C7",
}

_EDGE_COLORS = {
    "es_aliado_de": "#78B891",
    "es_enemigo_de": "#D46A6A",
    "pertenece_a": "#7C9BFF",
    "esta_en": "#7EC8A5",
    "esta_relacionado_con": "#A4AEC0",
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
    return _EdgeView(
        relation=relation,
        relation_id=str(getattr(relation, "id", "")),
        source_id=str(getattr(relation, "source_id", "")),
        target_id=str(getattr(relation, "target_id", "")),
        kind=kind,
        label=label,
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
        self.setPen(self._highlight_pen if enabled else self._normal_pen)

    def itemChange(self, change, value):
        return super().itemChange(change, value)


class GraphEdgeItem(QGraphicsPathItem):
    """Selectable relation edge derived from a domain relation."""

    def __init__(self, edge: _EdgeView, source: GraphNodeItem, target: GraphNodeItem):
        super().__init__()
        self.edge = edge
        self.source = source
        self.target = target
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)
        color = QColor("#DCA35F" if edge.proposed else _EDGE_COLORS.get(edge.kind.lower(), "#A4AEC0"))
        self._normal_pen = QPen(color, 2.6 if edge.proposed else 2.2)
        if edge.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self._normal_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._selected_pen = QPen(color.lighter(135), 4.0)
        self._selected_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(self._normal_pen)
        self.label_item = QGraphicsSimpleTextItem(_fit_text(edge.label, 28), self)
        self.label_item.setBrush(QBrush(QColor("#6B7280")))
        self.label_item.setScale(0.86)
        self.handle_item = QGraphicsEllipseItem(-5, -5, 10, 10, self)
        self.handle_item.setBrush(QBrush(QColor("#D08770")))
        self.handle_item.setPen(QPen(QColor("#F7F1E8"), 1.2))
        self.handle_item.setToolTip("Abrir relación")
        self.update_path()

    def update_path(self):
        start = self.source.scenePos()
        end = self.target.scenePos()
        path = QPainterPath(start)
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        ctrl_offset = QPointF(-dy * 0.12, dx * 0.12)
        c1 = QPointF(start.x() + dx * 0.45 + ctrl_offset.x(), start.y() + dy * 0.45 + ctrl_offset.y())
        c2 = QPointF(start.x() + dx * 0.55 + ctrl_offset.x(), start.y() + dy * 0.55 + ctrl_offset.y())
        path.cubicTo(c1, c2, end)
        self.setPath(path)
        mid = path.pointAtPercent(0.5)
        rect = self.label_item.boundingRect()
        self.label_item.setPos(mid.x() - rect.width() * 0.43, mid.y() - 18)
        self.handle_item.setPos(mid.x(), mid.y())

    def mousePressEvent(self, event):
        self.setPen(self._selected_pen)
        super().mousePressEvent(event)


class GraphCanvasView(QGraphicsView):
    """Interactive view: pan/zoom with selectable nodes and edges."""

    entitySelected = Signal(str)
    relationSelected = Signal(str)
    relationCreateRequested = Signal(str, str)

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
        self._edges: list[GraphEdgeItem] = []
        self._pending_source: GraphNodeItem | None = None
        self._drag_source: GraphNodeItem | None = None
        self._drag_target: GraphNodeItem | None = None
        self._drag_origin_view_pos = QPointF()
        self._drag_line: QGraphicsLineItem | None = None

    def wheelEvent(self, event):
        factor = 1.12 if event.angleDelta().y() > 0 else 1 / 1.12
        self.scale(factor, factor)

    def _item_node_at(self, view_pos) -> GraphNodeItem | None:
        item = self.itemAt(view_pos.toPoint())
        while item is not None:
            if isinstance(item, GraphNodeItem):
                return item
            item = item.parentItem()
        return None

    def _item_edge_at(self, view_pos) -> GraphEdgeItem | None:
        item = self.itemAt(view_pos.toPoint())
        while item is not None:
            if isinstance(item, GraphEdgeItem):
                return item
            item = item.parentItem()
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            node = self._item_node_at(event.position())
            if node is not None:
                self._pending_source = node
                self._drag_origin_view_pos = event.position()
                self.entitySelected.emit(node.node.entity_id)
                event.accept()
                return
            edge = self._item_edge_at(event.position())
            if edge is not None:
                self.relationSelected.emit(edge.edge.relation_id)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
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
        if self._drag_source is not None:
            source = self._drag_source
            target = self._item_node_at(event.position())
            self._finish_relation_drag(target)
            if target is not None and target is not source:
                self.relationCreateRequested.emit(source.node.entity_id, target.node.entity_id)
            event.accept()
            return
        self._pending_source = None
        super().mouseReleaseEvent(event)

    def _start_relation_drag(self, source: GraphNodeItem):
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

    def _update_relation_drag(self, scene_pos: QPointF, target: GraphNodeItem | None):
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

    def _finish_relation_drag(self, target: GraphNodeItem | None):
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

    def clear_graph(self):
        self.scene_obj.clear()
        self._nodes.clear()
        self._edges.clear()

    def set_graph(self, nodes: list[_NodeView], edges: list[_EdgeView]):
        self.clear_graph()
        if not nodes:
            return
        radius = max(220, min(620, 80 * len(nodes)))
        center = QPointF(0, 0)
        for idx, node in enumerate(nodes):
            angle = (2 * math.pi * idx) / max(1, len(nodes))
            ring = radius if len(nodes) > 1 else 0
            x = center.x() + math.cos(angle) * ring
            y = center.y() + math.sin(angle) * ring * 0.72
            item = GraphNodeItem(node, x=x, y=y)
            self.scene_obj.addItem(item)
            self._nodes[node.entity_id] = item

        for edge in edges:
            source = self._nodes.get(edge.source_id)
            target = self._nodes.get(edge.target_id)
            if not source or not target:
                continue
            item = GraphEdgeItem(edge, source, target)
            self.scene_obj.addItem(item)
            self._edges.append(item)
        self.fitInView(self.scene_obj.itemsBoundingRect().adjusted(-140, -140, 140, 140), Qt.AspectRatioMode.KeepAspectRatio)

    def focus_entity(self, entity_id: str):
        item = self._nodes.get(entity_id)
        if item is None:
            return
        self.centerOn(item)
        item.setSelected(True)


class GraphCanvasWidget(QWidget):
    """B31-T03 graph-first Creation entry."""

    entitySelected = Signal(str)
    relationSelected = Signal(str)
    relationCreateRequested = Signal(str, str)

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

        header = QWidget()
        header.setObjectName("cardSurface")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 18, 12)
        header_layout.setSpacing(10)
        self.title = SectionHeader(
            "Grafo narrativo",
            "Explora entidades y relaciones. Arrastra un nodo sobre otro para proponer una relación."
        )
        header_layout.addWidget(self.title, 1)
        self.stats = QLabel("Sin proyecto")
        self.stats.setObjectName("mutedLabel")
        header_layout.addWidget(self.stats)
        self.ai_status = QLabel("IA: candidatos revisables")
        self.ai_status.setObjectName("mutedLabel")
        header_layout.addWidget(self.ai_status)
        self.btn_ai_nodes = QPushButton("IA nodos faltantes")
        self.btn_ai_nodes.clicked.connect(lambda: self.run_graph_ai_action("suggest_missing_nodes"))
        header_layout.addWidget(self.btn_ai_nodes)
        self.btn_ai_relations = QPushButton("IA relaciones")
        self.btn_ai_relations.clicked.connect(lambda: self.run_graph_ai_action("suggest_missing_relations"))
        header_layout.addWidget(self.btn_ai_relations)
        self.btn_fit = QPushButton("Enfocar todo")
        self.btn_fit.clicked.connect(self._fit_all)
        header_layout.addWidget(self.btn_fit)
        layout.addWidget(header)

        self.empty = EmptyState("Grafo narrativo", "Abre un proyecto o crea entidades para ver el lienzo.")
        layout.addWidget(self.empty)

        self.canvas = GraphCanvasView()
        self.canvas.entitySelected.connect(self._entity_selected)
        self.canvas.relationSelected.connect(self._relation_selected)
        self.canvas.relationCreateRequested.connect(self.relationCreateRequested.emit)
        layout.addWidget(self.canvas, 1)
        self.canvas.setVisible(False)

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def set_ai_controller(self, ai_controller):
        self.ai_controller = ai_controller
        available = ai_controller is not None
        self.btn_ai_nodes.setEnabled(available)
        self.btn_ai_relations.setEnabled(available)
        if not available:
            self.ai_status.setText("IA contextual no disponible")

    def run_graph_ai_action(self, action_type: str):
        if self.ai_controller is None:
            self.ai_status.setText("IA contextual no disponible")
            return
        project = self._project()
        entity_ids = [getattr(entity, "id", "") for entity in getattr(project, "entities", []) or [] if getattr(entity, "id", "")]
        relation_ids = [getattr(relation, "id", "") for relation in getattr(project, "relations", []) or [] if getattr(relation, "id", "")]
        self.btn_ai_nodes.setEnabled(False)
        self.btn_ai_relations.setEnabled(False)
        self.ai_status.setText("IA grafo…")
        result = self.ai_controller.graph_action(action_type, entity_ids=entity_ids, relation_ids=relation_ids)
        self.ai_status.setText(self.ai_controller.result_summary(result))
        self.btn_ai_nodes.setEnabled(True)
        self.btn_ai_relations.setEnabled(True)
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
            self.stats.setText("Sin proyecto")
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
            self.stats.setText("0 nodos · 0 relaciones")
            return
        self.empty.setVisible(False)
        self.canvas.setVisible(True)
        self.canvas.set_graph(entities, relations)
        suffix = ""
        if proposed_nodes or proposed_edges:
            suffix = f" · IA {len(proposed_nodes)} nodos/{len(proposed_edges)} relaciones"
        self.stats.setText(f"{len(entities) - len(proposed_nodes)} nodos · {len(relations) - len(proposed_edges)} relaciones{suffix}")

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
