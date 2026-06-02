"""
Graph view models — read-only derived structures for graph representation.

Provides base B11 graph view models plus B28 specialized graph contracts.
These are application-layer view models: they are derived from the core and
are not a source of canonical narrative data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class GraphViewType(str, Enum):
    """Specialized graph views required by Bloque 28."""

    GLOBAL = "global"
    PERSONAJE = "personaje"
    LOCALIZACION = "localizacion"
    FACCION = "faccion"
    CONFLICTO = "conflicto"
    SECRETOS = "secretos"
    PISTAS = "pistas"
    CRONOLOGIA = "cronologia"
    CAUSAL = "causal"
    CAMPANA = "campana"
    SESION = "sesion"
    CONOCIMIENTO = "conocimiento"
    ESTRUCTURA_NARRATIVA = "estructura_narrativa"
    INCONSISTENCIAS = "inconsistencias"
    CAPAS = "capas"


class GraphOverlay(str, Enum):
    """Optional read-only overlays for graph views."""

    ISSUES = "issues"
    CANDIDATES = "candidates"
    SECRETS = "secrets"
    CLUES = "clues"
    REVELATIONS = "revelations"


@dataclass
class GraphScope:
    """Scope for a graph view. IDs are references to existing core objects."""

    scope_type: str = "project"
    ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"scope_type": self.scope_type, "ids": list(self.ids)}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GraphScope:
        if not isinstance(data, dict):
            return cls()
        raw_ids = data.get("ids", [])
        return cls(
            scope_type=str(data.get("scope_type", "project")),
            ids=[str(i) for i in raw_ids] if isinstance(raw_ids, list) else [],
        )


@dataclass
class GraphNode:
    """A node in the graph, derived from a NarrativeEntity."""

    id: str = ""
    label: str = ""
    entity_type: str = ""
    custom_type_id: str | None = None
    canon_state: str = ""
    visibility_state: str = ""
    domain_ids: list[str] = field(default_factory=list)
    layer_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_archived: bool = False
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


@dataclass
class GraphEdge:
    """An edge in the graph, derived from a NarrativeRelation."""

    id: str = ""
    source_id: str = ""
    target_id: str = ""
    label: str = ""
    relation_type: str = ""
    custom_relation_type_id: str | None = None
    direction: str = ""
    canon_state: str = ""
    visibility_state: str = ""
    intensity: str = ""
    certainty: str = ""
    layer_ids: list[str] = field(default_factory=list)
    is_archived: bool = False
    is_broken: bool = False
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


@dataclass
class GraphPath:
    """A sequence of nodes and edges forming a path between two entities."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    length: int = 0
    found: bool = False
    path_type: str = "generic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "length": self.length,
            "found": self.found,
            "path_type": self.path_type,
        }


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
    view_type: GraphViewType | str = GraphViewType.GLOBAL
    scope: GraphScope | dict[str, Any] | None = None
    overlays: list[GraphOverlay | str] = field(default_factory=list)
    audience: str = "author"
    campaign_id: str | None = None
    session_id: str | None = None

    def normalized_view_type(self) -> GraphViewType:
        if isinstance(self.view_type, GraphViewType):
            return self.view_type
        try:
            return GraphViewType(str(self.view_type))
        except ValueError:
            return GraphViewType.GLOBAL

    def normalized_scope(self) -> GraphScope:
        if isinstance(self.scope, GraphScope):
            return self.scope
        if isinstance(self.scope, dict):
            return GraphScope.from_dict(self.scope)
        return GraphScope()

    def normalized_overlays(self) -> list[GraphOverlay]:
        result: list[GraphOverlay] = []
        for overlay in self.overlays:
            if isinstance(overlay, GraphOverlay):
                result.append(overlay)
                continue
            try:
                result.append(GraphOverlay(str(overlay)))
            except ValueError:
                continue
        return result

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
            "view_type": self.normalized_view_type().value,
            "scope": self.normalized_scope().to_dict(),
            "overlays": [o.value for o in self.normalized_overlays()],
            "audience": self.audience,
            "campaign_id": self.campaign_id,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GraphFilters:
        if not isinstance(data, dict):
            return cls()
        return cls(
            entity_type=data.get("entity_type"),
            custom_type_id=data.get("custom_type_id"),
            canon_state=data.get("canon_state"),
            visibility_state=data.get("visibility_state"),
            domain_id=data.get("domain_id"),
            layer_id=data.get("layer_id"),
            relation_type=data.get("relation_type"),
            custom_relation_type_id=data.get("custom_relation_type_id"),
            include_archived=bool(data.get("include_archived", False)),
            include_broken=bool(data.get("include_broken", True)),
            max_nodes=int(data.get("max_nodes", 200) or 200),
            max_edges=int(data.get("max_edges", 500) or 500),
            view_type=data.get("view_type", GraphViewType.GLOBAL.value),
            scope=GraphScope.from_dict(data.get("scope")),
            overlays=list(data.get("overlays", [])) if isinstance(data.get("overlays", []), list) else [],
            audience=str(data.get("audience", "author")),
            campaign_id=data.get("campaign_id"),
            session_id=data.get("session_id"),
        )

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
        if self.normalized_view_type() != GraphViewType.GLOBAL:
            labels.append(f"view_type={self.normalized_view_type().value}")
        if self.audience != "author":
            labels.append(f"audience={self.audience}")
        if self.campaign_id:
            labels.append(f"campaign_id={self.campaign_id}")
        if self.session_id:
            labels.append(f"session_id={self.session_id}")
        return labels


@dataclass
class GraphStats:
    """Statistics about the current graph view."""

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


@dataclass
class GraphView:
    """A filtered view of the graph with nodes, edges and metadata."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    hidden_node_count: int = 0
    hidden_edge_count: int = 0
    filters_applied: list[str] = field(default_factory=list)
    stats: GraphStats | None = None
    view_type: GraphViewType | str = GraphViewType.GLOBAL
    scope: GraphScope | dict[str, Any] | None = None
    overlays: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    clusters: dict[str, list[str]] = field(default_factory=dict)

    def normalized_view_type(self) -> GraphViewType:
        if isinstance(self.view_type, GraphViewType):
            return self.view_type
        try:
            return GraphViewType(str(self.view_type))
        except ValueError:
            return GraphViewType.GLOBAL

    def normalized_scope(self) -> GraphScope:
        if isinstance(self.scope, GraphScope):
            return self.scope
        if isinstance(self.scope, dict):
            return GraphScope.from_dict(self.scope)
        return GraphScope()

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "hidden_node_count": self.hidden_node_count,
            "hidden_edge_count": self.hidden_edge_count,
            "filters_applied": list(self.filters_applied),
            "stats": self.stats.to_dict() if self.stats else None,
            "view_type": self.normalized_view_type().value,
            "scope": self.normalized_scope().to_dict(),
            "overlays": {k: [dict(item) for item in v] for k, v in self.overlays.items()},
            "clusters": {k: list(v) for k, v in self.clusters.items()},
        }


@dataclass
class SavedGraphView:
    """Persisted graph view configuration only; no derived nodes or edges."""

    name: str
    id: str = field(default_factory=lambda: f"gv_{uuid4().hex[:8]}")
    filters: GraphFilters = field(default_factory=GraphFilters)
    scope: GraphScope = field(default_factory=GraphScope)
    overlays: list[GraphOverlay | str] = field(default_factory=list)
    layout_preferences: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        filters = self.filters.to_dict()
        if self.scope.scope_type != "project" or self.scope.ids:
            filters["scope"] = self.scope.to_dict()
        overlay_values = []
        for overlay in self.overlays:
            try:
                overlay_values.append((overlay if isinstance(overlay, GraphOverlay) else GraphOverlay(str(overlay))).value)
            except ValueError:
                continue
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "filters": filters,
            "scope": self.scope.to_dict(),
            "overlays": overlay_values,
            "layout_preferences": dict(self.layout_preferences),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SavedGraphView:
        filters = GraphFilters.from_dict(data.get("filters", {}))
        scope = GraphScope.from_dict(data.get("scope") or filters.to_dict().get("scope"))
        overlays = data.get("overlays", filters.to_dict().get("overlays", []))
        return cls(
            id=str(data.get("id") or f"gv_{uuid4().hex[:8]}"),
            name=str(data.get("name") or ""),
            description=str(data.get("description", "")),
            filters=filters,
            scope=scope,
            overlays=list(overlays) if isinstance(overlays, list) else [],
            layout_preferences=dict(data.get("layout_preferences", {}))
            if isinstance(data.get("layout_preferences", {}), dict) else {},
        )


@dataclass
class GraphComparisonChange:
    """A derived difference between two graph views."""

    id: str
    kind: str
    changes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "changes": dict(self.changes)}


@dataclass
class GraphComparison:
    """Derived comparison between two graph views."""

    view_a_id: str = ""
    view_b_id: str = ""
    added_nodes: list[GraphComparisonChange] = field(default_factory=list)
    removed_nodes: list[GraphComparisonChange] = field(default_factory=list)
    changed_nodes: list[GraphComparisonChange] = field(default_factory=list)
    added_edges: list[GraphComparisonChange] = field(default_factory=list)
    removed_edges: list[GraphComparisonChange] = field(default_factory=list)
    changed_edges: list[GraphComparisonChange] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "view_a_id": self.view_a_id,
            "view_b_id": self.view_b_id,
            "added_nodes": [c.to_dict() for c in self.added_nodes],
            "removed_nodes": [c.to_dict() for c in self.removed_nodes],
            "changed_nodes": [c.to_dict() for c in self.changed_nodes],
            "added_edges": [c.to_dict() for c in self.added_edges],
            "removed_edges": [c.to_dict() for c in self.removed_edges],
            "changed_edges": [c.to_dict() for c in self.changed_edges],
        }


__all__ = [
    "GraphViewType",
    "GraphOverlay",
    "GraphScope",
    "GraphNode",
    "GraphEdge",
    "GraphPath",
    "GraphFilters",
    "GraphView",
    "GraphStats",
    "SavedGraphView",
    "GraphComparisonChange",
    "GraphComparison",
]
