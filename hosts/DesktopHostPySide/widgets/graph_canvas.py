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
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QTransform
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
    """Visual node item; stores full entity ID internally, never shows it.

    Compact mode: shows name + type + status dot only.
    Brief description is available via tooltip, not rendered inside the node.
    """

    def __init__(self, node: _NodeView, *, x: float, y: float, radius: float = 58.0):
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

        # Name — centred, fitted to node width
        title = QGraphicsSimpleTextItem(_fit_text(node.name, 20), self)
        title.setBrush(QBrush(QColor("#111827")))
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        title.setFont(font)
        title_rect = title.boundingRect()
        title.setPos(-title_rect.width() / 2, -title_rect.height() / 2 - 6)

        # Type — small label below name
        type_label = QGraphicsSimpleTextItem(_fit_text(enum_human(node.kind), 18), self)
        type_label.setBrush(QBrush(QColor("#4B5563")))
        type_label.setFont(QFont("", 7))
        type_rect = type_label.boundingRect()
        type_label.setPos(-type_rect.width() / 2, title_rect.height() / 2 - 4)

        # Status dot (top-left)
        self._status_dot = QGraphicsEllipseItem(-radius + 8, -radius + 8, 10, 10, self)
        self._status_dot.setBrush(QBrush(QColor(_STATUS_COLORS.get(node.canon.lower(), "#A4AEC0"))))
        self._status_dot.setPen(QPen(QColor("#F7F1E8"), 1.0))

        # Visibility dot (top-right)
        visibility_key = node.visibility.lower()
        if visibility_key in _VISIBILITY_COLORS and visibility_key not in {"publico", "publico_mundo"}:
            self._visibility_dot = QGraphicsEllipseItem(radius - 18, -radius + 8, 10, 10, self)
            self._visibility_dot.setBrush(QBrush(QColor(_VISIBILITY_COLORS[visibility_key])))
            self._visibility_dot.setPen(QPen(QColor("#F7F1E8"), 1.0))

        # Tooltip with full info (not rendered inside node)
        tip_parts = [f"<b>{node.name}</b>", f"Tipo: {enum_human(node.kind)}"]
        if node.subtitle:
            tip_parts.append(f"Descripción: {node.subtitle}")
        tip_parts.append(f"Estado: {node.canon}")
        self.setToolTip("<br>".join(tip_parts))

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

    Renders as a rounded rectangle with a **fixed header bar** at the top.
    The header always shows: name, type badge, member count, collapse toggle.
    Brief description is in tooltip only — never in the content area.

    Children (GraphNodeItem / GraphTreeItem) are positioned below the header.
    The container auto-resizes to encompass children with padding.

    Collapse/Expand:
    - Collapsing hides child nodes AND their internal edges.
    - Expanding restores everything and recalculates layout.

    External relations (entity↔tree, tree↔tree narrative) connect to
    the tree's header or border, not the center.
    """

    def __init__(self, node: _NodeView, *, x: float, y: float, width: float = _CONTAINER_MIN_WIDTH, height: float = _CONTAINER_MIN_HEIGHT):
        super().__init__(0, 0, width, height)
        self.node = node
        self._width = width
        self._height = height
        self._coherence_selected = False
        self._collapsed = False
        self._expanded_rect: QRectF | None = None
        self.setPos(x - width / 2, y - height / 2)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(0)

        # ── Z-order hierarchy ──
        # Background: z=0 (this item)
        # Header: z=1
        # Children (nodes/subtrees): z=2+
        # Handles/edges on top: z=10
        self._BASE_Z = 0
        self._HEADER_Z = 1
        self._CHILD_Z = 2
        self._DEPTH = 0  # set during set_graph for nested containers

        # Pens
        self._normal_pen = QPen(QColor("#DCA35F" if node.proposed else "#A4AEC0"), 2.0 if not node.proposed else 2.6)
        if node.proposed:
            self._normal_pen.setStyle(Qt.PenStyle.DashLine)
        self._highlight_pen = QPen(QColor("#EBCB8B"), 3.5)
        self._selected_pen = QPen(QColor("#5B8DEF"), 4.0)

        # Background fill
        bg_color = QColor(_CONTAINER_COLOR)
        bg_color.setAlpha(160)
        self.setBrush(QBrush(bg_color))
        self.setPen(self._normal_pen)

        # ── Header bar (fixed at top of rect) ──
        self._header_item = QGraphicsRectItem(0, 0, width, _CONTAINER_HEADER_HEIGHT, self)
        self._header_item.setZValue(self._HEADER_Z)
        header_bg = QColor(_CONTAINER_HEADER_COLOR)
        header_bg.setAlpha(210)
        self._header_item.setBrush(QBrush(header_bg))
        self._header_item.setPen(QPen(Qt.PenStyle.NoPen))

        # Title in header
        self._title_item = QGraphicsSimpleTextItem(_fit_text(node.name, 26), self)
        self._title_item.setBrush(QBrush(QColor("#2D2A1E")))
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        self._title_item.setFont(title_font)
        self._reposition_title()

        # Type badge in header (right side)
        type_text = _fit_text(enum_human(node.kind), 14)
        self._type_badge = QGraphicsSimpleTextItem(type_text, self)
        self._type_badge.setBrush(QBrush(QColor("#6F6A42")))
        self._type_badge.setFont(QFont("", 7))
        self._reposition_type_badge()

        # Member count (updates dynamically)
        self._count_item = QGraphicsSimpleTextItem("", self)
        self._count_item.setBrush(QBrush(QColor("#5C5A3E")))
        self._count_item.setFont(QFont("", 8))

        # Collapse indicator
        self._collapse_indicator = QGraphicsSimpleTextItem("", self)
        self._collapse_indicator.setBrush(QBrush(QColor("#6F6A42")))
        self._collapse_indicator.setFont(QFont("", 8))
        self._collapse_indicator.setVisible(False)

        # Status dot (top-right of header)
        self._status_dot = QGraphicsEllipseItem(width - 20, 8, 10, 10, self)
        self._status_dot.setBrush(QBrush(QColor(_STATUS_COLORS.get(node.canon.lower(), "#A4AEC0"))))
        self._status_dot.setPen(QPen(QColor("#F7F1E8"), 1.0))

        # Visibility dot
        visibility_key = node.visibility.lower()
        if visibility_key in _VISIBILITY_COLORS and visibility_key not in {"publico", "publico_mundo"}:
            self._visibility_dot = QGraphicsEllipseItem(width - 36, 8, 10, 10, self)
            self._visibility_dot.setBrush(QBrush(QColor(_VISIBILITY_COLORS[visibility_key])))
            self._visibility_dot.setPen(QPen(QColor("#F7F1E8"), 1.0))

        # Track children and internal edges
        self._child_nodes: list[GraphNodeItem | GraphTreeItem] = []
        self._internal_edges: list[GraphEdgeItem] = []

        # Tooltip with full info
        tip_parts = [f"<b>{node.name}</b>", f"Tipo: {enum_human(node.kind)}"]
        if node.subtitle:
            tip_parts.append(f"Descripción: {node.subtitle}")
        tip_parts.append(f"Estado: {node.canon}")
        self.setToolTip("<br>".join(tip_parts))

    # ── Helper repositioning ──

    def _reposition_title(self):
        tr = self._title_item.boundingRect()
        self._title_item.setPos(10, (_CONTAINER_HEADER_HEIGHT - tr.height()) / 2)

    def _reposition_type_badge(self):
        br = self._type_badge.boundingRect()
        self._type_badge.setPos(self._width - br.width() - 46, (_CONTAINER_HEADER_HEIGHT - br.height()) / 2)

    def _reposition_status_dots(self):
        self._status_dot.setRect(self._width - 20, 8, 10, 10)
        if hasattr(self, "_visibility_dot"):
            self._visibility_dot.setRect(self._width - 36, 8, 10, 10)

    def _update_count(self):
        n = len(self._child_nodes)
        label = f"({n})"
        self._count_item.setText(label)
        cr = self._count_item.boundingRect()
        self._count_item.setPos(
            10 + self._title_item.boundingRect().width() + 6,
            (_CONTAINER_HEADER_HEIGHT - cr.height()) / 2,
        )

    # ------------------------------------------------------------------
    # Descendant helpers (transitive)
    # ------------------------------------------------------------------

    def _descendants(self) -> list["GraphNodeItem | GraphTreeItem"]:
        """All descendant nodes transitively (children + grandchildren + ...)."""
        result: list[GraphNodeItem | GraphTreeItem] = []
        stack = list(self._child_nodes)
        while stack:
            item = stack.pop()
            result.append(item)
            if isinstance(item, GraphTreeItem):
                stack.extend(item._child_nodes)
        return result

    def _descendant_tree_ids(self) -> set[str]:
        """Entity IDs of all descendant containers."""
        ids: set[str] = set()
        for d in self._descendants():
            if isinstance(d, GraphTreeItem):
                ids.add(d.node.entity_id)
        return ids

    def _all_descendant_entity_ids(self) -> set[str]:
        """Entity IDs of ALL descendant items (nodes + trees)."""
        return {d.node.entity_id for d in self._descendants()}

    def _descendant_edges(self, all_edges: list) -> list:
        """All edges that involve at least one descendant entity."""
        desc_ids = self._all_descendant_entity_ids()
        result = []
        for edge in all_edges:
            src_id = edge.source.node.entity_id if hasattr(edge.source, "node") else ""
            tgt_id = edge.target.node.entity_id if hasattr(edge.target, "node") else ""
            if src_id in desc_ids or tgt_id in desc_ids:
                result.append(edge)
        return result

    # ------------------------------------------------------------------
    # Collapse / Expand (transitive)
    # ------------------------------------------------------------------

    def toggle_collapse(self):
        if self._collapsed:
            self._expand()
        else:
            self._collapse()

    def _collapse(self):
        """Hide ALL descendants transitively + all their edges, shrink."""
        self._expanded_rect = QRectF(self.rect())
        # 1. Hide all descendants transitively
        for desc in self._descendants():
            desc.setVisible(False)
            # Also collapse any descendant trees so their state is consistent
            if isinstance(desc, GraphTreeItem) and not desc._collapsed:
                desc._collapse_silent()
        # 2. Hide all edges involving any descendant
        if hasattr(self, "_canvas_edges"):
            for edge in self._descendant_edges(self._canvas_edges):
                edge.setVisible(False)
        # 3. Show collapse indicator with total descendant count
        n = len(self._descendants())
        label = f"{n} miembro{'s' if n != 1 else ''}"
        self._collapse_indicator.setText(label)
        self._collapse_indicator.setVisible(True)
        # 4. Shrink to header + indicator
        collapse_h = _CONTAINER_HEADER_HEIGHT + 20
        title_w = self._title_item.boundingRect().width()
        ind_w = self._collapse_indicator.boundingRect().width()
        collapse_w = max(_CONTAINER_MIN_WIDTH, title_w + ind_w + 60)
        self._width = collapse_w
        self._height = collapse_h
        self.setRect(0, 0, collapse_w, collapse_h)
        self._header_item.setRect(0, 0, collapse_w, _CONTAINER_HEADER_HEIGHT)
        self._reposition_title()
        self._reposition_type_badge()
        self._reposition_status_dots()
        self._collapse_indicator.setPos(10, _CONTAINER_HEADER_HEIGHT + 4)
        self._collapsed = True

    def _collapse_silent(self):
        """Mark as collapsed and shrink, but don't recurse (parent handles that)."""
        self._expanded_rect = QRectF(self.rect())
        self._collapsed = True
        n = len(self._descendants())
        label = f"{n} miembro{'s' if n != 1 else ''}"
        self._collapse_indicator.setText(label)
        self._collapse_indicator.setVisible(True)
        collapse_h = _CONTAINER_HEADER_HEIGHT + 20
        collapse_w = max(_CONTAINER_MIN_WIDTH, self._title_item.boundingRect().width() + 60)
        self._width = collapse_w
        self._height = collapse_h
        self.setRect(0, 0, collapse_w, collapse_h)
        self._header_item.setRect(0, 0, collapse_w, _CONTAINER_HEADER_HEIGHT)
        self._reposition_title()
        self._reposition_type_badge()
        self._reposition_status_dots()
        self._collapse_indicator.setPos(10, _CONTAINER_HEADER_HEIGHT + 4)

    def _expand(self):
        """Restore ALL descendants transitively + recalculate layout bottom-up."""
        self._collapsed = False
        self._collapse_indicator.setVisible(False)
        # 1. Expand descendant trees first (bottom-up)
        for child in self._child_nodes:
            if isinstance(child, GraphTreeItem) and child._collapsed:
                child._expand()
        # 2. Show direct children
        for child in self._child_nodes:
            child.setVisible(True)
        # 3. Re-show all descendant edges via global edge visibility pass
        if hasattr(self, "_canvas_edges"):
            self._refresh_edge_visibility()
        # 4. Recalculate size
        if self._child_nodes:
            self.resize_to_fit_children()
        elif self._expanded_rect is not None:
            self._width = self._expanded_rect.width()
            self._height = self._expanded_rect.height()
            self.setRect(self._expanded_rect)
            self._header_item.setRect(0, 0, self._width, _CONTAINER_HEADER_HEIGHT)
            self._reposition_title()
            self._reposition_type_badge()
            self._reposition_status_dots()

    def _refresh_edge_visibility(self):
        """Show/hide all canvas edges based on source+target visibility."""
        if not hasattr(self, "_canvas_edges"):
            return
        for edge in self._canvas_edges:
            src_vis = edge.source.isVisible()
            tgt_vis = edge.target.isVisible()
            edge.setVisible(src_vis and tgt_vis)

    def set_canvas_edges(self, edges: list):
        """Store reference to all canvas edges for visibility management."""
        self._canvas_edges = edges

    def refresh_hierarchical_visibility(self):
        """Central visibility refresh: compute hidden IDs and apply to all items.

        Called after collapse, expand, set_graph, or any structural change.
        Rules:
        - A node/tree is hidden if any ancestor tree is collapsed.
        - An edge is visible only if both source and target are visible.
        """
        if not hasattr(self, "_canvas_edges"):
            return
        # Collect all descendant entity IDs of collapsed trees
        hidden_ids: set[str] = set()
        # Walk all trees in the scene to find collapsed ones
        # (this works for any tree, not just self)
        pass  # visibility is managed per-tree in _collapse/_expand/_refresh_edge_visibility

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    # ------------------------------------------------------------------
    # Child / Edge management
    # ------------------------------------------------------------------

    def add_child_node(self, child):
        """Register a child item (GraphNodeItem or GraphTreeItem).

        Makes the child a Qt child (setParentItem) so it paints above
        the container background and participates in scene hit testing
        with correct z-ordering.
        """
        self._child_nodes.append(child)
        # Make child a Qt child of this container for z-ordering
        child.setParentItem(self)
        # Position relative to parent's local coordinates
        child.setZValue(self._CHILD_Z + child._DEPTH if isinstance(child, GraphTreeItem) else self._CHILD_Z)
        self._update_count()

    def child_node_count(self) -> int:
        return len(self._child_nodes)

    def register_internal_edge(self, edge):
        """Register an edge between two children of this container."""
        self._internal_edges.append(edge)

    def find_internal_edges(self, all_edges: list):
        """Scan all_edges and register those whose source+target are both children."""
        child_ids = set()
        for child in self._child_nodes:
            child_ids.add(child.node.entity_id)
        # Also include this tree's own ID (entity inside tree → tree itself)
        child_ids.add(self.node.entity_id)
        self._internal_edges = []
        for edge in all_edges:
            src_id = edge.source.node.entity_id if hasattr(edge.source, "node") else ""
            tgt_id = edge.target.node.entity_id if hasattr(edge.target, "node") else ""
            if src_id in child_ids and tgt_id in child_ids:
                self._internal_edges.append(edge)

    def resize_to_fit_children(self):
        """Expand the rectangle so all children fit below the header with padding.

        Uses boundingRect() for sub-trees (which accounts for their own children)
        and radius for regular nodes.  Works correctly for nested containers.

        Since children are Qt children (parentItem=self), child.pos() is already
        in local coordinates — no need to subtract self.pos().
        """
        if not self._child_nodes:
            return
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for child in self._child_nodes:
            if not child.isVisible():
                continue
            # child.pos() is already in parent-local coords (Qt child)
            cx = child.pos().x()
            cy = child.pos().y()
            if isinstance(child, GraphTreeItem):
                # Use the tree's actual bounding rect (includes its children)
                br = child.boundingRect()
                min_x = min(min_x, cx + br.left() - 8)
                min_y = min(min_y, cy + br.top() - 8)
                max_x = max(max_x, cx + br.right() + 8)
                max_y = max(max_y, cy + br.bottom() + 8)
            else:
                cr = getattr(child, "radius", 58.0)
                min_x = min(min_x, cx - cr - 8)
                min_y = min(min_y, cy - cr - 8)
                max_x = max(max_x, cx + cr + 8)
                max_y = max(max_y, cy + cr + 8)
        # Ensure header is above all children
        min_y = min(min_y, 0)
        min_x = min(min_x, 0)
        # Add padding
        min_x -= _CONTAINER_PADDING
        min_y -= _CONTAINER_PADDING
        max_x += _CONTAINER_PADDING
        max_y += _CONTAINER_PADDING
        # Ensure header height at top
        min_y = min(min_y, -_CONTAINER_HEADER_HEIGHT - 8)
        w = max(_CONTAINER_MIN_WIDTH, max_x - min_x)
        h = max(_CONTAINER_MIN_HEIGHT, max_y - min_y)
        self._width = w
        self._height = h
        self.setRect(min_x, min_y, w, h)
        self._header_item.setRect(min_x, min_y, w, _CONTAINER_HEADER_HEIGHT)
        self._title_item.setPos(min_x + 10, min_y + (_CONTAINER_HEADER_HEIGHT - self._title_item.boundingRect().height()) / 2)
        self._type_badge.setPos(
            min_x + w - self._type_badge.boundingRect().width() - 46,
            min_y + (_CONTAINER_HEADER_HEIGHT - self._type_badge.boundingRect().height()) / 2,
        )
        self._status_dot.setRect(min_x + w - 20, min_y + 8, 10, 10)
        if hasattr(self, "_visibility_dot"):
            self._visibility_dot.setRect(min_x + w - 36, min_y + 8, 10, 10)
        self._count_item.setPos(
            min_x + 10 + self._title_item.boundingRect().width() + 6,
            min_y + (_CONTAINER_HEADER_HEIGHT - self._count_item.boundingRect().height()) / 2,
        )

    @property
    def radius(self) -> float:
        """Effective 'radius' for edge shortening — distance from center to top of header."""
        return min(self._width, self._height) / 2

    def connection_point(self, from_pos: QPointF) -> QPointF:
        """Return the best point on the header border for an external relation edge.

        This avoids edges going to the center of the container where children are.
        """
        center = self.scenePos() + QPointF(self._width / 2, self._height / 2)
        # Prefer connecting to the header area (top portion)
        header_center = self.scenePos() + QPointF(self._width / 2, self.rect().top() + _CONTAINER_HEADER_HEIGHT / 2)
        return header_center

    def set_drag_highlight(self, enabled: bool):
        if self._coherence_selected and not enabled:
            self.setPen(self._selected_pen)
            return
        self.setPen(self._highlight_pen if enabled else self._normal_pen)

    def set_coherence_selected(self, enabled: bool):
        self._coherence_selected = bool(enabled)
        self.setPen(self._selected_pen if enabled else self._normal_pen)

    def mouseDoubleClickEvent(self, event):
        local_pos = event.pos()
        header_bottom = self.rect().top() + _CONTAINER_HEADER_HEIGHT
        if local_pos.y() <= header_bottom:
            self.toggle_collapse()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def shape(self) -> QPainterPath:
        """Hit testing: only the header bar and border are interactive.

        The content area passes through to children.  This prevents the
        container from eating clicks meant for its children.
        """
        path = QPainterPath()
        r = self.rect()
        h = _CONTAINER_HEADER_HEIGHT
        border = 10.0  # border width for edge click area

        # Header bar
        path.addRect(QRectF(r.left(), r.top(), r.width(), h))

        # Left border strip
        path.addRect(QRectF(r.left(), r.top(), border, r.height()))
        # Right border strip
        path.addRect(QRectF(r.right() - border, r.top(), border, r.height()))
        # Bottom border strip
        path.addRect(QRectF(r.left(), r.bottom() - border, r.width(), border))

        return path

    def mousePressEvent(self, event):
        """Only accept press if it's on header/border; pass through to children otherwise."""
        local_pos = event.pos()
        header_bottom = self.rect().top() + _CONTAINER_HEADER_HEIGHT

        # Check if click is in header area
        if local_pos.y() <= header_bottom:
            super().mousePressEvent(event)
            return

        # Check if click is in border area (within 10px of edge)
        r = self.rect()
        in_left = local_pos.x() <= r.left() + 10
        in_right = local_pos.x() >= r.right() - 10
        in_bottom = local_pos.y() >= r.bottom() - 10

        if in_left or in_right or in_bottom:
            super().mousePressEvent(event)
            return

        # Click is in content area — check if a child item is under cursor
        scene_pos = self.mapToScene(local_pos)
        child_at = self.scene().itemAt(scene_pos, self.scene().views()[0].transform() if self.scene().views() else QTransform())
        if child_at and child_at != self and child_at is not None:
            # Don't accept — let the child handle it
            event.ignore()
            return

        # No child under cursor — select the container itself
        super().mousePressEvent(event)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawRoundedRect(self.rect(), 12.0, 12.0)

    def itemChange(self, change, value):
        # Children are Qt children (parentItem=self) so they move automatically.
        # No manual delta propagation needed.
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
        self.setZValue(100)  # Always above containers and nodes

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
        # For containers, use connection_point (header) instead of center
        if isinstance(self.source, GraphTreeItem) and hasattr(self.source, "connection_point"):
            start = self.source.connection_point(self.target.scenePos())
        else:
            start = self.source.scenePos()
        if isinstance(self.target, GraphTreeItem) and hasattr(self.target, "connection_point"):
            end = self.target.connection_point(start)
        else:
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
    relationCreateRejected = Signal(str)

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
        self._drag_line: QGraphicsPathItem | None = None
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
        self._clear_selection_impl(emit=emit)

    def refresh_all_visibility(self):
        """Central visibility refresh for all edges based on source/target visibility.

        Called after collapse, expand, or any structural change.
        Rule: an edge is visible only if both source and target are visible.
        """
        for edge in self._edges:
            src_vis = edge.source.isVisible()
            tgt_vis = edge.target.isVisible()
            edge.setVisible(src_vis and tgt_vis)

    def _clear_selection_impl(self, *, emit: bool = True):
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
            if target is not None:
                if target is source:
                    self.relationCreateRejected.emit("No se puede crear una relación sobre la misma entidad")
                else:
                    self.relationCreateRequested.emit(source.node.entity_id, target.node.entity_id)
            else:
                self.relationCreateRejected.emit("Relación cancelada")
            event.accept()
            return
        self._pending_source = None
        self._alt_source = None
        super().mouseReleaseEvent(event)

    def _start_relation_drag(self, source: GraphNodeItem | GraphTreeItem):
        self._drag_source = source
        self._drag_target = None
        line = QGraphicsPathItem()
        pen = QPen(QColor("#D08770"), 2.5, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line.setPen(pen)
        line.setZValue(3)
        line.setToolTip("Flecha provisional de relación")
        self._drag_line = line
        self.scene_obj.addItem(line)
        source.set_drag_highlight(True)

    def _update_relation_drag(self, scene_pos: QPointF, target: GraphNodeItem | GraphTreeItem | None):
        if self._drag_source is None or self._drag_line is None:
            return
        start = self._drag_source.scenePos()
        self._drag_line.setPath(self._relation_drag_arrow_path(start, scene_pos))
        if target is self._drag_source:
            target = None
        if target is not self._drag_target:
            if self._drag_target is not None:
                self._drag_target.set_drag_highlight(False)
            self._drag_target = target
            if self._drag_target is not None:
                self._drag_target.set_drag_highlight(True)

    def _relation_drag_arrow_path(self, start: QPointF, end: QPointF) -> QPainterPath:
        path = QPainterPath(start)
        path.lineTo(end)
        line = QLineF(start, end)
        if line.length() > 4:
            angle = math.atan2(-(end.y() - start.y()), end.x() - start.x())
            arrow_size = 16
            p1 = QPointF(
                end.x() - arrow_size * math.cos(angle - math.pi / 6),
                end.y() + arrow_size * math.sin(angle - math.pi / 6),
            )
            p2 = QPointF(
                end.x() - arrow_size * math.cos(angle + math.pi / 6),
                end.y() + arrow_size * math.sin(angle + math.pi / 6),
            )
            path.moveTo(end)
            path.lineTo(p1)
            path.moveTo(end)
            path.lineTo(p2)
        return path

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

    def _start_alt_drag(self, source: GraphNodeItem | GraphTreeItem):
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
        # Visual feedback: red line if would create cycle
        if target is not None and self._alt_source is not None:
            src_id = self._alt_source.node.entity_id
            tgt_id = target.node.entity_id
            if self.would_create_cycle(src_id, tgt_id):
                self._alt_line.setPen(QPen(QColor("#D94040"), 2.5, Qt.PenStyle.DashDotLine))
            else:
                self._alt_line.setPen(QPen(QColor("#5B8DEF"), 2.5, Qt.PenStyle.DashDotLine))

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

        # ── Build membership index for cycle detection ──
        self._membership = {}
        for edge in edges:
            if edge.kind.lower() == "contiene":
                self._membership[edge.target_id] = edge.source_id

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
        # Build dependency graph for bottom-up layout
        container_child_map: dict[str, list[str]] = {}  # parent_id -> [child_container_ids]
        for idx, cnode in enumerate(container_nodes):
            child_ids = contains_map.get(cnode.entity_id, set())
            c_children = [n.entity_id for n in container_nodes
                          if n.entity_id in child_ids and n.entity_id != cnode.entity_id]
            container_child_map[cnode.entity_id] = c_children

        # Topological sort: leaves first, parents later
        sorted_container_ids: list[str] = []
        visited: set[str] = set()
        def _visit(cid: str):
            if cid in visited:
                return
            visited.add(cid)
            for child_cid in container_child_map.get(cid, []):
                _visit(child_cid)
            sorted_container_ids.append(cid)
        for cn in container_nodes:
            _visit(cn.entity_id)
        # sorted_container_ids is now leaves-first

        # Calculate depth for each container (for z-ordering)
        container_depth: dict[str, int] = {}
        for cid in sorted_container_ids:
            child_cids = container_child_map.get(cid, [])
            if child_cids:
                container_depth[cid] = max(container_depth.get(c, 0) for c in child_cids) + 1
            else:
                container_depth[cid] = 0

        # Position containers in outer ring
        for idx, cnode in enumerate(container_nodes):
            c_angle = (2 * math.pi * idx) / max(1, len(container_nodes)) + math.pi / len(container_nodes)
            c_ring = radius * 1.6 if len(container_nodes) > 1 else 0
            cx = center.x() + math.cos(c_angle) * c_ring
            cy = center.y() + math.sin(c_angle) * c_ring * 0.72
            tree = GraphTreeItem(cnode, x=cx, y=cy)
            tree._DEPTH = container_depth.get(cnode.entity_id, 0)
            tree.setZValue(-10 + tree._DEPTH)  # deeper containers paint first (lower z)
            self.scene_obj.addItem(tree)
            self._trees[cnode.entity_id] = tree
            self._nodes[cnode.entity_id] = tree  # type: ignore[assignment]

        # Populate children bottom-up (leaves first)
        for cnode_id in sorted_container_ids:
            tree = self._trees.get(cnode_id)
            if tree is None:
                continue
            cnode = next((n for n in container_nodes if n.entity_id == cnode_id), None)
            if cnode is None:
                continue
            child_ids = contains_map.get(cnode_id, set())
            all_children = [n for n in (regular_nodes + container_nodes)
                            if n.entity_id in child_ids and n.entity_id != cnode_id]
            child_nodes = [n for n in all_children if n.kind.lower() != "contenedor"]
            container_children = [n for n in all_children if n.kind.lower() == "contenedor"]

            # Get tree center position
            tree_cx = tree._width / 2
            tree_cy = tree._height / 2

            # Layout regular children below header (in parent-local coords)
            child_radius = 70.0
            if child_nodes:
                child_radius = max(70, min(160, 50 * len(child_nodes)))
                for ci, child in enumerate(child_nodes):
                    child_item = self._nodes.get(child.entity_id)
                    if child_item is None:
                        continue
                    n_children = max(1, len(child_nodes))
                    if n_children == 1:
                        child_x = tree_cx
                        child_y = tree_cy + _CONTAINER_HEADER_HEIGHT + 60
                    else:
                        ca = (2 * math.pi * ci) / n_children
                        child_x = tree_cx + math.cos(ca) * child_radius
                        child_y = tree_cy + _CONTAINER_HEADER_HEIGHT + 60 + math.sin(ca) * child_radius * 0.5
                    # setPos before add_child_node because add_child_node changes parent
                    child_item.setPos(child_x, child_y)
                    tree.add_child_node(child_item)  # type: ignore[arg-type]

            # Layout nested containers below regular children (in parent-local coords)
            if container_children:
                nested_y_offset = _CONTAINER_HEADER_HEIGHT + 60 + (child_radius * 2 + 40 if child_nodes else 0)
                for nci, nc in enumerate(container_children):
                    nc_item = self._trees.get(nc.entity_id) or self._nodes.get(nc.entity_id)
                    if nc_item is None:
                        continue
                    spread = max(1, len(container_children))
                    nc_w = nc_item._width if isinstance(nc_item, GraphTreeItem) else _CONTAINER_MIN_WIDTH
                    nc_x = tree_cx + (nci - (spread - 1) / 2) * (nc_w + 30)
                    nc_y = tree_cy + nested_y_offset
                    # Convert from parent-scene to parent-local coords
                    # The child is currently at scene position from outer ring layout.
                    # We need to compute the local offset.
                    nc_item.setPos(nc_x, nc_y)
                    tree.add_child_node(nc_item)  # type: ignore[arg-type]

            # Resize container to fit all children (bottom-up: children already laid out)
            if tree._child_nodes:
                tree.resize_to_fit_children()

        # ── Create edge items ──
        seen_edge_ids: set[str] = set()
        for edge in edges:
            edge_id = getattr(edge, "relation_id", "")
            if edge_id and edge_id in seen_edge_ids:
                continue
            if edge_id:
                seen_edge_ids.add(edge_id)
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

        # ── Register internal edges for each container ──
        for tree in self._trees.values():
            tree.find_internal_edges(self._edges)

        # ── Pass canvas edges to all root-level trees for collapse visibility ──
        for tree in self._trees.values():
            tree.set_canvas_edges(self._edges)

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
    relationCreateRejected = Signal(str)

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
        self.canvas.relationCreateRejected.connect(self.relationCreateRejected.emit)
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
        entities = []
        seen_entity_ids: set[str] = set()
        for entity in (getattr(project, "entities", []) or []):
            entity_id = getattr(entity, "id", "")
            if not entity_id or entity_id in seen_entity_ids:
                continue
            seen_entity_ids.add(entity_id)
            entities.append(_entity_view(entity))
        relations = []
        seen_relation_ids: set[str] = set()
        for relation in (getattr(project, "relations", []) or []):
            relation_id = getattr(relation, "id", "")
            if not relation_id or relation_id in seen_relation_ids:
                continue
            seen_relation_ids.add(relation_id)
            relations.append(_relation_view(relation))
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
