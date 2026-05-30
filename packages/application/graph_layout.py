"""
Graph layout — deterministic positioning for graph nodes (B11-T04).

Provides circular and by_type layouts. No external dependencies beyond
Python stdlib math. Output is JSON-serializable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from packages.application.graph_models import GraphView

# ---------------------------------------------------------------------------
# Layout models
# ---------------------------------------------------------------------------


@dataclass
class GraphLayoutNode:
    """A node with a position in 2D space."""
    id: str = ""
    x: float = 0.0
    y: float = 0.0
    group: str = ""         # entity_type, domain_id, or layer_id
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "x": self.x, "y": self.y,
            "group": self.group, "label": self.label,
        }


@dataclass
class GraphLayoutEdge:
    """An edge with start and end positions."""
    id: str = ""
    source_id: str = ""
    target_id: str = ""
    source_x: float = 0.0
    source_y: float = 0.0
    target_x: float = 0.0
    target_y: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "source_id": self.source_id,
            "target_id": self.target_id,
            "source_x": self.source_x, "source_y": self.source_y,
            "target_x": self.target_x, "target_y": self.target_y,
        }


@dataclass
class GraphLayout:
    """Complete layout with nodes, edges and canvas dimensions."""
    nodes: list[GraphLayoutNode] = field(default_factory=list)
    edges: list[GraphLayoutEdge] = field(default_factory=list)
    width: float = 800.0
    height: float = 600.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "width": self.width, "height": self.height,
        }


# ---------------------------------------------------------------------------
# Layout algorithms
# ---------------------------------------------------------------------------


def layout_circular(
    graph_view: GraphView, radius: float = 300.0,
) -> GraphLayout:
    """Distribute nodes evenly on a circle. Deterministic: same input → same output."""
    nodes = graph_view.nodes
    n = len(nodes)
    angle_step = 2 * math.pi / max(n, 1)
    center_x = radius + 50
    center_y = radius + 50

    layout_nodes: list[GraphLayoutNode] = []
    for i, node in enumerate(nodes):
        angle = i * angle_step
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        layout_nodes.append(GraphLayoutNode(
            id=node.id, x=round(x, 2), y=round(y, 2),
            group=node.entity_type, label=node.label,
        ))

    # Build edges with positions
    node_positions = {ln.id: (ln.x, ln.y) for ln in layout_nodes}
    layout_edges: list[GraphLayoutEdge] = []
    for edge in graph_view.edges:
        sx, sy = node_positions.get(edge.source_id, (0.0, 0.0))
        tx, ty = node_positions.get(edge.target_id, (0.0, 0.0))
        layout_edges.append(GraphLayoutEdge(
            id=edge.id, source_id=edge.source_id, target_id=edge.target_id,
            source_x=sx, source_y=sy, target_x=tx, target_y=ty,
        ))

    return GraphLayout(
        nodes=layout_nodes, edges=layout_edges,
        width=2 * radius + 100, height=2 * radius + 100,
    )


def layout_by_type(
    graph_view: GraphView, group_by: str = "type",
    spacing: float = 150.0,
) -> GraphLayout:
    """Group nodes in columns by entity_type (or domain_id/layer_id).

    Deterministic: stable sort by id within each group.
    """
    nodes = sorted(graph_view.nodes, key=lambda n: n.id)

    # Determine group key
    def _group_key(node):
        if group_by == "domain_id":
            return node.domain_ids[0] if node.domain_ids else "sin_dominio"
        elif group_by == "layer_id":
            return node.layer_ids[0] if node.layer_ids else "sin_capa"
        return node.entity_type

    # Group nodes
    groups: dict[str, list] = {}
    for node in nodes:
        key = _group_key(node)
        groups.setdefault(key, []).append(node)

    layout_nodes: list[GraphLayoutNode] = []
    col = 0
    max_y = 0.0

    for group_name in sorted(groups.keys()):
        group_nodes = groups[group_name]
        x = col * spacing + 50
        for row, node in enumerate(group_nodes):
            y = row * 80 + 50
            max_y = max(max_y, y + 80)
            layout_nodes.append(GraphLayoutNode(
                id=node.id, x=float(x), y=float(y),
                group=group_name, label=node.label,
            ))
        col += 1

    node_positions = {ln.id: (ln.x, ln.y) for ln in layout_nodes}
    layout_edges: list[GraphLayoutEdge] = []
    for edge in graph_view.edges:
        sx, sy = node_positions.get(edge.source_id, (0.0, 0.0))
        tx, ty = node_positions.get(edge.target_id, (0.0, 0.0))
        layout_edges.append(GraphLayoutEdge(
            id=edge.id, source_id=edge.source_id, target_id=edge.target_id,
            source_x=sx, source_y=sy, target_x=tx, target_y=ty,
        ))

    return GraphLayout(
        nodes=layout_nodes, edges=layout_edges,
        width=col * spacing + 100, height=max_y + 50,
    )


__all__ = [
    "GraphLayout", "GraphLayoutNode", "GraphLayoutEdge",
    "layout_circular", "layout_by_type",
]
