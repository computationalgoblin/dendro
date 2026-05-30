"""
Graph view models — read-only derived structures for graph representation.

Provides GraphNode, GraphEdge, GraphPath, GraphFilters, GraphView and
GraphStats.  These are view models in the application layer — they
consume domain entities but never modify them and are never persisted
as a source of truth.

Usage::

    from packages.application.graph_models import (
        GraphNode, GraphEdge, GraphPath, GraphFilters, GraphView, GraphStats,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# GraphNode
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """A node in the graph, derived from a NarrativeEntity."""

    id: str = ""
    label: str = ""                    # entity.name
    entity_type: str = ""              # entity.entity_type.value
    custom_type_id: str | None = None  # entity.custom_type_id
    canon_state: str = ""              # entity.canon_state.value
    visibility_state: str = ""         # entity.visibility_state.value
    domain_ids: list[str] = field(default_factory=list)
    layer_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_archived: bool = False          # canon_state == ARCHIVADO
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "entity_type": self.entity_type,
            "custom_type_id": self.custom_type_id,
            "canon_state": self.canon_state,
            "visibility_state": self.visibility_state,
            "domain_ids": list(self.domain_ids),
            "layer_ids": list(self.layer_ids),
            "tags": list(self.tags),
            "is_archived": self.is_archived,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# GraphEdge
# ---------------------------------------------------------------------------


@dataclass
class GraphEdge:
    """An edge in the graph, derived from a NarrativeRelation."""

    id: str = ""
    source_id: str = ""                # relation.source_id
    target_id: str = ""                # relation.target_id
    label: str = ""                    # relation.relation_type.value
    relation_type: str = ""            # relation.relation_type.value
    custom_relation_type_id: str | None = None
    direction: str = ""                # relation.direction.value
    canon_state: str = ""              # relation.canon_state.value
    visibility_state: str = ""         # relation.visibility_state.value
    intensity: str = ""                # relation.intensity.value
    certainty: str = ""                # relation.certainty_level.value
    layer_ids: list[str] = field(default_factory=list)
    is_archived: bool = False          # canon_state == ARCHIVADO
    is_broken: bool = False            # source or target doesn't exist in project
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "label": self.label,
            "relation_type": self.relation_type,
            "custom_relation_type_id": self.custom_relation_type_id,
            "direction": self.direction,
            "canon_state": self.canon_state,
            "visibility_state": self.visibility_state,
            "intensity": self.intensity,
            "certainty": self.certainty,
            "layer_ids": list(self.layer_ids),
            "is_archived": self.is_archived,
            "is_broken": self.is_broken,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# GraphPath
# ---------------------------------------------------------------------------


@dataclass
class GraphPath:
    """A sequence of nodes and edges forming a path between two entities."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    length: int = 0                    # number of edges
    found: bool = False                # True if a path was found

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "length": self.length,
            "found": self.found,
        }


# ---------------------------------------------------------------------------
# GraphFilters
# ---------------------------------------------------------------------------


@dataclass
class GraphFilters:
    """Filters applied when building a graph view."""

    entity_type: str | None = None
    custom_type_id: str | None = None
    canon_state: str | list[str] | None = None
    visibility_state: str | None = None
    domain_id: str | None = None
    layer_id: str | None = None
    relation_type: str | None = None
    custom_relation_type_id: str | None = None
    include_archived: bool = False
    include_broken: bool = True
    max_nodes: int = 200
    max_edges: int = 500

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "custom_type_id": self.custom_type_id,
            "canon_state": self.canon_state,
            "visibility_state": self.visibility_state,
            "domain_id": self.domain_id,
            "layer_id": self.layer_id,
            "relation_type": self.relation_type,
            "custom_relation_type_id": self.custom_relation_type_id,
            "include_archived": self.include_archived,
            "include_broken": self.include_broken,
            "max_nodes": self.max_nodes,
            "max_edges": self.max_edges,
        }

    def active_filter_labels(self) -> list[str]:
        """Return human-readable labels for non-default filters."""
        labels: list[str] = []
        if self.entity_type:
            labels.append(f"entity_type={self.entity_type}")
        if self.custom_type_id:
            labels.append(f"custom_type_id={self.custom_type_id}")
        if self.canon_state:
            cs = self.canon_state
            if isinstance(cs, list):
                labels.append(f"canon_state=[{','.join(cs)}]")
            else:
                labels.append(f"canon_state={cs}")
        if self.visibility_state:
            labels.append(f"visibility_state={self.visibility_state}")
        if self.domain_id:
            labels.append(f"domain_id={self.domain_id}")
        if self.layer_id:
            labels.append(f"layer_id={self.layer_id}")
        if self.relation_type:
            labels.append(f"relation_type={self.relation_type}")
        if self.custom_relation_type_id:
            labels.append(f"custom_relation_type_id={self.custom_relation_type_id}")
        if self.include_archived:
            labels.append("include_archived")
        if not self.include_broken:
            labels.append("exclude_broken")
        return labels


# ---------------------------------------------------------------------------
# GraphView
# ---------------------------------------------------------------------------


@dataclass
class GraphView:
    """A filtered view of the graph with nodes, edges and metadata."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    hidden_node_count: int = 0
    hidden_edge_count: int = 0
    filters_applied: list[str] = field(default_factory=list)
    stats: GraphStats | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "hidden_node_count": self.hidden_node_count,
            "hidden_edge_count": self.hidden_edge_count,
            "filters_applied": list(self.filters_applied),
            "stats": self.stats.to_dict() if self.stats else None,
        }


# ---------------------------------------------------------------------------
# GraphStats
# ---------------------------------------------------------------------------


@dataclass
class GraphStats:
    """Statistics about the current graph view.

    Terminology:
    - candidate: after main filters, before max_nodes/max_edges truncation
    - visible: included in GraphView.nodes/edges (after truncation)
    - hidden: candidates omitted by max_nodes/max_edges truncation
    - broken: edge endpoint doesn't exist in project (not filtered-out)
    """

    candidate_nodes: int = 0
    candidate_edges: int = 0
    visible_nodes: int = 0
    visible_edges: int = 0
    hidden_nodes: int = 0
    hidden_edges: int = 0
    archived_nodes: int = 0
    archived_edges: int = 0
    broken_edges: int = 0
    active_nodes: int = 0
    active_edges: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_nodes": self.candidate_nodes,
            "candidate_edges": self.candidate_edges,
            "visible_nodes": self.visible_nodes,
            "visible_edges": self.visible_edges,
            "hidden_nodes": self.hidden_nodes,
            "hidden_edges": self.hidden_edges,
            "archived_nodes": self.archived_nodes,
            "archived_edges": self.archived_edges,
            "broken_edges": self.broken_edges,
            "active_nodes": self.active_nodes,
            "active_edges": self.active_edges,
        }


__all__ = [
    "GraphNode",
    "GraphEdge",
    "GraphPath",
    "GraphFilters",
    "GraphView",
    "GraphStats",
]
