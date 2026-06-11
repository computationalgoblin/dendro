"""Graph canvas for B31-T03/B31-T06.

Visual graph derived from the active project. The graph is a view over existing
entities and relations; relation creation is emitted as an intent and executed
outside the canvas through application services.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QStyle,
    QStyleOptionGraphicsItem,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.design_system import EmptyState, enum_human
from packages.application.world_layer_causal import get_causal_rank, sort_layers_by_causal_rank
from packages.domain.world_layer import default_world_layers


def _b44trace(message: str):
    """Temporary B44 diagnostic trace; remove after Windows repro is diagnosed."""
    print(f"B44TRACE {message}", flush=True)


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
    "deriva_de": "#8B5CF6",
    "condiciona": "#7C3AED",
    "explica": "#6D28D9",
    "contradice": "#D46A6A",
    "produce_consecuencia_en": "#A855F7",
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
    layer_id: str = ""
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
    inter_ring: bool = False
    causal: bool = False


@dataclass(frozen=True)
class _RingVisual:
    """Calculated B44 concentric ring state. Ephemeral UI data, never canon."""

    ring_id: str
    display_name: str
    causal_rank: int | None
    color: str
    inner_radius: float
    outer_radius: float
    item_ids: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    count_label: str = ""
    state: str = "normal"  # normal | focused | hidden


@dataclass(frozen=True)
class VisualFilterState:
    """Ephemeral B37 visual filters. Never persisted and never mutates canon."""

    entity_types: tuple[str, ...] = ()
    relation_types: tuple[str, ...] = ()
    relation_families: tuple[str, ...] = ()
    tree_id: str = ""
    layer_ids: tuple[str, ...] = ()
    focus_entity_ids: tuple[str, ...] = ()
    canon_states: tuple[str, ...] = ()
    visibility_states: tuple[str, ...] = ()
    show_relations: bool = True

    def is_active(self) -> bool:
        return bool(
            self.entity_types
            or self.relation_types
            or self.relation_families
            or self.tree_id
            or self.layer_ids
            or self.focus_entity_ids
            or self.canon_states
            or self.visibility_states
            or not self.show_relations
        )


@dataclass(frozen=True)
class GraphSearchResult:
    """Clean search result for Creación. IDs stay internal and are not display text."""

    item_id: str
    item_kind: str  # entity | tree | relation
    title: str
    type_label: str
    category: str
    summary: str = ""
    parent_tree_name: str = ""
    parent_tree_id: str = ""
    is_inside_collapsed_tree: bool = False

    def display_lines(self) -> tuple[str, str, str]:
        where = f"Dentro de {self.parent_tree_name}" if self.parent_tree_name else self.category
        details = " · ".join(part for part in [self.type_label, where] if part)
        return (self.title, details, self.summary)


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
        layer_id=str((getattr(entity, "layer_ids", []) or [""])[0] or ""),
    )


def _relation_view(relation: Any) -> _EdgeView:
    kind = _enum_value(getattr(relation, "relation_type", None), "relación")
    label = enum_human(kind)
    direction = _enum_value(getattr(relation, "direction", None), "unidireccional")
    meta = dict(getattr(relation, "custom_metadata", {}) or {})
    color = meta.get("_edge_color", "") or _EDGE_COLORS.get(kind.lower(), "")
    return _EdgeView(
        relation=relation,
        relation_id=str(getattr(relation, "id", "")),
        source_id=str(getattr(relation, "source_id", "")),
        target_id=str(getattr(relation, "target_id", "")),
        kind=kind,
        label=label,
        direction=direction,
        color=color,
        causal=relation_family(kind) == "causal",
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
        layer_id=str(data.get("layer_id") or ((data.get("layer_ids") or [""])[0] if isinstance(data.get("layer_ids"), list) else "")),
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
        # BETA1-B03: edges must follow items. Scene-position notifications
        # also fire when an ANCESTOR moves, so nested children keep their
        # relations attached while their tree is dragged.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self._connected_edges: list = []
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
        # BETA1-B03: keep relations attached while the node moves (own move
        # or an ancestor tree dragging it along).
        if change in (
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged,
        ):
            for edge in getattr(self, "_connected_edges", ()):  # noqa: B007
                edge.update_path()
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
        # BETA1-B03: see GraphNodeItem — edges follow trees too, including
        # nested trees dragged along by an ancestor.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self._connected_edges: list = []
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
        # BETA1-B03: a nested collapse/expand changes this tree's size, so
        # every ancestor container must refit around it (bottom-up).
        ancestor = self.parentItem()
        while isinstance(ancestor, GraphTreeItem):
            if ancestor._child_nodes:
                ancestor.resize_to_fit_children()
            ancestor = ancestor.parentItem()
        # BETA1-B03: rings react to content size changes. Children keep
        # their own positions (hidden on collapse, restored on expand);
        # only ring radii and top-level slots are recomputed.
        scene = self.scene()
        if scene is not None:
            for view in scene.views():
                if isinstance(view, GraphCanvasView):
                    view._relayout_concentric()
                    break

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
        # Hide member count badge (collapse indicator shows the count instead)
        self._count_item.setVisible(False)
        self._collapsed = True
        self._update_attached_edges()  # BETA1-B03: no floating edges

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
        # Restore member count badge
        self._count_item.setVisible(True)
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
        self._update_attached_edges()  # BETA1-B03: no floating edges

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
        # BETA1-B03: the rect changed → connection points moved. Recalculate
        # attached relations so none is left floating.
        self._update_attached_edges()

    def _update_attached_edges(self):
        """BETA1-B03: refresh geometry of every relation touching this tree
        or its content (rect/size changes don't fire itemChange)."""
        for edge in getattr(self, "_connected_edges", ()):  # noqa: B007
            edge.update_path()
        for edge in getattr(self, "_internal_edges", ()):  # noqa: B007
            edge.update_path()

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
        """Hit testing: full rect always. Children have higher z-order so they
        get priority in _item_node_at when expanded and a child is under cursor."""
        path = QPainterPath()
        path.addRect(self.rect())
        return path

    def mousePressEvent(self, event):
        """Handle clicks: select the container and propagate to canvas view."""
        # Always propagate to the view so it can handle selection + entitySelected
        # regardless of where in the container the click lands.
        super().mousePressEvent(event)

    def _notify_canvas_selected(self):
        """Propagate selection to the GraphCanvasView so entitySelected fires."""
        views = self.scene().views() if self.scene() else []
        for view in views:
            if isinstance(view, GraphCanvasView):
                view.entitySelected.emit(self.node.entity_id)
                view._set_single_node_selection(self)
                break

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
        # BETA1-B03: keep this tree's relations attached while it moves
        if change in (
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
            QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged,
        ):
            for edge in getattr(self, "_connected_edges", ()):  # noqa: B007
                edge.update_path()
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
        # BETA1-B03: register on both endpoints so their itemChange keeps
        # this edge's geometry in sync while they move.
        for endpoint in (source, target):
            registry = getattr(endpoint, "_connected_edges", None)
            if registry is not None and self not in registry:
                registry.append(self)
        self._is_bidirectional = edge.direction == "bidireccional"
        self._coherence_selected = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(100)  # Always above containers and nodes

        # Resolve colour: stored colour > type colour > default
        base_color = edge.color or _EDGE_COLORS.get(edge.kind.lower(), "#A4AEC0")
        color = QColor("#DCA35F" if edge.proposed else base_color)

        self._normal_pen = QPen(color, 2.6 if edge.proposed else 2.2)
        if edge.inter_ring:
            self._normal_pen.setStyle(Qt.PenStyle.DashDotLine if edge.causal else Qt.PenStyle.DotLine)
            self._normal_pen.setWidthF(3.0 if edge.causal else 2.4)
        elif edge.proposed:
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


class GraphRingItem(QGraphicsPathItem):
    """B44 selectable ring background. Empty-area clicks select the ring.

    Nodes, tree containers and relation handles have higher z-order, so this
    item only wins hit testing in empty corona areas.
    """

    def __init__(self, ring: _RingVisual, path: QPainterPath):
        super().__init__(path)
        self.ring = ring
        self._base_pen: QPen | None = None
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Anillo: {ring.display_name}\n{ring.count_label}\nDoble click: entrar en anillo")
        self.setZValue(-100)

    def paint(self, painter: QPainter, option, widget=None):
        # BETA1-B02: suppress Qt's default selection marquee (a dashed
        # bounding RECTANGLE around the whole ring). Selection feedback is the
        # highlighted ring outline applied in itemChange instead.
        clean = QStyleOptionGraphicsItem(option)
        clean.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, clean, widget)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if self._base_pen is None:
                self._base_pen = QPen(self.pen())
            if value:
                selected = QPen(QColor("#5B8DEF"), 3.4, Qt.PenStyle.SolidLine)
                selected.setCosmetic(True)
                self.setPen(selected)
            else:
                self.setPen(self._base_pen)
        return super().itemChange(change, value)

    def _canvas_view(self):
        scene = self.scene()
        if scene is None:
            return None
        for view in scene.views():
            if isinstance(view, GraphCanvasView):
                return view
        return None

    def mousePressEvent(self, event):
        # BETA1-B02: only the left button selects. Without this filter the
        # right button also triggered select_ring before the context menu
        # opened, causing a view jump on every right click.
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        view = self._canvas_view()
        if view is not None:
            view.select_ring(self.ring.ring_id)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        view = self._canvas_view()
        if view is not None:
            view.select_ring(self.ring.ring_id)
            view.focus_ring_scope(self.ring.ring_id)
        event.accept()


_STRUCTURAL_RELATIONS = {"contiene", "pertenece_a"}
_CAUSAL_RELATIONS = {"deriva_de", "condiciona", "explica", "contradice", "produce_consecuencia_en"}
_COHERENCE_RELATIONS = {"incidencia", "contradiccion", "hueco", "reparacion"}


def relation_family(kind: str) -> str:
    value = (kind or "").lower()
    if value in _STRUCTURAL_RELATIONS:
        return "estructural"
    if value in _CAUSAL_RELATIONS:
        return "causal"
    if value in _COHERENCE_RELATIONS or "coher" in value or "incid" in value:
        return "coherencia"
    return "narrativa"

class GraphCanvasView(QGraphicsView):
    """Interactive view: pan/zoom with selectable nodes and edges."""

    entitySelected = Signal(str)
    relationSelected = Signal(str)
    relationCreateRequested = Signal(str, str)
    graphSelectionChanged = Signal(list, list)
    nodeAssignToTreeRequested = Signal(str, str)  # entity_id, tree_entity_id
    relationCreateRejected = Signal(str)
    ringSelected = Signal(str, str)  # ring_id, display_name
    ringFocused = Signal(str, str)  # ring_id, display_name
    # BETA1-B01: context-menu intents. The canvas only emits intent; the
    # CreationWorkspace wires them to its existing creation/deletion routes
    # so no persistence logic lives here.
    contextCreateEntityRequested = Signal()
    contextCreateTreeRequested = Signal()
    contextCreateEntityInTreeRequested = Signal(str)  # parent tree entity_id
    contextCreateSubtreeRequested = Signal(str)  # parent tree entity_id
    contextDeleteRequested = Signal()
    # BETA1-B02: emitted after Escape has cancelled modes and cleared the
    # selection, so the workspace can close contextual surfaces (drawer).
    escapePressed = Signal()
    # BETA1-B03: 'Mover a anillo' — entity_id, ring_id (= world layer id).
    # The workspace resolves it through EntityController.update (CRUD-U).
    nodeAssignToRingRequested = Signal(str, str)
    # BETA1-B03: ring CRUD intents (LayerController routes in the workspace)
    ringCreateRequested = Signal()
    ringEditRequested = Signal(str)  # ring_id
    ringDeleteRequested = Signal(str)  # ring_id
    # BETA1-B03: dragging content OUT of its container extracts it (the
    # workspace removes the 'contiene' membership).
    nodeExtractFromTreeRequested = Signal(str)  # entity_id

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
        self._all_nodes: list[_NodeView] = []
        self._all_edges: list[_EdgeView] = []
        self._all_layers: list[Any] = []
        self._layout_mode_active = "free"
        self._layer_mode_active = False  # compatibility flag for existing B36 toolbar code
        self._ring_visuals: list[_RingVisual] = []
        self._ring_items: dict[str, GraphRingItem] = {}
        self._node_ring_ids: dict[str, str] = {}
        self._selected_ring_id = ""
        self._focused_ring_id = ""
        self._visual_filter = VisualFilterState()
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
        # BETA1-B02: keyboard core. Click focus so shortcuts only apply when
        # the user is actually working on the canvas; text inputs in panels
        # keep receiving their own key events untouched.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._space_pan_active = False
        # BETA1-B02 fix: explicit ring chosen via context menu must win over
        # any focused ring while the creation route runs (one-shot override).
        self._context_ring_override = ""
        # BETA1-B02: camera state captured by set_graph for same-layout rebuilds
        self._view_state_to_restore: tuple[QTransform, QPointF] | None = None
        # BETA1-B03: plain left-drag MOVES items (Qt native move). The item
        # being moved is tracked so the release can offer drop-on-tree
        # assignment. Relation creation lives in the context menu only.
        self._moving_item: GraphNodeItem | GraphTreeItem | None = None
        self._move_origin_scene = QPointF()

    def selected_entity_ids(self) -> list[str]:
        return list(self._selected_entity_ids)

    def selected_relation_ids(self) -> list[str]:
        return list(self._selected_relation_ids)

    def selection_payload(self) -> tuple[list[str], list[str]]:
        return self.selected_entity_ids(), self.selected_relation_ids()

    def _emit_selection_changed(self):
        self._apply_relation_emphasis()
        self.graphSelectionChanged.emit(self.selected_entity_ids(), self.selected_relation_ids())

    def clear_selection(self, *, emit: bool = True):
        for item in self._nodes.values():
            item.set_coherence_selected(False)
        for item in self._trees.values():
            item.set_coherence_selected(False)
        self._clear_selection_impl(emit=emit)

    def refresh_all_visibility(self):
        """Central visibility refresh for all edges based on source/target visibility.

        Called after collapse, expand, filters, or any structural change.
        Rule: an edge is visible only if both source and target are visible and relations are enabled.
        """
        for edge in self._edges:
            src_vis = edge.source.isVisible()
            tgt_vis = edge.target.isVisible()
            edge.setVisible(src_vis and tgt_vis and self._visual_filter.show_relations)

    def _clear_selection_impl(self, *, emit: bool = True):
        for item in self._edges:
            item.set_coherence_selected(False)
        # BETA1-B02: also drop ring selection feedback (outline) so clicking
        # the background leaves no ring visually "selected".
        for ring_item in self._ring_items.values():
            if ring_item.isSelected():
                ring_item.setSelected(False)
        self._selected_entity_ids.clear()
        self._selected_relation_ids.clear()
        if emit:
            self._emit_selection_changed()

    def wheelEvent(self, event):
        """Smooth bounded zoom under mouse.

        Keeps camera movement predictable: small steps, no accidental infinite zoom,
        and immediate feedback on every wheel gesture.
        """
        current = self.transform().m11()
        if event.angleDelta().y() > 0:
            factor = 1.08
            if current >= 3.0:
                event.accept()
                return
        else:
            factor = 1 / 1.08
            if current <= 0.22:
                event.accept()
                return
        self.scale(factor, factor)
        event.accept()

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

    def _item_ring_at(self, view_pos) -> GraphRingItem | None:
        """Find the precise concentric ring under *view_pos* by radius.

        Qt's item lookup can return several QGraphicsPathItem rings for the same
        point because large annular paths overlap in their item shapes/z-order.
        B44 ring activation must use the actual concentric radius, not the first
        item returned by QGraphicsView.items().
        """
        scene_pos = self.mapToScene(view_pos.toPoint())
        radius = math.hypot(scene_pos.x(), scene_pos.y())
        matches: list[GraphRingItem] = []
        for ring_id, item in self._ring_items.items():
            ring = item.ring
            if ring.inner_radius <= radius <= ring.outer_radius:
                matches.append(item)
        if matches:
            return min(matches, key=lambda item: item.ring.outer_radius)
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

    def _apply_relation_emphasis(self):
        if not self._selected_entity_ids and not self._selected_relation_ids:
            for edge in self._edges:
                edge.setOpacity(1.0)
            return
        for edge in self._edges:
            related = (
                edge.edge.relation_id in self._selected_relation_ids
                or edge.edge.source_id in self._selected_entity_ids
                or edge.edge.target_id in self._selected_entity_ids
            )
            edge.setOpacity(1.0 if related else 0.22)

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

    # ── BETA1-B02: keyboard core (Delete, Escape, Space+drag) ────────────

    def _is_text_input_focused(self) -> bool:
        """True when a text editor has keyboard focus anywhere in the app.

        Canvas shortcuts must never fire while the user types in a detail
        panel: Space writes spaces, Delete deletes characters, not entities.
        """
        widget = QApplication.focusWidget()
        return isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit))

    def keyPressEvent(self, event):
        if self._is_text_input_focused():
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            if not self._space_pan_active:
                self._space_pan_active = True
                # Disable item interaction so the native ScrollHandDrag pans
                # even when the drag starts on top of a node/ring.
                self.setInteractive(False)
                self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._request_delete_selection()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self._handle_escape()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            # Always clear pan mode on release, even if focus moved meanwhile,
            # so the canvas can never get stuck in non-interactive state.
            if self._space_pan_active:
                self._space_pan_active = False
                self.setInteractive(True)
                self.viewport().unsetCursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _request_delete_selection(self):
        """Delete current selection through the existing route, after explicit
        confirmation. No selection → no-op (and no dialog)."""
        entity_ids = list(self._selected_entity_ids)
        relation_ids = list(self._selected_relation_ids)
        if not entity_ids and not relation_ids:
            return
        if not self._confirm_delete(entity_ids, relation_ids):
            return
        # Same intent signal as the B01 context menu → workspace._delete_selected
        self.contextDeleteRequested.emit()

    def _confirm_delete(self, entity_ids: list[str], relation_ids: list[str]) -> bool:
        """Modal confirmation. Separated so tests can monkeypatch it."""
        parts = []
        if entity_ids:
            parts.append(f"{len(entity_ids)} elemento(s)")
        if relation_ids:
            parts.append(f"{len(relation_ids)} relación(es)")
        message = (
            f"¿Eliminar {' y '.join(parts)}?\n"
            "Esta acción no se puede deshacer."
        )
        result = QMessageBox.question(
            self,
            "Confirmar eliminación",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def _handle_escape(self):
        """Escape: cancel transient modes, clear selection, notify workspace."""
        if self._drag_source is not None:
            self._finish_relation_drag(None)
            self.relationCreateRejected.emit("Relación cancelada")
        if self._alt_line is not None:
            self._finish_alt_drag()
        self._pending_source = None
        self._alt_source = None
        self.clear_selection()
        self.escapePressed.emit()

    # ── BETA1-B01: context menus ─────────────────────────────────────────

    def contextMenuEvent(self, event):
        # Never open a menu mid-drag: cancel transient drag state first so the
        # menu cannot corrupt relation/assignment flows.
        if self._drag_source is not None:
            self._finish_relation_drag(None)
        if self._alt_line is not None:
            self._finish_alt_drag()
        self._pending_source = None
        self._alt_source = None
        menu = self._build_context_menu(QPointF(event.pos()))
        if menu is None or menu.isEmpty():
            super().contextMenuEvent(event)
            return
        event.accept()
        menu.exec(event.globalPos())

    def _build_context_menu(self, view_pos) -> QMenu | None:
        """Hit-test *view_pos* and build the QMenu for the element found.

        Priority mirrors left-click handling: node/tree, then edge, then ring,
        then background. The element under the cursor is selected first so
        edit/delete act on what the user sees highlighted.
        """
        node = self._item_node_at(view_pos)
        if node is not None:
            self._set_single_node_selection(node)
            if isinstance(node, GraphTreeItem):
                return self._tree_context_menu(node)
            return self._node_context_menu(node)
        edge = self._item_edge_at(view_pos)
        if edge is not None:
            self._set_single_edge_selection(edge)
            return self._edge_context_menu(edge)
        ring = self._item_ring_at(view_pos)
        if ring is not None:
            return self._ring_context_menu(ring)
        return self._background_context_menu()

    def _background_context_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Crear hoja aquí", self.contextCreateEntityRequested.emit)
        menu.addAction("Crear rama aquí", self.contextCreateTreeRequested.emit)
        if self._layout_mode_active == "concentric_rings":
            menu.addSeparator()
            menu.addAction("Crear anillo…", self.ringCreateRequested.emit)
        return menu

    def _node_context_menu(self, item: GraphNodeItem) -> QMenu:
        entity_id = item.node.entity_id
        menu = QMenu(self)
        menu.addAction("Editar", lambda: self.entitySelected.emit(entity_id))
        menu.addAction(
            "Crear relación desde aquí",
            lambda: self._begin_context_relation(item),
        )
        # Parent the submenu explicitly: with addMenu("…") PySide leaves the
        # wrapper Python-owned and shiboken deletes the C++ menu when the
        # local reference dies (before exec()). QMenu(title, parent) hands
        # ownership to the parent menu.
        move_menu = QMenu("Mover a rama", menu)
        menu.addMenu(move_menu)
        targets = self._context_target_trees(exclude_id=entity_id)
        if targets:
            for tree_id, tree_name in targets:
                move_menu.addAction(
                    tree_name,
                    lambda _=False, tid=tree_id: self.nodeAssignToTreeRequested.emit(entity_id, tid),
                )
        else:
            empty = move_menu.addAction("Sin ramas disponibles")
            empty.setEnabled(False)
        # BETA1-B03: ring reassignment through EntityController.update
        ring_targets = self._context_target_rings(exclude_entity=entity_id)
        if ring_targets:
            ring_menu = QMenu("Mover a anillo", menu)
            menu.addMenu(ring_menu)
            for ring_id, ring_name in ring_targets:
                ring_menu.addAction(
                    ring_name,
                    lambda _=False, rid=ring_id: self.nodeAssignToRingRequested.emit(entity_id, rid),
                )
        else:
            ring_action = menu.addAction("Mover a anillo")
            ring_action.setEnabled(False)
            ring_action.setToolTip("Sin anillos disponibles (vista concéntrica)")
        menu.addSeparator()
        menu.addAction("Eliminar", self.contextDeleteRequested.emit)
        return menu

    def _tree_context_menu(self, item: GraphTreeItem) -> QMenu:
        tree_id = item.node.entity_id
        menu = QMenu(self)
        menu.addAction("Editar", lambda: self.entitySelected.emit(tree_id))
        menu.addAction(
            "Crear relación desde aquí",
            lambda: self._begin_context_relation(item),
        )
        menu.addAction(
            "Crear hoja dentro",
            lambda: self.contextCreateEntityInTreeRequested.emit(tree_id),
        )
        menu.addAction(
            "Crear subrama",
            lambda: self.contextCreateSubtreeRequested.emit(tree_id),
        )
        ring_targets = self._context_target_rings(exclude_entity=tree_id)
        if ring_targets:
            ring_menu = QMenu("Mover a anillo", menu)
            menu.addMenu(ring_menu)
            for ring_id, ring_name in ring_targets:
                ring_menu.addAction(
                    ring_name,
                    lambda _=False, rid=ring_id: self.nodeAssignToRingRequested.emit(tree_id, rid),
                )
        else:
            ring_action = menu.addAction("Mover a anillo")
            ring_action.setEnabled(False)
            ring_action.setToolTip("Sin anillos disponibles (vista concéntrica)")
        menu.addSeparator()
        menu.addAction("Eliminar", self.contextDeleteRequested.emit)
        return menu

    def _edge_context_menu(self, item: GraphEdgeItem) -> QMenu:
        relation_id = item.edge.relation_id
        menu = QMenu(self)
        menu.addAction("Editar relación", lambda: self.relationSelected.emit(relation_id))
        menu.addSeparator()
        menu.addAction("Eliminar relación", self.contextDeleteRequested.emit)
        return menu

    def _ring_context_menu(self, item: GraphRingItem) -> QMenu:
        ring_id = item.ring.ring_id
        menu = QMenu(self)
        menu.addAction(
            "Crear hoja en este anillo",
            lambda: self._create_in_ring(ring_id, self.contextCreateEntityRequested),
        )
        menu.addAction(
            "Crear rama en este anillo",
            lambda: self._create_in_ring(ring_id, self.contextCreateTreeRequested),
        )
        # BETA1-B03: ring CRUD. The synthetic unclassified ring is not a real
        # world layer, so it cannot be edited/deleted.
        if ring_id != "__unclassified__":
            menu.addSeparator()
            menu.addAction("Editar anillo…", lambda: self.ringEditRequested.emit(ring_id))
            menu.addAction("Crear anillo…", self.ringCreateRequested.emit)
            menu.addAction("Eliminar anillo", lambda: self.ringDeleteRequested.emit(ring_id))
        return menu

    def _create_in_ring(self, ring_id: str, signal):
        # select_ring marks the ring active, so the existing creation route
        # (_with_active_ring_payload in CreationWorkspace) lands the new
        # element in this ring without new persistence logic.
        # The one-shot override guarantees the right-clicked ring wins even
        # when another ring holds focus (active_ring_id prefers focus).
        self.select_ring(ring_id)
        self._context_ring_override = ring_id
        try:
            signal.emit()  # synchronous: creation runs inside this emit
        finally:
            self._context_ring_override = ""

    def _context_target_trees(self, *, exclude_id: str) -> list[tuple[str, str]]:
        """Candidate trees for 'Mover a rama': all trees except self and any
        assignment that would create a containment cycle."""
        targets: list[tuple[str, str]] = []
        for item_id, item in self._nodes.items():
            if not isinstance(item, GraphTreeItem) or item_id == exclude_id:
                continue
            if self.would_create_cycle(exclude_id, item_id):
                continue
            targets.append((item_id, item.node.name or item_id))
        targets.sort(key=lambda pair: pair[1].lower())
        return targets[:20]

    def _context_target_rings(self, *, exclude_entity: str) -> list[tuple[str, str]]:
        """Candidate rings for 'Mover a anillo': every visible ring except the
        synthetic unclassified ring and the entity's current one."""
        current = self._node_ring_ids.get(exclude_entity, "")
        targets: list[tuple[str, str]] = []
        for ring in self._ring_visuals:
            if ring.ring_id in ("__unclassified__", current):
                continue
            targets.append((ring.ring_id, ring.display_name))
        return targets

    def _begin_context_relation(self, source: GraphNodeItem | GraphTreeItem):
        """Start the existing relation-drag flow from a context-menu action.

        The arrow follows the cursor (mouseMoveEvent already handles
        _drag_source) and the next left-click completes or cancels the
        relation — see the early branch in mousePressEvent.
        """
        self._start_relation_drag(source)

    def mousePressEvent(self, event):
        # BETA1-B02: in space-pan mode the view is non-interactive and the
        # native ScrollHandDrag must receive the press untouched (no
        # selection, no relation logic).
        if self._space_pan_active:
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            # BETA1-B01: a relation started from the context menu has
            # _drag_source set without a held button; the next click picks
            # the target (or cancels on background). Normal drags never enter
            # here because the button is already held down.
            if self._drag_source is not None and self._pending_source is None:
                source = self._drag_source
                target = self._item_node_at(event.position())
                self._finish_relation_drag(target)
                if target is None:
                    self.relationCreateRejected.emit("Relación cancelada")
                elif target is source:
                    self.relationCreateRejected.emit("No se puede crear una relación sobre el mismo elemento")
                else:
                    self.relationCreateRequested.emit(source.node.entity_id, target.node.entity_id)
                event.accept()
                return
            items = self.items(event.position().toPoint())
            _b44trace(
                "mouse_press "
                f"layout={self._layout_mode_active} pos=({event.position().x():.1f},{event.position().y():.1f}) "
                f"scene=({self.mapToScene(event.position().toPoint()).x():.1f},{self.mapToScene(event.position().toPoint()).y():.1f}) "
                f"items={[type(item).__name__ for item in items[:8]]!r}"
            )
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
                self.entitySelected.emit(node.node.entity_id)
                # BETA1-B03: plain drag moves the item (ItemIsMovable does the
                # work once the item receives the press). Relation creation
                # moved to the context menu in B01, so the old drag-to-relate
                # interception is gone. Track the item to support
                # drop-on-tree assignment at release.
                self._moving_item = node
                self._move_origin_scene = QPointF(node.scenePos())
                super().mousePressEvent(event)
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
            ring = self._item_ring_at(event.position())
            _b44trace(
                "mouse_press_hit "
                f"node={getattr(getattr(node, 'node', None), 'entity_id', '') if node is not None else ''!r} "
                f"edge={getattr(getattr(edge, 'edge', None), 'relation_id', '') if edge is not None else ''!r} "
                f"ring={getattr(getattr(ring, 'ring', None), 'ring_id', '') if ring is not None else ''!r}"
            )
            if ring is not None:
                self.select_ring(ring.ring.ring_id)
                event.accept()
                return
            self.clear_selection()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            items = self.items(event.position().toPoint())
            _b44trace(
                "mouse_double "
                f"layout={self._layout_mode_active} pos=({event.position().x():.1f},{event.position().y():.1f}) "
                f"items={[type(item).__name__ for item in items[:8]]!r}"
            )
            node = self._item_node_at(event.position())
            edge = self._item_edge_at(event.position())
            if node is None and edge is None:
                ring = self._item_ring_at(event.position())
                _b44trace(
                    "mouse_double_hit "
                    f"node='' edge='' ring={getattr(getattr(ring, 'ring', None), 'ring_id', '') if ring is not None else ''!r}"
                )
                if ring is not None:
                    self.select_ring(ring.ring.ring_id)
                    self.focus_ring_scope(ring.ring.ring_id)
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        # BETA1-B02: space-pan passes straight to the native hand-drag
        if self._space_pan_active:
            super().mouseMoveEvent(event)
            return
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

        # BETA1-B03: plain drag no longer starts a relation (it moves the
        # item natively). Relations start from the context menu, which sets
        # _drag_source directly via _begin_context_relation.
        if self._drag_source is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._update_relation_drag(scene_pos, self._item_node_at(event.position()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # BETA1-B02: space-pan release returns to the open-hand cursor
        if self._space_pan_active:
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            super().mouseReleaseEvent(event)
            return
        # Alt-drag release: assign node to tree
        if self._alt_line is not None:
            source_item = self._alt_source
            target_tree = self._item_tree_at(event.position())
            self._finish_alt_drag()
            if target_tree is not None and source_item is not None:
                src_id = source_item.node.entity_id
                tgt_id = target_tree.node.entity_id
                if self.would_create_cycle(src_id, tgt_id):
                    self.relationCreateRejected.emit(
                        "No se puede asignar: crearía un ciclo de contención"
                    )
                else:
                    self.nodeAssignToTreeRequested.emit(src_id, tgt_id)
            event.accept()
            return

        if self._drag_source is not None:
            source = self._drag_source
            target = self._item_node_at(event.position())
            self._finish_relation_drag(target)
            if target is not None:
                if target is source:
                    self.relationCreateRejected.emit("No se puede crear una relación sobre el mismo elemento")
                else:
                    self.relationCreateRequested.emit(source.node.entity_id, target.node.entity_id)
            else:
                self.relationCreateRejected.emit("Relación cancelada")
            event.accept()
            return
        # BETA1-B03: finish a native move-drag. If the item was dropped on a
        # tree container, offer assignment through the existing route (same
        # signal as Alt+drag and the context menu).
        moving = self._moving_item
        self._moving_item = None
        if moving is not None and event.button() == Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)  # let Qt close the move grab
            if moving.scenePos() != self._move_origin_scene:
                self._handle_move_drop(moving, event.position())
            return
        self._pending_source = None
        self._alt_source = None
        super().mouseReleaseEvent(event)

    def _handle_move_drop(self, moved: GraphNodeItem | GraphTreeItem, view_pos):
        """BETA1-B03: dropping a moved item onto a tree assigns it to that
        tree — no Alt needed. Drops elsewhere just leave the item moved."""
        target = self._drop_tree_target(moved, view_pos)
        if target is None:
            parent = moved.parentItem()
            if isinstance(parent, GraphTreeItem):
                # BETA1-B03: dropping OUTSIDE the container's own rectangle
                # (pre-refit, children excluded) extracts the item from the
                # branch instead of stretching the branch to swallow it.
                drop_scene = self.mapToScene(view_pos.toPoint())
                parent_rect = parent.mapRectToScene(parent.rect())
                if not parent_rect.contains(drop_scene):
                    self.nodeExtractFromTreeRequested.emit(moved.node.entity_id)
                    return
                # Internal rearrange: refit the whole ancestor chain
                ancestor = parent
                while isinstance(ancestor, GraphTreeItem):
                    if ancestor._child_nodes:
                        ancestor.resize_to_fit_children()
                    ancestor = ancestor.parentItem()
            # BETA1-B03: rings wrap the content wherever the user left it —
            # spans recalc after EVERY move, without repositioning items.
            self._refresh_ring_spans()
            return
        src_id = moved.node.entity_id
        tgt_id = target.node.entity_id
        if self._membership.get(src_id) == tgt_id:
            return
        if self.would_create_cycle(src_id, tgt_id):
            self.relationCreateRejected.emit("No se puede asignar: crearía un ciclo de contención")
            return
        self.nodeAssignToTreeRequested.emit(src_id, tgt_id)

    def _drop_tree_target(self, moved, view_pos) -> GraphTreeItem | None:
        """Tree under *view_pos*, excluding the moved item itself and its
        current ancestor chain (so dragging a child within its own tree is a
        rearrange, not a reassignment)."""
        ancestors: set = set()
        parent = moved.parentItem()
        while parent is not None:
            ancestors.add(parent)
            parent = parent.parentItem()
        for item in self.items(view_pos.toPoint()):
            check = item
            while check is not None:
                if isinstance(check, GraphTreeItem) and check is not moved and check not in ancestors:
                    return check
                check = check.parentItem()
        return None

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

    def _descendant_ids_for_tree(self, tree_id: str) -> set[str]:
        descendants: set[str] = set()
        stack = [tree_id]
        while stack:
            parent = stack.pop()
            for child, current_parent in self._membership.items():
                if current_parent == parent and child not in descendants:
                    descendants.add(child)
                    stack.append(child)
        return descendants

    def _ancestor_tree_ids(self, entity_id: str) -> list[str]:
        ancestors: list[str] = []
        current = self._membership.get(entity_id)
        seen: set[str] = set()
        while current and current not in seen:
            ancestors.append(current)
            seen.add(current)
            current = self._membership.get(current)
        return ancestors

    def _parent_tree_info(self, entity_id: str) -> tuple[str, str, bool]:
        parent_id = self._membership.get(entity_id) or ""
        if not parent_id:
            return "", "", False
        parent_node = next((node for node in self._all_nodes if node.entity_id == parent_id), None)
        parent_name = parent_node.name if parent_node is not None else "Árbol"
        parent_item = self._trees.get(parent_id)
        collapsed = bool(getattr(parent_item, "_collapsed", False)) if parent_item is not None else False
        return parent_id, parent_name, collapsed

    def _node_passes_filter(self, node: _NodeView, allowed_tree_ids: set[str] | None = None) -> bool:
        vf = self._visual_filter
        if allowed_tree_ids is not None and node.entity_id not in allowed_tree_ids:
            return False
        if vf.focus_entity_ids and node.entity_id not in vf.focus_entity_ids:
            return False
        if vf.entity_types and node.kind.lower() not in vf.entity_types:
            return False
        if vf.layer_ids and (node.layer_id or "") not in vf.layer_ids:
            return False
        if vf.canon_states and node.canon.lower() not in vf.canon_states:
            return False
        if vf.visibility_states and node.visibility.lower() not in vf.visibility_states:
            return False
        return True

    def _edge_passes_filter(self, edge: _EdgeView, visible_node_ids: set[str]) -> bool:
        vf = self._visual_filter
        if edge.source_id not in visible_node_ids or edge.target_id not in visible_node_ids:
            return False
        if edge.kind.lower() == "contiene":
            return True
        if not vf.show_relations:
            return False
        if vf.relation_families and relation_family(edge.kind) not in vf.relation_families:
            return False
        if vf.relation_types and edge.kind.lower() not in vf.relation_types:
            return False
        return True

    def _filtered_graph(self, nodes: list[_NodeView], edges: list[_EdgeView]) -> tuple[list[_NodeView], list[_EdgeView]]:
        # Build membership from the full edge set before applying visual filters.
        self._membership = {edge.target_id: edge.source_id for edge in edges if edge.kind.lower() == "contiene"}
        tree_scope: set[str] | None = None
        if self._visual_filter.tree_id:
            tree_scope = {self._visual_filter.tree_id} | self._descendant_ids_for_tree(self._visual_filter.tree_id)
        filtered_nodes = [node for node in nodes if self._node_passes_filter(node, tree_scope)]
        visible_node_ids = {node.entity_id for node in filtered_nodes}
        filtered_edges = [edge for edge in edges if self._edge_passes_filter(edge, visible_node_ids)]
        return filtered_nodes, filtered_edges

    def clear_graph(self):
        self.clear_selection(emit=False)
        self.scene_obj.clear()
        self._nodes.clear()
        self._trees.clear()
        self._edges.clear()
        self._ring_visuals.clear()
        self._ring_items.clear()
        self._node_ring_ids.clear()
        self._selected_ring_id = ""
        self._emit_selection_changed()

    def _layer_for_node(self, node: _NodeView, layers_by_id: dict[str, Any]):
        return layers_by_id.get(node.layer_id or "")

    def _set_graph_by_layers(self, nodes: list[_NodeView], edges: list[_EdgeView], layers: list[Any]):
        self.clear_graph()
        if not nodes:
            return
        visible_layers = [layer for layer in sort_layers_by_causal_rank(layers or []) if getattr(layer, "is_visible", True) and get_causal_rank(layer) is not None]
        layers_by_id = {str(getattr(layer, "id", "")): layer for layer in visible_layers}
        layer_ids_with_nodes = {n.layer_id for n in nodes if n.layer_id}
        if not visible_layers:
            self.set_graph(nodes, edges, layer_mode=False, layers=[])
            return
        ordered_layer_ids = [str(getattr(layer, "id", "")) for layer in visible_layers]
        unknown_nodes = [n for n in nodes if not n.layer_id or n.layer_id not in layers_by_id]
        band_h = 210.0
        band_w = max(900.0, 150.0 * max(3, len(nodes)))
        x0 = -band_w / 2
        for row, layer in enumerate(visible_layers):
            y = row * band_h
            rect = QGraphicsRectItem(x0, y - band_h / 2 + 8, band_w, band_h - 16)
            color = QColor("#F0EDE1" if row % 2 == 0 else "#E9E4D3")
            color.setAlpha(165)
            rect.setBrush(QBrush(color))
            rect.setPen(QPen(QColor("#D8D2BF"), 1.0, Qt.PenStyle.DashLine))
            rect.setZValue(-50)
            self.scene_obj.addItem(rect)
            label = QGraphicsSimpleTextItem(str(getattr(layer, "name", "Capa")))
            label.setBrush(QBrush(QColor("#6F6A42")))
            font = QFont(); font.setBold(True); font.setPointSize(10)
            label.setFont(font)
            label.setPos(x0 + 18, y - band_h / 2 + 18)
            label.setZValue(-49)
            self.scene_obj.addItem(label)
        nodes_by_layer: dict[str, list[_NodeView]] = {lid: [] for lid in ordered_layer_ids}
        for node in nodes:
            if node.layer_id in nodes_by_layer:
                nodes_by_layer[node.layer_id].append(node)
        if unknown_nodes:
            nodes_by_layer.setdefault("__sin_capa__", []).extend(unknown_nodes)
            y = len(visible_layers) * band_h
            rect = QGraphicsRectItem(x0, y - band_h / 2 + 8, band_w, band_h - 16)
            rect.setBrush(QBrush(QColor("#F7F1E8")))
            rect.setPen(QPen(QColor("#D8D2BF"), 1.0, Qt.PenStyle.DashLine))
            rect.setZValue(-50)
            self.scene_obj.addItem(rect)
            label = QGraphicsSimpleTextItem("Sin anillo asignado")
            label.setBrush(QBrush(QColor("#6F6A42")))
            self.scene_obj.addItem(label)
            label.setPos(x0 + 18, y - band_h / 2 + 18)
            ordered_layer_ids.append("__sin_capa__")
        for row, layer_id in enumerate(ordered_layer_ids):
            layer_nodes = nodes_by_layer.get(layer_id, [])
            if not layer_nodes:
                continue
            spacing = min(170.0, band_w / max(1, len(layer_nodes) + 1))
            start_x = -spacing * (len(layer_nodes) - 1) / 2
            y = row * band_h
            for idx, node in enumerate(layer_nodes):
                x = start_x + idx * spacing
                if node.kind.lower() == "contenedor":
                    item = GraphTreeItem(node, x=x, y=y, width=240, height=120)
                    self._trees[node.entity_id] = item
                else:
                    item = GraphNodeItem(node, x=x, y=y)
                self.scene_obj.addItem(item)
                self._nodes[node.entity_id] = item  # type: ignore[assignment]
        self._membership = {edge.target_id: edge.source_id for edge in edges if edge.kind.lower() == "contiene"}
        seen_edge_ids: set[str] = set()
        for edge in edges:
            edge_id = getattr(edge, "relation_id", "")
            if edge_id and edge_id in seen_edge_ids:
                continue
            if edge_id:
                seen_edge_ids.add(edge_id)
            if edge.kind.lower() == "contiene":
                continue
            source = self._nodes.get(edge.source_id)
            target = self._nodes.get(edge.target_id)
            if not source or not target:
                continue
            source_ring = self._node_ring_ids.get(edge.source_id, "")
            target_ring = self._node_ring_ids.get(edge.target_id, "")
            styled_edge = replace(
                edge,
                inter_ring=bool(source_ring and target_ring and source_ring != target_ring),
                causal=bool(edge.causal or relation_family(edge.kind) == "causal"),
            )
            item = GraphEdgeItem(styled_edge, source, target)
            self.scene_obj.addItem(item)
            self._edges.append(item)
        self._finalize_view(140.0)  # BETA1-B02

    def _ring_color(self, index: int) -> str:
        palette = [
            "#E9D8FD",
            "#DBEAFE",
            "#D1FAE5",
            "#FEF3C7",
            "#FCE7F3",
            "#E0F2FE",
            "#EDE9FE",
            "#FDE68A",
        ]
        return palette[index % len(palette)]

    def _ring_item_size_estimate(self, node: _NodeView, child_count: int = 0) -> float:
        if node.kind.lower() != "contenedor":
            return 124.0
        if child_count <= 0:
            # Fallback for callers without containment info
            entity = getattr(node, "entity", None)
            child_ids = list(getattr(entity, "child_entity_ids", []) or getattr(entity, "children_ids", []) or getattr(entity, "entity_ids", []) or [])
            child_count = len(child_ids)
        if child_count <= 0:
            return _CONTAINER_MIN_WIDTH
        # BETA1-B03: nested children render inside the tree, so the tree (and
        # therefore its ring) must reserve room for them with slack.
        cols = max(1, min(4, math.ceil(math.sqrt(child_count))))
        rows = math.ceil(child_count / cols)
        estimated_width = max(_CONTAINER_MIN_WIDTH, cols * 152.0 + (cols - 1) * _CONTAINER_CHILD_SPACING + _CONTAINER_PADDING * 2)
        estimated_height = max(_CONTAINER_MIN_HEIGHT, _CONTAINER_HEADER_HEIGHT + rows * 132.0 + (rows - 1) * 32.0 + _CONTAINER_PADDING)
        return max(estimated_width, estimated_height)

    def _build_concentric_ring_visuals(
        self,
        nodes: list[_NodeView],
        edges: list[_EdgeView],
        layers: list[Any],
        measured: dict[str, float] | None = None,
    ) -> tuple[list[_RingVisual], dict[str, str]]:
        """Build ephemeral B44 ring visuals and node→ring assignment.

        Uses WorldLayer/Anillo instances already present in the project. No
        persistence or canon mutation is performed here.
        """
        visible_layers = [layer for layer in sort_layers_by_causal_rank(layers or []) if getattr(layer, "is_visible", True)]
        layer_by_id = {str(getattr(layer, "id", "")): layer for layer in visible_layers if str(getattr(layer, "id", ""))}
        ordered_ring_ids = [str(getattr(layer, "id", "")) for layer in visible_layers if str(getattr(layer, "id", ""))]

        node_ring_ids: dict[str, str] = {}
        node_ids_by_ring: dict[str, list[str]] = {ring_id: [] for ring_id in ordered_ring_ids}
        unclassified: list[str] = []
        for node in nodes:
            layer_id = node.layer_id or ""
            if layer_id and layer_id in layer_by_id:
                ring_id = layer_id
                node_ids_by_ring.setdefault(ring_id, []).append(node.entity_id)
            else:
                ring_id = "__unclassified__"
                unclassified.append(node.entity_id)
            node_ring_ids[node.entity_id] = ring_id

        if unclassified:
            node_ids_by_ring["__unclassified__"] = unclassified
            ordered_ring_ids.append("__unclassified__")

        relation_ids_by_ring: dict[str, list[str]] = {ring_id: [] for ring_id in ordered_ring_ids}
        for edge in edges:
            if edge.kind.lower() == "contiene":
                continue
            source_ring = node_ring_ids.get(edge.source_id)
            target_ring = node_ring_ids.get(edge.target_id)
            if not source_ring or not target_ring:
                continue
            # B44-T01/T02: basic association only. Advanced inter-ring styling is T06.
            ring_id = source_ring if source_ring == target_ring else source_ring
            if ring_id in relation_ids_by_ring:
                relation_ids_by_ring[ring_id].append(edge.relation_id)

        nodes_by_id = {node.entity_id: node for node in nodes}
        # BETA1-B03: containment info — contained items render INSIDE their
        # tree, so they don't occupy a ring slot of their own, while trees
        # grow with their child count (with slack).
        contains_count: dict[str, int] = {}
        contained_set: set[str] = set()
        for edge in edges:
            if edge.kind.lower() == "contiene":
                contains_count[edge.source_id] = contains_count.get(edge.source_id, 0) + 1
                contained_set.add(edge.target_id)
        visuals: list[_RingVisual] = []
        previous_outer = 0.0
        gap = 34.0
        for index, ring_id in enumerate(ordered_ring_ids):
            item_ids = tuple(node_ids_by_ring.get(ring_id, []))
            ring_nodes = [nodes_by_id[item_id] for item_id in item_ids if item_id in nodes_by_id]
            branch_count = sum(1 for node in ring_nodes if node.kind.lower() == "contenedor")
            leaf_count = max(0, len(ring_nodes) - branch_count)
            relation_ids = tuple(relation_ids_by_ring.get(ring_id, []))
            slotted_nodes = [node for node in ring_nodes if node.entity_id not in contained_set]

            def _extent(node: _NodeView) -> float:
                # BETA1-B03 reactive: a real measured size (tree already
                # nested/resized/collapsed) beats any estimate.
                if measured and node.entity_id in measured:
                    return measured[node.entity_id]
                return self._ring_item_size_estimate(node, contains_count.get(node.entity_id, 0))

            extents = [_extent(node) for node in slotted_nodes]
            slot_total = sum(extents)
            slot_total += max(0, len(slotted_nodes)) * 36.0 + 140.0  # label arc reserve
            required_mid_radius = slot_total / (2 * math.pi) if slotted_nodes else 0.0
            max_extent = max(extents) if extents else 0.0
            # The ring must be at least thick enough to hold its largest item
            # with slack (90px), and grows mildly with crowding.
            content_thickness = (
                max(176.0, max_extent + 90.0)
                + max(0, len(slotted_nodes) - 1) * 16.0
                + branch_count * 24.0
            )
            inner = 42.0 if index == 0 else previous_outer + gap
            outer = max(inner + content_thickness, required_mid_radius + content_thickness / 2.0)
            if outer <= inner:
                outer = inner + content_thickness

            if ring_id == "__unclassified__":
                display_name = "Sin clasificar"
                rank = None
                color = "#ECE7DA"
            else:
                layer = layer_by_id[ring_id]
                display_name = str(getattr(layer, "name", "Anillo"))
                rank = get_causal_rank(layer)
                color = self._ring_color(index)

            relation_count = len(relation_ids)
            count_label = f"{leaf_count} hojas · {branch_count} ramas · {relation_count} relaciones"
            state = "focused" if self._focused_ring_id and ring_id == self._focused_ring_id else "normal"
            visuals.append(_RingVisual(
                ring_id=ring_id,
                display_name=display_name,
                causal_rank=rank,
                color=color,
                inner_radius=inner,
                outer_radius=outer,
                item_ids=item_ids,
                relation_ids=relation_ids,
                count_label=count_label,
                state=state,
            ))
            previous_outer = outer
        return visuals, node_ring_ids

    def _draw_ring_background(self, ring: _RingVisual):
        outer_rect = QRectF(-ring.outer_radius, -ring.outer_radius, ring.outer_radius * 2, ring.outer_radius * 2)
        inner_rect = QRectF(-ring.inner_radius, -ring.inner_radius, ring.inner_radius * 2, ring.inner_radius * 2)
        outer_path = QPainterPath()
        outer_path.addEllipse(outer_rect)
        inner_path = QPainterPath()
        inner_path.addEllipse(inner_rect)
        path = outer_path.subtracted(inner_path)
        item = GraphRingItem(ring, path)
        color = QColor(ring.color)
        color.setAlpha(116 if ring.state == "focused" else 82)
        item.setBrush(QBrush(color))
        pen = QPen(QColor("#6F6A42") if ring.state == "focused" else QColor(ring.color).darker(118), 2.4 if ring.state == "focused" else 1.2, Qt.PenStyle.SolidLine if ring.state == "focused" else Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        item.setPen(pen)
        item._base_pen = QPen(pen)  # restored when the ring is deselected
        item.setZValue(-100)
        self.scene_obj.addItem(item)
        self._ring_items[ring.ring_id] = item

        label_text = f"{ring.display_name} · {ring.count_label} · doble click: entrar"
        label = QGraphicsSimpleTextItem(_fit_text(label_text, 72), item)
        label.setBrush(QBrush(QColor("#5F5A3D")))
        label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        font = QFont(); font.setBold(True); font.setPointSize(10)
        label.setFont(font)
        rect = label.boundingRect()
        label.setPos(-rect.width() / 2, -ring.outer_radius + 14)
        label.setZValue(10)

    def _layout_concentric_rings(self, nodes: list[_NodeView], edges: list[_EdgeView], layers: list[Any]) -> bool:
        """BETA1-B03: (re)compute ring visuals from the REAL current item
        sizes, draw the ring backgrounds and place top-level items in their
        slots. Reused by the initial build and by reactive re-layouts
        (collapse/expand), so ring sizes always match the content.

        Returns False when there are no rings to draw (caller falls back)."""
        # Drop previous ring graphics (labels are their Qt children)
        for ring_item in self._ring_items.values():
            self.scene_obj.removeItem(ring_item)
        self._ring_items = {}

        # Measure top-level trees as they really are (nested, resized,
        # possibly collapsed). Leaves keep the standard estimate.
        measured: dict[str, float] = {}
        for entity_id, tree in self._trees.items():
            if tree.parentItem() is None:
                rect = tree.boundingRect()
                measured[entity_id] = max(rect.width(), rect.height())

        self._ring_visuals, self._node_ring_ids = self._build_concentric_ring_visuals(
            nodes, edges, layers, measured=measured
        )
        if not self._ring_visuals:
            return False

        for ring in self._ring_visuals:
            self._draw_ring_background(ring)

        contained_set = {edge.target_id for edge in edges if edge.kind.lower() == "contiene"}
        nodes_by_id = {node.entity_id: node for node in nodes}
        for ring in self._ring_visuals:
            ring_nodes = [nodes_by_id[item_id] for item_id in ring.item_ids if item_id in nodes_by_id]
            slotted = [node for node in ring_nodes if node.entity_id not in contained_set]
            for idx, node in enumerate(slotted):
                item = self._nodes.get(node.entity_id)
                if item is None or item.parentItem() is not None:
                    continue
                pos = self._position_for_ring_slot(ring, idx, len(slotted))
                if isinstance(item, GraphTreeItem):
                    # Center the tree's actual rect on the slot
                    rect = item.boundingRect()
                    item.setPos(pos.x() - rect.center().x(), pos.y() - rect.center().y())
                else:
                    item.setPos(pos)
        # Edges may already exist (reactive re-layout): follow the new slots
        for edge_item in self._edges:
            edge_item.update_path()
        return True

    def _relayout_concentric(self):
        """BETA1-B03: reactive ring sizing — called after collapse/expand so
        rings grow/shrink around the content without rebuilding the graph."""
        if self._layout_mode_active != "concentric_rings":
            return
        inputs = getattr(self, "_concentric_inputs", None)
        if not inputs:
            return
        nodes, edges, layers = inputs
        if self._layout_concentric_rings(nodes, edges, layers):
            self._expand_scene_rect_to_content()

    def _refresh_ring_spans(self):
        """BETA1-B03: resize ring bands around the CURRENT positions and
        sizes of their top-level items, WITHOUT repositioning anything.

        Used after manual moves: _relayout_concentric would snap items back
        to their slots, undoing the user's placement; this only makes each
        ring wide enough to wrap its content wherever it sits."""
        if self._layout_mode_active != "concentric_rings" or not self._ring_visuals:
            return
        contained: set[str] = set()
        inputs = getattr(self, "_concentric_inputs", None)
        if inputs:
            _, edges, _ = inputs
            contained = {edge.target_id for edge in edges if edge.kind.lower() == "contiene"}
        new_visuals: list[_RingVisual] = []
        previous_outer = 0.0
        gap = 34.0
        for index, ring in enumerate(self._ring_visuals):
            inner = 42.0 if index == 0 else previous_outer + gap
            required = inner + 176.0
            for item_id in ring.item_ids:
                if item_id in contained:
                    continue
                item = self._nodes.get(item_id)
                if item is None or item.parentItem() is not None:
                    continue
                rect = item.sceneBoundingRect()
                center_dist = math.hypot(rect.center().x(), rect.center().y())
                extent = max(rect.width(), rect.height()) / 2.0
                required = max(required, center_dist + extent + 60.0)
            outer = required
            new_visuals.append(replace(ring, inner_radius=inner, outer_radius=outer))
            previous_outer = outer
        self._ring_visuals = new_visuals
        selected_ring = self._selected_ring_id
        for ring_item in self._ring_items.values():
            self.scene_obj.removeItem(ring_item)
        self._ring_items = {}
        for ring in self._ring_visuals:
            self._draw_ring_background(ring)
        if selected_ring and selected_ring in self._ring_items:
            self._ring_items[selected_ring].setSelected(True)
        self._expand_scene_rect_to_content()

    def _nest_contained_items(self, nodes: list[_NodeView], edges: list[_EdgeView]):
        """BETA1-B03: re-parent contained items into their tree containers.

        Mirrors the free-layout nesting contract for the concentric view:
        children become Qt children of the tree (they render inside it and
        move with it) and trees are resized bottom-up to fit with slack.
        """
        contains_map: dict[str, set[str]] = {}
        for edge in edges:
            if edge.kind.lower() == "contiene":
                contains_map.setdefault(edge.source_id, set()).add(edge.target_id)
        if not contains_map:
            return
        # Leaves-first order so nested containers are sized before parents
        ordered: list[str] = []
        visited: set[str] = set()

        def _visit(container_id: str):
            if container_id in visited:
                return
            visited.add(container_id)
            for child_id in contains_map.get(container_id, ()):  # noqa: B023
                if child_id in self._trees:
                    _visit(child_id)
            ordered.append(container_id)

        for container_id in contains_map:
            if container_id in self._trees:
                _visit(container_id)

        for container_id in ordered:
            tree = self._trees.get(container_id)
            if tree is None:
                continue
            child_ids = contains_map.get(container_id, set())
            leaf_ids = [eid for eid in child_ids if eid in self._nodes and eid not in self._trees]
            nested_tree_ids = [eid for eid in child_ids if eid in self._trees and eid != container_id]
            tree_cx = tree._width / 2
            tree_cy = tree._height / 2
            child_radius = max(70, min(160, 50 * len(leaf_ids))) if leaf_ids else 70.0
            for index, entity_id in enumerate(leaf_ids):
                item = self._nodes[entity_id]
                count = max(1, len(leaf_ids))
                if count == 1:
                    cx, cy = tree_cx, tree_cy + _CONTAINER_HEADER_HEIGHT + 60
                else:
                    angle = (2 * math.pi * index) / count
                    cx = tree_cx + math.cos(angle) * child_radius
                    cy = tree_cy + _CONTAINER_HEADER_HEIGHT + 60 + math.sin(angle) * child_radius * 0.5
                item.setPos(cx, cy)
                tree.add_child_node(item)  # type: ignore[arg-type]
            if nested_tree_ids:
                nested_y = _CONTAINER_HEADER_HEIGHT + 60 + (child_radius * 2 + 40 if leaf_ids else 0)
                for index, entity_id in enumerate(nested_tree_ids):
                    nested = self._trees[entity_id]
                    spread = max(1, len(nested_tree_ids))
                    width = nested._width
                    nested.setPos(tree_cx + (index - (spread - 1) / 2) * (width + 30), tree_cy + nested_y)
                    tree.add_child_node(nested)  # type: ignore[arg-type]
            if tree._child_nodes:
                tree.resize_to_fit_children()

    def _position_for_ring_slot(self, ring: _RingVisual, index: int, count: int) -> QPointF:
        mid_radius = (ring.inner_radius + ring.outer_radius) / 2.0
        if count <= 1:
            angle = math.pi / 2.0
        else:
            reserved = 0.72  # keep top label arc clear
            span = 2 * math.pi - reserved * 2
            angle = -math.pi / 2 + reserved + (span * index / max(1, count - 1))
        return QPointF(math.cos(angle) * mid_radius, math.sin(angle) * mid_radius)

    def _set_graph_by_concentric_rings(self, nodes: list[_NodeView], edges: list[_EdgeView], layers: list[Any]):
        _b44trace(
            "concentric_enter "
            f"nodes={len(nodes or [])} edges={len(edges or [])} layers={len(layers or [])} "
            f"filter_layers={tuple(getattr(self._visual_filter, 'layer_ids', ()))!r} "
            f"filter_focus={tuple(getattr(self._visual_filter, 'focus_entity_ids', ()))!r}"
        )
        self.clear_graph()
        if self._focused_ring_id:
            all_visuals, all_node_ring_ids = self._build_concentric_ring_visuals(nodes, edges, layers or [])
            focused = next((ring for ring in all_visuals if ring.ring_id == self._focused_ring_id), None)
            if focused is None:
                self._focused_ring_id = ""
            else:
                focused_node_ids = {entity_id for entity_id, ring_id in all_node_ring_ids.items() if ring_id == focused.ring_id}
                nodes = [node for node in nodes if node.entity_id in focused_node_ids]
                edges = [edge for edge in edges if edge.source_id in focused_node_ids and edge.target_id in focused_node_ids]
                if focused.ring_id != "__unclassified__":
                    layers = [layer for layer in (layers or []) if str(getattr(layer, "id", "")) == focused.ring_id]
                else:
                    layers = []
        # BETA1-B03 (reactive rings): create ALL items first at a provisional
        # origin, nest contained items into their trees and resize them —
        # only then compute ring radii from the REAL measured sizes. This is
        # what lets rings reserve space with slack and react to growth.
        for node in nodes:
            if node.kind.lower() == "contenedor":
                item = GraphTreeItem(
                    node,
                    x=0.0,
                    y=0.0,
                    width=_CONTAINER_MIN_WIDTH,
                    height=_CONTAINER_MIN_HEIGHT,
                )
                self._trees[node.entity_id] = item
            else:
                item = GraphNodeItem(node, x=0.0, y=0.0)
            self.scene_obj.addItem(item)
            self._nodes[node.entity_id] = item  # type: ignore[assignment]

        # Nest contained items (same visual contract as the free layout:
        # children inside the rectangle, the tree moves with all its content)
        self._nest_contained_items(nodes, edges)

        # Remember inputs so collapse/expand can re-layout reactively
        self._concentric_inputs = (list(nodes), list(edges), list(layers or []))

        laid_out = self._layout_concentric_rings(nodes, edges, layers or [])
        _b44trace(
            "concentric_built "
            f"ring_visuals={len(self._ring_visuals)} ring_ids={[ring.ring_id for ring in self._ring_visuals]!r} "
            f"node_ring_ids={self._node_ring_ids!r}"
        )
        if not laid_out:
            _b44trace(f"concentric_no_rings fallback_to_free={bool(nodes)}")
            if nodes:
                self.set_graph(nodes, edges, layout_mode="free", layers=layers)
            return

        self._membership = {edge.target_id: edge.source_id for edge in edges if edge.kind.lower() == "contiene"}
        seen_edge_ids: set[str] = set()
        for edge in edges:
            edge_id = getattr(edge, "relation_id", "")
            if edge_id and edge_id in seen_edge_ids:
                continue
            if edge_id:
                seen_edge_ids.add(edge_id)
            if edge.kind.lower() == "contiene":
                continue
            source = self._nodes.get(edge.source_id)
            target = self._nodes.get(edge.target_id)
            if not source or not target:
                continue
            source_ring = self._node_ring_ids.get(edge.source_id, "")
            target_ring = self._node_ring_ids.get(edge.target_id, "")
            styled_edge = replace(
                edge,
                inter_ring=bool(source_ring and target_ring and source_ring != target_ring),
                causal=bool(edge.causal or relation_family(edge.kind) == "causal"),
            )
            item = GraphEdgeItem(styled_edge, source, target)
            self.scene_obj.addItem(item)
            self._edges.append(item)

        # BETA1-B03: register internal edges (tree↔content and content↔content)
        # so collapse/visibility behaves like the free layout.
        for tree in self._trees.values():
            tree.find_internal_edges(self._edges)
            tree.set_canvas_edges(self._edges)

        # BETA1-B02: set_graph returns early for this layout, so the common
        # view finalization (scene rect + camera restore/fit) happens here.
        self._finalize_view(160.0)
        rect = self.scene_obj.itemsBoundingRect()
        _b44trace(
            "concentric_done "
            f"scene_items={len(self.scene_obj.items())} ring_items={len(self._ring_items)} "
            f"nodes_drawn={len(self._nodes)} trees_drawn={len(self._trees)} edges_drawn={len(self._edges)} "
            f"scene_rect_valid={rect.isValid()} scene_rect_empty={rect.isEmpty()}"
        )

    def set_graph(
        self,
        nodes: list[_NodeView],
        edges: list[_EdgeView],
        *,
        layer_mode: bool = False,
        layout_mode: str | None = None,
        layers: list[Any] | None = None,
    ):
        self._all_nodes = list(nodes or [])
        self._all_edges = list(edges or [])
        self._all_layers = list(layers or [])
        if layout_mode is None:
            layout_mode = "layered" if layer_mode else "free"
        if layout_mode not in {"free", "layered", "concentric_rings"}:
            layout_mode = "free"
        # BETA1-B02: rebuilding the same layout (refresh after create/edit/
        # delete) must not reset the user's zoom and pan — constant re-fitting
        # made navigation impossible. Capture the camera now; _finalize_view
        # restores it instead of fitting when the layout didn't change.
        previous_layout = self._layout_mode_active
        self._view_state_to_restore = None
        if layout_mode == previous_layout and self._nodes:
            self._view_state_to_restore = (
                QTransform(self.transform()),
                self.mapToScene(self.viewport().rect().center()),
            )
        self._layout_mode_active = layout_mode
        self._layer_mode_active = layout_mode == "layered"
        if layout_mode == "concentric_rings" and self._focused_ring_id:
            # Ring focus is a concentric-view scope, not a generic visual filter.
            # Build from the full canonical graph so moving an item between rings
            # cannot be hidden by a stale layer filter.
            nodes, edges = list(self._all_nodes), list(self._all_edges)
        else:
            nodes, edges = self._filtered_graph(self._all_nodes, self._all_edges)
        _b44trace(
            "set_graph "
            f"requested_layout={layout_mode} all_nodes={len(self._all_nodes)} all_edges={len(self._all_edges)} "
            f"filtered_nodes={len(nodes)} filtered_edges={len(edges)} layers={len(self._all_layers)} "
            f"filter_layers={tuple(getattr(self._visual_filter, 'layer_ids', ()))!r} "
            f"filter_focus={tuple(getattr(self._visual_filter, 'focus_entity_ids', ()))!r}"
        )
        if layout_mode == "concentric_rings":
            self._set_graph_by_concentric_rings(nodes, edges, layers or [])
            return
        if layout_mode == "layered":
            self._set_graph_by_layers(nodes, edges, layers or [])
            return
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
            source_ring = self._node_ring_ids.get(edge.source_id, "")
            target_ring = self._node_ring_ids.get(edge.target_id, "")
            styled_edge = replace(
                edge,
                inter_ring=bool(source_ring and target_ring and source_ring != target_ring),
                causal=bool(edge.causal or relation_family(edge.kind) == "causal"),
            )
            item = GraphEdgeItem(styled_edge, source, target)
            self.scene_obj.addItem(item)
            self._edges.append(item)

        # ── Register internal edges for each container ──
        for tree in self._trees.values():
            tree.find_internal_edges(self._edges)

        # ── Pass canvas edges to all root-level trees for collapse visibility ──
        for tree in self._trees.values():
            tree.set_canvas_edges(self._edges)

        self._finalize_view(140.0)

    def _finalize_view(self, margin: float = 140.0):
        """BETA1-B02: common tail for every layout builder.

        Expands the scene rect to the content and then either restores the
        camera captured by set_graph (same-layout rebuild → keep the user's
        zoom/pan) or fits the whole graph (first build / layout change)."""
        self._expand_scene_rect_to_content()
        state = self._view_state_to_restore
        if state is not None:
            self._view_state_to_restore = None
            transform, center = state
            self.setTransform(transform)
            self.centerOn(center)
            return
        rect = self.scene_obj.itemsBoundingRect()
        if rect.isValid() and not rect.isEmpty():
            self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.AspectRatioMode.KeepAspectRatio)

    def reveal_entity(self, entity_id: str):
        """BETA1-B02: make an entity visible by scrolling only — no zoom
        change. Used after contextual creation so the new element shows up
        without yanking the camera (focus_entity does a fitInView zoom)."""
        item = self._nodes.get(entity_id) or self._trees.get(entity_id)
        if item is not None:
            self.ensureVisible(item, 120, 120)

    def _expand_scene_rect_to_content(self):
        """BETA1-B02: make the scene rect cover the real content (plus margin)
        so panning — Space+drag, hand-drag, scrollbars — can reach every part
        of the graph. The fixed default rect (3200x2200) was smaller than
        large concentric layouts, which froze navigation near the center.
        Must be called by EVERY layout builder (free/layered/concentric):
        set_graph returns early for layered and concentric modes."""
        content_rect = self.scene_obj.itemsBoundingRect()
        if content_rect.isNull():
            return
        margin = 400.0
        expanded = content_rect.adjusted(-margin, -margin, margin, margin)
        # Never shrink below the historical default so small/free graphs
        # keep their roomy feel.
        expanded = expanded.united(QRectF(-1600, -1100, 3200, 2200))
        self.scene_obj.setSceneRect(expanded)

    def recompute_edge_visibility(self):
        self.refresh_all_visibility()

    def apply_visual_filter(self, filter_state: VisualFilterState):
        self._visual_filter = filter_state
        self.set_graph(self._all_nodes, self._all_edges, layout_mode=self._layout_mode_active, layers=self._all_layers)

    def clear_visual_filters(self):
        self.apply_visual_filter(VisualFilterState())

    def get_filter_state(self) -> VisualFilterState:
        return self._visual_filter

    def active_filter_count(self) -> int:
        vf = self._visual_filter
        return sum(1 for active in [vf.entity_types, vf.relation_types, vf.relation_families, vf.tree_id, vf.layer_ids, vf.focus_entity_ids, vf.canon_states, vf.visibility_states, not vf.show_relations] if active)

    def center_on_item(self, item: QGraphicsItem):
        self.centerOn(item)
        rect = item.sceneBoundingRect().adjusted(-180, -160, 180, 160)
        if rect.isValid() and not rect.isEmpty():
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def focus_node(self, entity_id: str, *, expand_path: bool = True) -> bool:
        if expand_path:
            for ancestor_id in reversed(self._ancestor_tree_ids(entity_id)):
                tree = self._trees.get(ancestor_id)
                if tree is not None and getattr(tree, "_collapsed", False):
                    tree._expand()
        item = self._nodes.get(entity_id) or self._trees.get(entity_id)
        if item is None:
            return False
        self.clear_selection(emit=False)
        self._selected_entity_ids.add(entity_id)
        item.set_coherence_selected(True)
        self.center_on_item(item)
        self._emit_selection_changed()
        return True

    def focus_tree(self, tree_id: str) -> bool:
        return self.focus_node(tree_id, expand_path=True)

    def focus_relation(self, relation_id: str) -> bool:
        edge = next((edge for edge in self._edges if edge.edge.relation_id == relation_id), None)
        if edge is None:
            return False
        self.clear_selection(emit=False)
        self._selected_relation_ids.add(relation_id)
        edge.set_coherence_selected(True)
        self.center_on_item(edge)
        self._emit_selection_changed()
        return True

    def clear_search_focus(self):
        self.clear_selection()

    def search(self, query: str, *, worldbuilding_active: bool = False) -> list[GraphSearchResult]:
        terms = [term for term in str(query or "").lower().split() if term]
        if not terms:
            return []
        layer_names = {str(getattr(layer, "id", "")): str(getattr(layer, "name", "")) for layer in self._all_layers}
        results: list[GraphSearchResult] = []
        for node in self._all_nodes:
            layer_name = layer_names.get(node.layer_id, "") if worldbuilding_active else ""
            haystack = " ".join([node.name, node.kind, node.subtitle, layer_name]).lower()
            if all(term in haystack for term in terms):
                parent_id, parent_name, collapsed = self._parent_tree_info(node.entity_id)
                item_kind = "tree" if node.kind.lower() == "contenedor" else "entity"
                results.append(GraphSearchResult(
                    item_id=node.entity_id,
                    item_kind=item_kind,
                    title=node.name,
                    type_label=enum_human(node.kind),
                    category="Rama" if item_kind == "tree" else "Entidad",
                    summary=_fit_text(node.subtitle, 90),
                    parent_tree_name=parent_name,
                    parent_tree_id=parent_id,
                    is_inside_collapsed_tree=collapsed,
                ))
        for edge in self._all_edges:
            if edge.kind.lower() == "contiene":
                continue
            source = next((node for node in self._all_nodes if node.entity_id == edge.source_id), None)
            target = next((node for node in self._all_nodes if node.entity_id == edge.target_id), None)
            title = edge.label or enum_human(edge.kind)
            haystack = " ".join([title, edge.kind, source.name if source else "", target.name if target else ""]).lower()
            if all(term in haystack for term in terms):
                summary = " → ".join(part for part in [source.name if source else "Origen", target.name if target else "Destino"] if part)
                results.append(GraphSearchResult(
                    item_id=edge.relation_id,
                    item_kind="relation",
                    title=title,
                    type_label=enum_human(edge.kind),
                    category="Relación",
                    summary=summary,
                ))
        return results[:40]

    def _ring_display_name(self, ring_id: str) -> str:
        ring = next((ring for ring in self._ring_visuals if ring.ring_id == ring_id), None)
        if ring is not None:
            return ring.display_name
        if ring_id == "__unclassified__":
            return "Sin clasificar"
        layer = next((layer for layer in self._all_layers if str(getattr(layer, "id", "")) == ring_id), None)
        return str(getattr(layer, "name", "Anillo")) if layer is not None else "Anillo"

    def active_ring_id(self) -> str:
        """Current ring for contextual creation: context-menu override wins
        (explicit user intent), then focused ring, then selected ring."""
        if self._context_ring_override:
            return self._context_ring_override
        return str(self._focused_ring_id or self._selected_ring_id or "")

    def focused_ring_id(self) -> str:
        return str(self._focused_ring_id or "")

    def select_ring(self, ring_id: str) -> bool:
        _b44trace(f"select_ring_request ring_id={ring_id!r} available={[ring.ring_id for ring in self._ring_visuals]!r}")
        if not ring_id:
            _b44trace("select_ring_result ok=False reason=empty_ring_id")
            return False
        ring = next((ring for ring in self._ring_visuals if ring.ring_id == ring_id), None)
        if ring is None:
            _b44trace("select_ring_result ok=False reason=ring_not_found")
            return False
        self.clear_selection(emit=False)
        self._selected_ring_id = ring_id
        # BETA1-B02: only one ring can show selection feedback at a time
        for other in self._ring_items.values():
            if other.isSelected():
                other.setSelected(False)
        item = self._ring_items.get(ring_id)
        if item is not None:
            item.setSelected(True)
            # BETA1-B02: selection must not navigate. center_on_item here did
            # a fitInView (zoom jump) on every ring click, which made manual
            # navigation nearly impossible. Use focus (double click) to dive
            # into a ring; single click only selects.
        self._emit_selection_changed()
        self.ringSelected.emit(ring_id, ring.display_name)
        _b44trace(
            "select_ring_result "
            f"ok=True selected={self._selected_ring_id!r} focused={self._focused_ring_id!r} display={ring.display_name!r}"
        )
        return True

    def focus_ring_scope(self, ring_id: str) -> bool:
        """B44: enter ring focus without mutating canon or assignments."""
        _b44trace(
            "focus_ring_request "
            f"ring_id={ring_id!r} all_nodes={len(self._all_nodes)} all_edges={len(self._all_edges)} all_layers={len(self._all_layers)} "
            f"layout={self._layout_mode_active}"
        )
        if not ring_id:
            _b44trace("focus_ring_result ok=False reason=empty_ring_id")
            return False
        visuals, node_ring_ids = self._build_concentric_ring_visuals(self._all_nodes, self._all_edges, self._all_layers)
        _b44trace(
            "focus_ring_visuals "
            f"available={[ring.ring_id for ring in visuals]!r} node_ring_ids={node_ring_ids!r}"
        )
        ring = next((ring for ring in visuals if ring.ring_id == ring_id), None)
        if ring is None:
            _b44trace("focus_ring_result ok=False reason=ring_not_found")
            return False
        self._focused_ring_id = ring_id
        # Ring focus is not a generic visual layer filter. Keep independent
        # filter dimensions, but clear stale scope filters that hide nodes after
        # ring reassignment.
        self._visual_filter = replace(self._visual_filter, layer_ids=(), focus_entity_ids=(), tree_id="")
        self.set_graph(self._all_nodes, self._all_edges, layout_mode="concentric_rings", layers=self._all_layers)
        self.ringFocused.emit(ring_id, ring.display_name)
        _b44trace(
            "focus_ring_result "
            f"ok=True focused={self._focused_ring_id!r} selected={self._selected_ring_id!r} "
            f"filter_layers={tuple(getattr(self._visual_filter, 'layer_ids', ()))!r} "
            f"filter_focus={tuple(getattr(self._visual_filter, 'focus_entity_ids', ()))!r} "
            f"ring_items={len(self._ring_items)} nodes_drawn={len(self._nodes)}"
        )
        return True

    def clear_ring_focus(self):
        self._focused_ring_id = ""
        self._selected_ring_id = ""
        self._visual_filter = replace(self._visual_filter, layer_ids=(), focus_entity_ids=(), tree_id="")
        if self._layout_mode_active == "concentric_rings":
            self.set_graph(self._all_nodes, self._all_edges, layout_mode="concentric_rings", layers=self._all_layers)

    def focus_tree_scope(self, tree_id: str) -> bool:
        ids = {tree_id} | self._descendant_ids_for_tree(tree_id)
        self.apply_visual_filter(VisualFilterState(focus_entity_ids=tuple(sorted(ids))))
        return self.focus_tree(tree_id)

    def focus_neighborhood(self, item_id: str) -> bool:
        ids: set[str] = set()
        relation = next((edge for edge in self._all_edges if edge.relation_id == item_id), None)
        center_relation = ""
        if relation is not None:
            ids.update([relation.source_id, relation.target_id])
            center_relation = item_id
        else:
            ids.add(item_id)
            for edge in self._all_edges:
                if edge.source_id == item_id or edge.target_id == item_id:
                    ids.update([edge.source_id, edge.target_id])
        # Include ancestor containers so nodes inside trees remain visible
        for eid in list(ids):
            current = self._membership.get(eid)
            while current is not None:
                ids.add(current)
                current = self._membership.get(current)
        self.apply_visual_filter(VisualFilterState(focus_entity_ids=tuple(sorted(ids))))
        if center_relation:
            return self.focus_relation(center_relation)
        return self.focus_node(item_id)

    def clear_focus_scope(self):
        self.clear_ring_focus()
        self.clear_visual_filters()

    def fit_all(self):
        rect = self.scene_obj.itemsBoundingRect()
        if rect.isValid() and not rect.isEmpty():
            self.fitInView(rect.adjusted(-140, -140, 140, 140), Qt.AspectRatioMode.KeepAspectRatio)

    def reset_view(self):
        self.resetTransform()
        self.centerOn(0, 0)

    def center_selection(self) -> bool:
        selected_items = []
        selected_items.extend(item for eid, item in self._nodes.items() if eid in self._selected_entity_ids)
        selected_items.extend(item for eid, item in self._trees.items() if eid in self._selected_entity_ids)
        selected_items.extend(edge for edge in self._edges if edge.edge.relation_id in self._selected_relation_ids)
        if not selected_items:
            return False
        rect = selected_items[0].sceneBoundingRect()
        for item in selected_items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        self.fitInView(rect.adjusted(-180, -160, 180, 160), Qt.AspectRatioMode.KeepAspectRatio)
        return True

    def focus_entity(self, entity_id: str):
        self.focus_node(entity_id)


class GraphCanvasWidget(QWidget):
    """B31-T03 graph-first Creation entry."""

    entitySelected = Signal(str)
    relationSelected = Signal(str)
    relationCreateRequested = Signal(str, str)
    graphSelectionChanged = Signal(list, list)
    nodeAssignToTreeRequested = Signal(str, str)
    relationCreateRejected = Signal(str)
    ringSelected = Signal(str, str)
    ringFocused = Signal(str, str)
    # BETA1-B01: context-menu intents re-exposed from GraphCanvasView
    contextCreateEntityRequested = Signal()
    contextCreateTreeRequested = Signal()
    contextCreateEntityInTreeRequested = Signal(str)
    contextCreateSubtreeRequested = Signal(str)
    contextDeleteRequested = Signal()
    # BETA1-B02
    escapePressed = Signal()
    # BETA1-B03
    nodeAssignToRingRequested = Signal(str, str)
    ringCreateRequested = Signal()
    ringEditRequested = Signal(str)
    ringDeleteRequested = Signal(str)
    nodeExtractFromTreeRequested = Signal(str)

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self._advanced_mode = bool(ctx.advanced_mode)
        self.ai_controller = None
        stored_mode = str(getattr(ctx, "creation_layout_mode", "free") or "free")
        self._layout_mode = stored_mode if stored_mode in {"free", "layered", "concentric_rings"} else "free"
        self._layer_mode = self._layout_mode == "layered"
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
        self.canvas.ringSelected.connect(self.ringSelected.emit)
        self.canvas.ringFocused.connect(self.ringFocused.emit)
        # BETA1-B01: context-menu intents
        self.canvas.contextCreateEntityRequested.connect(self.contextCreateEntityRequested.emit)
        self.canvas.contextCreateTreeRequested.connect(self.contextCreateTreeRequested.emit)
        self.canvas.contextCreateEntityInTreeRequested.connect(self.contextCreateEntityInTreeRequested.emit)
        self.canvas.contextCreateSubtreeRequested.connect(self.contextCreateSubtreeRequested.emit)
        self.canvas.contextDeleteRequested.connect(self.contextDeleteRequested.emit)
        # BETA1-B02
        self.canvas.escapePressed.connect(self.escapePressed.emit)
        # BETA1-B03
        self.canvas.nodeAssignToRingRequested.connect(self.nodeAssignToRingRequested.emit)
        self.canvas.ringCreateRequested.connect(self.ringCreateRequested.emit)
        self.canvas.ringEditRequested.connect(self.ringEditRequested.emit)
        self.canvas.ringDeleteRequested.connect(self.ringDeleteRequested.emit)
        self.canvas.nodeExtractFromTreeRequested.connect(self.nodeExtractFromTreeRequested.emit)
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

    def search(self, query: str) -> list[GraphSearchResult]:
        project = self._project()
        return self.canvas.search(
            query,
            worldbuilding_active=bool(getattr(project, "worldbuilding_active", False)) if project is not None else False,
        )

    def focus_node(self, entity_id: str) -> bool:
        ok = self.canvas.focus_node(entity_id)
        if ok:
            self._entity_selected(entity_id)
        return ok

    def focus_tree(self, tree_id: str) -> bool:
        ok = self.canvas.focus_tree(tree_id)
        if ok:
            self._entity_selected(tree_id)
        return ok

    def focus_relation(self, relation_id: str) -> bool:
        ok = self.canvas.focus_relation(relation_id)
        if ok:
            self._relation_selected(relation_id)
        return ok

    def center_on_item(self, item):
        self.canvas.center_on_item(item)

    def clear_search_focus(self):
        self.canvas.clear_search_focus()

    def apply_visual_filter(self, filter_state: VisualFilterState):
        self.canvas.apply_visual_filter(filter_state)

    def clear_visual_filters(self):
        self.canvas.clear_visual_filters()

    def get_filter_state(self) -> VisualFilterState:
        return self.canvas.get_filter_state()

    def recompute_edge_visibility(self):
        self.canvas.recompute_edge_visibility()

    def active_filter_count(self) -> int:
        return self.canvas.active_filter_count()

    def focus_tree_scope(self, tree_id: str) -> bool:
        ok = self.canvas.focus_tree_scope(tree_id)
        if ok:
            self._entity_selected(tree_id)
        return ok

    def focus_ring_scope(self, ring_id: str) -> bool:
        _b44trace(f"widget_focus_ring_request ring_id={ring_id!r} layout={self._layout_mode!r}")
        ok = self.canvas.focus_ring_scope(ring_id)
        _b44trace(
            "widget_focus_ring_result "
            f"ok={ok} layout={self._layout_mode!r} canvas_layout={self.canvas._layout_mode_active!r} "
            f"ring_items={len(self.canvas._ring_items)} nodes={len(self.canvas._nodes)}"
        )
        if ok:
            self._layout_mode = "concentric_rings"
            self._layer_mode = False
            self.ctx.creation_layout_mode = "concentric_rings"
            self.ctx.save_preferences()
        return ok

    def focused_ring_id(self) -> str:
        return str(getattr(self.canvas, "_focused_ring_id", ""))

    def active_ring_id(self) -> str:
        return self.canvas.active_ring_id() if hasattr(self.canvas, "active_ring_id") else ""

    def ring_visual_by_id(self, ring_id: str):
        return next((ring for ring in getattr(self.canvas, "_ring_visuals", []) if ring.ring_id == ring_id), None)

    def focus_neighborhood(self, item_id: str) -> bool:
        ok = self.canvas.focus_neighborhood(item_id)
        if ok:
            if item_id in {rel.relation_id for rel in self.canvas._all_edges}:
                self._relation_selected(item_id)
            else:
                self._entity_selected(item_id)
        return ok

    def clear_focus_scope(self):
        self.canvas.clear_focus_scope()
        self.ctx.creation_focused_ring_id = ""
        self.ctx.save_preferences()

    def fit_all(self):
        self.canvas.fit_all()

    def reset_view(self):
        self.canvas.reset_view()

    def center_selection(self) -> bool:
        return self.canvas.center_selection()

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

    def _effective_world_layers(self, project) -> list[Any]:
        """Return visual-only layers for anillo layouts without mutating canon.

        New BETA1 projects can have no `project.world_layers` yet. In that
        state the concentric canvas stays empty until the user explicitly
        creates a ring or applies the suggested template.
        """
        project_layers = list(getattr(project, "world_layers", []) or [])
        defaults = default_world_layers()
        if not project_layers:
            return []

        default_by_id = {str(getattr(layer, "id", "")): layer for layer in defaults}
        effective: list[Any] = []
        for layer in project_layers:
            layer_id = str(getattr(layer, "id", ""))
            default = default_by_id.get(layer_id)
            if default is not None and get_causal_rank(layer) is None and get_causal_rank(default) is not None:
                metadata = dict(getattr(default, "metadata", {}) or {})
                metadata.update(dict(getattr(layer, "metadata", {}) or {}))
                effective.append(replace(layer, metadata=metadata))
            else:
                effective.append(layer)
        return effective

    def refresh(self):
        project = self._project()
        if project is None:
            _b44trace(f"widget_refresh project=None layout={self._layout_mode!r}")
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
        # B40-FIX: do not inject pending AI candidates into the graph canvas as
        # visual nodes. They are not canon, are not removable through the normal
        # entity deletion flow, and in new projects they look like auto-created
        # empty entities. Candidate review/acceptance belongs in the candidate
        # tray or explicit AI suggestion UI; only accepted/canonical entities and
        # relations are rendered here.
        _b44trace(
            "widget_refresh_data "
            f"layout={self._layout_mode!r} entities={len(entities)} relations={len(relations)} "
            f"project_layers={len(getattr(project, 'world_layers', []) or [])} "
            f"canvas_visible_before={self.canvas.isVisible()} empty_visible_before={self.empty.isVisible()}"
        )
        if not entities and self._layout_mode != "concentric_rings":
            self.canvas.clear_graph()
            self.canvas.setVisible(False)
            self.empty.setVisible(True)
            return
        self.empty.setVisible(False)
        self.canvas.setVisible(True)
        # _layer_mode is controlled only by explicit user action (Anillos button).
        # Do NOT derive it from project.worldbuilding_active here — that flag
        # means "worldbuilding feature is available", not "show layer bands".
        layers = self._effective_world_layers(project) if self._layout_mode in {"layered", "concentric_rings"} else []
        _b44trace(
            "widget_refresh_before_set_graph "
            f"layout={self._layout_mode!r} effective_layers={len(layers)} layer_ids={[str(getattr(layer, 'id', '')) for layer in layers]!r}"
        )
        self.canvas.set_graph(entities, relations, layout_mode=self._layout_mode, layers=layers)
        _b44trace(
            "widget_refresh_after_set_graph "
            f"canvas_layout={self.canvas._layout_mode_active!r} canvas_visible={self.canvas.isVisible()} empty_visible={self.empty.isVisible()} "
            f"ring_items={len(self.canvas._ring_items)} ring_visuals={len(self.canvas._ring_visuals)} nodes_drawn={len(self.canvas._nodes)}"
        )

    def set_layout_mode(self, layout_mode: str):
        requested = layout_mode
        if layout_mode not in {"free", "layered", "concentric_rings"}:
            layout_mode = "free"
        _b44trace(
            "widget_set_layout_mode "
            f"requested={requested!r} normalized={layout_mode!r} previous={self._layout_mode!r} "
            f"ctx_previous={getattr(self.ctx, 'creation_layout_mode', '')!r}"
        )
        self._layout_mode = layout_mode
        self._layer_mode = layout_mode == "layered"
        self.ctx.creation_layout_mode = layout_mode
        if layout_mode != "concentric_rings":
            self.ctx.creation_focused_ring_id = ""
            self.canvas.clear_ring_focus()
        self.ctx.save_preferences()
        self.refresh()

    def set_worldbuilding_active(self, active: bool):
        # Compatibility with existing B36 toolbar: this toggles the layered bands
        # view, not the project worldbuilding feature flag.
        self.set_layout_mode("layered" if active else "free")

    def set_advanced_mode(self, enabled: bool):
        self._advanced_mode = bool(enabled)
