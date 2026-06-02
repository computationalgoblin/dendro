"""
GraphService — builds filtered graph views from existing entities and relations.

Consumes QueryService, RelationService and EntityService exclusively.
Stateless: every call builds the graph from scratch from the active project.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from packages.application.graph_models import (
    GraphComparison,
    GraphComparisonChange,
    GraphEdge,
    GraphFilters,
    GraphNode,
    GraphOverlay,
    GraphPath,
    GraphStats,
    GraphView,
    GraphViewType,
)
from packages.domain.entity import CanonState, VisibilityState
from packages.domain.result import Error, Ok, Result

logger = logging.getLogger("narrative-architect.graph")


@dataclass
class GraphService:
    """Stateless service that builds graph views from the active project."""

    query_service: Any       # QueryService
    relation_service: Any    # RelationService
    entity_service: Any      # EntityService

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_graph(
        self, filters: GraphFilters | None = None,
    ) -> Result[GraphView, str]:
        """Build a full GraphView with all visible nodes and edges."""
        gf = filters or GraphFilters()

        # 1. Get candidate entities
        entities_result = self._fetch_entities(gf)
        if isinstance(entities_result, Error):
            return Error(entities_result.error)
        entities = entities_result.value

        # 2. Build valid entity ID set + count archived across all entities
        proj = self.entity_service._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        all_entities = proj.value.entities
        all_entity_ids = {e.id for e in all_entities}
        archived_node_count = sum(
            1 for e in all_entities
            if e.canon_state == CanonState.ARCHIVADO
        )

        # 3. Filter archived from visible if needed
        if not gf.include_archived:
            entities = [e for e in entities
                        if e.canon_state != CanonState.ARCHIVADO]

        # 4. Build nodes (candidates)
        candidate_nodes = [self._entity_to_node(e) for e in entities]
        candidate_count = len(candidate_nodes)

        # 5. Build edges from visible entity relationships
        visible_ids = {e.id for e in entities}
        all_edges = self._fetch_edges(visible_ids, all_entity_ids, gf)
        candidate_edge_count = len(all_edges)

        # 6. Apply max limits
        nodes = candidate_nodes[:gf.max_nodes]
        edges = all_edges[:gf.max_edges]
        hidden_nodes = max(0, candidate_count - len(nodes))
        hidden_edges = max(0, candidate_edge_count - len(edges))

        # 7. Build stats (use pre-filter archived count from step 2)
        archived_edge_count = sum(1 for e in all_edges if e.is_archived)
        broken_edge_count = sum(1 for e in all_edges if e.is_broken)

        stats = GraphStats(
            candidate_nodes=candidate_count,
            candidate_edges=candidate_edge_count,
            visible_nodes=len(nodes),
            visible_edges=len(edges),
            hidden_nodes=hidden_nodes,
            hidden_edges=hidden_edges,
            archived_nodes=archived_node_count,
            archived_edges=archived_edge_count,
            broken_edges=broken_edge_count,
            active_nodes=candidate_count - archived_node_count,
            active_edges=candidate_edge_count - archived_edge_count - broken_edge_count,
        )

        return Ok(GraphView(
            nodes=nodes,
            edges=edges,
            hidden_node_count=hidden_nodes,
            hidden_edge_count=hidden_edges,
            filters_applied=gf.active_filter_labels(),
            stats=stats,
        ))

    def build_entity_neighborhood(
        self, entity_id: str, depth: int = 1,
        filters: GraphFilters | None = None,
    ) -> Result[GraphView, str]:
        """Build a graph centered on one entity with its neighborhood."""
        gf = filters or GraphFilters()

        # Check entity exists
        entity_result = self.entity_service.get_by_id(entity_id)
        if isinstance(entity_result, Error):
            return Error(f"Entity '{entity_id}' not found")

        entity = entity_result.value

        # Check archived
        if entity.canon_state == CanonState.ARCHIVADO and not gf.include_archived:
            return Error(
                f"Entity '{entity_id}' is archived; use include_archived=True"
            )

        # Build the center node (always included)
        center_node = self._entity_to_node(entity)

        # Collect neighbor IDs at each depth level
        visited_ids: set[str] = {entity_id}
        current_ids: set[str] = {entity_id}
        all_neighbor_entities: dict[str, Any] = {}
        all_neighbor_edges: list[GraphEdge] = []

        proj = self.entity_service._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        all_entity_ids = {e.id for e in proj.value.entities}

        for _ in range(depth):
            next_ids: set[str] = set()
            for eid in current_ids:
                incoming = self.relation_service.get_incoming(eid)
                outgoing = self.relation_service.get_outgoing(eid)
                relations = (
                    (incoming.value if not isinstance(incoming, Error) else []) +
                    (outgoing.value if not isinstance(outgoing, Error) else [])
                )
                for rel in relations:
                    edge = self._relation_to_edge(rel, all_entity_ids, gf)
                    neighbor_id = (
                        rel.source_id if rel.source_id != eid else rel.target_id
                    )
                    if neighbor_id not in visited_ids:
                        next_ids.add(neighbor_id)
                        # Fetch neighbor entity
                        ent_r = self.entity_service.get_by_id(neighbor_id)
                        if not isinstance(ent_r, Error):
                            # Apply filters to neighbors (not center)
                            if self._entity_passes_filters(ent_r.value, gf):
                                all_neighbor_entities[neighbor_id] = ent_r.value
                    if neighbor_id in all_neighbor_entities or neighbor_id == entity_id:
                        all_neighbor_edges.append(edge)
            visited_ids.update(next_ids)
            current_ids = next_ids

        # Build nodes: center + filtered neighbors
        nodes = [center_node]
        for e in all_neighbor_entities.values():
            nodes.append(self._entity_to_node(e))

        stats = GraphStats(
            candidate_nodes=len(nodes),
            visible_nodes=len(nodes),
            active_nodes=len(nodes),
            candidate_edges=len(all_neighbor_edges),
            visible_edges=len(all_neighbor_edges),
            active_edges=len(all_neighbor_edges),
        )

        return Ok(GraphView(
            nodes=nodes, edges=all_neighbor_edges,
            filters_applied=gf.active_filter_labels(), stats=stats,
        ))

    def build_path_between(
        self, source_id: str, target_id: str,
        max_depth: int = 5, filters: GraphFilters | None = None,
    ) -> Result[GraphPath, str]:
        """Find a path between two entities."""
        gf = filters or GraphFilters()

        # Check both entities exist
        for eid, label in [(source_id, "Source"), (target_id, "Target")]:
            er = self.entity_service.get_by_id(eid)
            if isinstance(er, Error):
                return Error(f"{label} entity '{eid}' not found")

        # Get raw paths from RelationService
        paths_result = self.relation_service.find_simple_paths(
            source_id, target_id, max_depth,
        )
        if isinstance(paths_result, Error):
            return Error(f"Path search failed: {paths_result.error}")

        raw_paths = paths_result.value
        if not raw_paths:
            return Ok(GraphPath(found=False))

        proj = self.entity_service._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        all_entity_ids = {e.id for e in proj.value.entities}

        # Try each path until one passes filters
        for path_data in raw_paths:
            # path_data is expected to be a list of relation IDs or dicts
            if not path_data:
                continue

            nodes, edges = self._resolve_path(path_data, all_entity_ids, gf)
            if nodes is not None:
                return Ok(GraphPath(
                    nodes=nodes, edges=edges,
                    length=len(edges), found=True,
                ))

        return Ok(GraphPath(found=False))

    def _resolve_path(
        self, path_data: list, all_entity_ids: set[str], gf: GraphFilters,
    ) -> tuple[list[GraphNode], list[GraphEdge]] | tuple[None, None]:
        """Resolve a raw path into nodes and edges. Returns (None, None) if
        any node/edge fails filter checks."""
        edges: list[GraphEdge] = []
        node_ids_ordered: list[str] = []

        for item in path_data:
            if isinstance(item, str):
                # It's a relation ID — resolve it
                rel_r = self.relation_service.get_by_id(item)
                if isinstance(rel_r, Error):
                    return None, None
                rel = rel_r.value
                edge = self._relation_to_edge(rel, all_entity_ids, gf)
                if not self._edge_passes_filters(edge, gf):
                    return None, None
                edges.append(edge)
                if not node_ids_ordered:
                    node_ids_ordered.append(rel.source_id)
                node_ids_ordered.append(rel.target_id)
            elif hasattr(item, "id"):
                # It's already a relation object
                edge = self._relation_to_edge(item, all_entity_ids, gf)
                if not self._edge_passes_filters(edge, gf):
                    return None, None
                edges.append(edge)
                if not node_ids_ordered:
                    node_ids_ordered.append(item.source_id)
                node_ids_ordered.append(item.target_id)

        # Resolve nodes
        nodes: list[GraphNode] = []
        seen: set[str] = set()
        for nid in node_ids_ordered:
            if nid in seen:
                continue
            seen.add(nid)
            er = self.entity_service.get_by_id(nid)
            if isinstance(er, Error):
                return None, None
            nodes.append(self._entity_to_node(er.value))

        return nodes, edges

    def get_graph_stats(
        self, filters: GraphFilters | None = None,
    ) -> Result[GraphStats, str]:
        """Get stats without building the full graph."""
        result = self.build_graph(filters)
        if isinstance(result, Error):
            return Error(result.error)
        stats = result.value.stats
        if stats is None:
            return Ok(GraphStats())
        return Ok(stats)

    def build_specialized_graph(
        self, filters: GraphFilters | None = None,
    ) -> Result[GraphView, str]:
        """Build a B28 specialized graph view.

        The result is always derived from current core entities/relations.
        Overlays are read-only metadata and never accept candidates, resolve
        issues, reveal secrets, or persist graph data.
        """
        gf = filters or GraphFilters()
        scoped = self._specialized_filters(gf)
        result = self.build_graph(scoped)
        if isinstance(result, Error):
            return Error(result.error)

        view = result.value
        view.view_type = gf.normalized_view_type()
        view.scope = gf.normalized_scope()
        view.clusters = self._build_clusters(view)
        overlays_result = self._build_overlays(gf, {n.id for n in view.nodes})
        if isinstance(overlays_result, Error):
            return Error(overlays_result.error)
        view.overlays = overlays_result.value
        return Ok(view)

    def compare_graph_views(
        self,
        view_a: GraphView,
        view_b: GraphView,
        view_a_id: str = "",
        view_b_id: str = "",
    ) -> Result[GraphComparison, str]:
        """Compare two derived graph views without storing canonical snapshots."""
        a_nodes = {n.id: n.to_dict() for n in view_a.nodes}
        b_nodes = {n.id: n.to_dict() for n in view_b.nodes}
        a_edges = {e.id: e.to_dict() for e in view_a.edges}
        b_edges = {e.id: e.to_dict() for e in view_b.edges}

        return Ok(GraphComparison(
            view_a_id=view_a_id,
            view_b_id=view_b_id,
            added_nodes=[GraphComparisonChange(id=i, kind="node") for i in sorted(b_nodes.keys() - a_nodes.keys())],
            removed_nodes=[GraphComparisonChange(id=i, kind="node") for i in sorted(a_nodes.keys() - b_nodes.keys())],
            changed_nodes=[
                GraphComparisonChange(id=i, kind="node", changes=self._diff_dicts(a_nodes[i], b_nodes[i]))
                for i in sorted(a_nodes.keys() & b_nodes.keys())
                if self._diff_dicts(a_nodes[i], b_nodes[i])
            ],
            added_edges=[GraphComparisonChange(id=i, kind="edge") for i in sorted(b_edges.keys() - a_edges.keys())],
            removed_edges=[GraphComparisonChange(id=i, kind="edge") for i in sorted(a_edges.keys() - b_edges.keys())],
            changed_edges=[
                GraphComparisonChange(id=i, kind="edge", changes=self._diff_dicts(a_edges[i], b_edges[i]))
                for i in sorted(a_edges.keys() & b_edges.keys())
                if self._diff_dicts(a_edges[i], b_edges[i])
            ],
        ))

    def graph_view_from_dict(self, data: dict[str, Any]) -> GraphView:
        """Reconstruct a GraphView from exported view data for comparison."""
        nodes = [GraphNode(**self._node_kwargs(n)) for n in data.get("nodes", []) if isinstance(n, dict)]
        edges = [GraphEdge(**self._edge_kwargs(e)) for e in data.get("edges", []) if isinstance(e, dict)]
        return GraphView(nodes=nodes, edges=edges)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_entities(self, gf: GraphFilters) -> Result[list, str]:
        """Fetch entities via QueryService with filters applied."""
        return self.query_service.query(
            entity_type=gf.entity_type,
            canon_state=gf.canon_state,
            visibility_state=gf.visibility_state,
            custom_type_id=gf.custom_type_id,
            domain=gf.domain_id,
            layer=gf.layer_id,
            limit=gf.max_nodes * 2,  # fetch more than max for accurate hidden count
        )

    def _fetch_edges(
        self, visible_ids: set[str], all_entity_ids: set[str],
        gf: GraphFilters,
    ) -> list[GraphEdge]:
        """Fetch edges for visible entities, applying edge filters."""
        edges: list[GraphEdge] = []
        seen_edge_ids: set[str] = set()

        for eid in visible_ids:
            incoming = self.relation_service.get_incoming(eid)
            outgoing = self.relation_service.get_outgoing(eid)
            relations = (
                (incoming.value if not isinstance(incoming, Error) else []) +
                (outgoing.value if not isinstance(outgoing, Error) else [])
            )
            for rel in relations:
                if rel.id in seen_edge_ids:
                    continue
                seen_edge_ids.add(rel.id)
                edge = self._relation_to_edge(rel, all_entity_ids, gf)
                if self._edge_passes_filters(edge, gf):
                    edges.append(edge)

        return edges

    def _entity_to_node(self, entity: Any) -> GraphNode:
        """Convert a NarrativeEntity to a GraphNode."""
        return GraphNode(
            id=entity.id,
            label=entity.name,
            entity_type=entity.entity_type.value,
            custom_type_id=entity.custom_type_id,
            canon_state=entity.canon_state.value,
            visibility_state=entity.visibility_state.value,
            domain_ids=list(getattr(entity, "domain_ids", [])),
            layer_ids=list(getattr(entity, "layer_ids", [])),
            tags=list(entity.tags),
            is_archived=(entity.canon_state == CanonState.ARCHIVADO),
            metadata={"brief": entity.brief_description[:100]},
        )

    def _relation_to_edge(
        self, relation: Any, all_entity_ids: set[str], gf: GraphFilters,
    ) -> GraphEdge:
        """Convert a NarrativeRelation to a GraphEdge."""
        is_broken = (
            relation.source_id not in all_entity_ids or
            relation.target_id not in all_entity_ids
        )
        return GraphEdge(
            id=relation.id,
            source_id=relation.source_id,
            target_id=relation.target_id,
            label=relation.relation_type.value,
            relation_type=relation.relation_type.value,
            custom_relation_type_id=relation.custom_relation_type_id,
            direction=relation.direction.value,
            canon_state=relation.canon_state.value,
            visibility_state=relation.visibility_state.value,
            intensity=relation.intensity.value,
            certainty=relation.certainty_level.value,
            layer_ids=list(getattr(relation, "layer_ids", [])),
            is_archived=(relation.canon_state == CanonState.ARCHIVADO),
            is_broken=is_broken,
            metadata={"desc": relation.description[:100]},
        )

    def _entity_passes_filters(self, entity: Any, gf: GraphFilters) -> bool:
        """Check if an entity passes non-QueryService filters."""
        if not gf.include_archived and entity.canon_state == CanonState.ARCHIVADO:
            return False
        if gf.visibility_state and entity.visibility_state.value != gf.visibility_state:
            return False
        return True

    def _edge_passes_filters(self, edge: GraphEdge, gf: GraphFilters) -> bool:
        """Check if an edge passes filters."""
        if edge.is_broken and not gf.include_broken:
            return False
        if edge.is_archived and not gf.include_archived:
            return False
        if gf.relation_type and edge.relation_type != gf.relation_type:
            return False
        crt_id = gf.custom_relation_type_id
        if crt_id and edge.custom_relation_type_id != crt_id:
            return False
        return True

    def _specialized_filters(self, gf: GraphFilters) -> GraphFilters:
        """Translate a specialized view contract into core graph filters."""
        data = gf.to_dict()
        scoped = GraphFilters.from_dict(data)
        view_type = gf.normalized_view_type()
        entity_type_map = {
            GraphViewType.PERSONAJE: "personaje",
            GraphViewType.LOCALIZACION: "localizacion",
            GraphViewType.FACCION: "faccion",
            GraphViewType.CONFLICTO: "conflicto",
            GraphViewType.SECRETOS: "secreto",
            GraphViewType.PISTAS: "pista",
            GraphViewType.SESION: "sesion",
        }
        if not scoped.entity_type and view_type in entity_type_map:
            scoped.entity_type = entity_type_map[view_type]
        if scoped.audience in {"player", "public"}:
            scoped.visibility_state = VisibilityState.VISIBLE_JUGADORES.value
        return scoped

    def _build_clusters(self, view: GraphView) -> dict[str, list[str]]:
        """Build derived visual clusters; never stores semantic truth."""
        clusters: dict[str, list[str]] = {}
        for node in view.nodes:
            for domain_id in node.domain_ids:
                clusters.setdefault(f"domain:{domain_id}", []).append(node.id)
            for layer_id in node.layer_ids:
                clusters.setdefault(f"layer:{layer_id}", []).append(node.id)
            if node.entity_type:
                clusters.setdefault(f"type:{node.entity_type}", []).append(node.id)

        proj = self.entity_service._active_project() if self.entity_service else Error("No entity service")
        if not isinstance(proj, Error):
            visible_ids = {n.id for n in view.nodes}
            for faction in getattr(proj.value, "factions", []):
                entity_id = getattr(faction, "entity_id", None)
                if entity_id in visible_ids:
                    clusters.setdefault(f"faction:{getattr(faction, 'id', '')}", []).append(entity_id)
        return clusters

    def _build_overlays(
        self,
        gf: GraphFilters,
        visible_node_ids: set[str],
    ) -> Result[dict[str, list[dict[str, Any]]], str]:
        proj = self.entity_service._active_project() if self.entity_service else Error("No entity service")
        if isinstance(proj, Error):
            return Error(proj.error)
        overlays: dict[str, list[dict[str, Any]]] = {}
        requested = {o.value for o in gf.normalized_overlays()}
        audience = gf.audience

        if GraphOverlay.ISSUES.value in requested:
            overlays["issues"] = [
                item.to_dict() for item in getattr(proj.value, "issues", [])
                if self._references_visible_node(item, visible_node_ids)
            ]
        if GraphOverlay.CANDIDATES.value in requested:
            overlays["candidates"] = [
                item.to_dict() for item in getattr(proj.value, "candidates", [])
                if self._references_visible_node(item, visible_node_ids)
            ]
        if GraphOverlay.SECRETS.value in requested:
            secrets = []
            for item in getattr(proj.value, "secrets", []):
                if audience in {"player", "public"} and getattr(getattr(item, "revelation_state", None), "value", "") != "revelado":
                    continue
                data = item.to_dict()
                if audience in {"player", "public"}:
                    data.pop("content", None)
                    data.pop("concealment_consequences", None)
                secrets.append(data)
            overlays["secrets"] = secrets
        if GraphOverlay.CLUES.value in requested:
            clues = []
            for item in getattr(proj.value, "clues", []):
                if audience in {"player", "public"} and getattr(getattr(item, "delivery_state", None), "value", "") != "entregada":
                    continue
                data = item.to_dict()
                if audience in {"player", "public"}:
                    data.pop("content", None)
                    data.pop("probable_interpretation", None)
                    data.pop("possible_misinterpretations", None)
                clues.append(data)
            overlays["clues"] = clues
        return Ok(overlays)

    def _references_visible_node(self, item: Any, visible_node_ids: set[str]) -> bool:
        entity_ids = set(getattr(item, "affected_entity_ids", []) or [])
        single = getattr(item, "affected_entity_id", None)
        if single:
            entity_ids.add(single)
        if not entity_ids:
            return True
        return bool(entity_ids & visible_node_ids)

    def _diff_dicts(self, old: dict[str, Any], new: dict[str, Any]) -> dict[str, list[Any]]:
        changes: dict[str, list[Any]] = {}
        ignored = {"metadata"}
        for key in sorted((old.keys() | new.keys()) - ignored):
            if old.get(key) != new.get(key):
                changes[key] = [old.get(key), new.get(key)]
        return changes

    def _node_kwargs(self, data: dict[str, Any]) -> dict[str, Any]:
        fields = set(GraphNode.__dataclass_fields__.keys())
        return {key: data.get(key) for key in fields if key in data}

    def _edge_kwargs(self, data: dict[str, Any]) -> dict[str, Any]:
        fields = set(GraphEdge.__dataclass_fields__.keys())
        return {key: data.get(key) for key in fields if key in data}


__all__ = ["GraphService"]
