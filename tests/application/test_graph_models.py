"""
Tests for graph view models (B11-T01) — GraphNode, GraphEdge, GraphPath,
GraphFilters, GraphView, GraphStats.
"""

from __future__ import annotations

import json

from packages.application.graph_models import (
    GraphEdge,
    GraphFilters,
    GraphNode,
    GraphPath,
    GraphStats,
    GraphView,
)
from packages.domain.entity import CanonState, EntityType, NarrativeEntity
from packages.domain.relation import NarrativeRelation, RelationType

# ---------------------------------------------------------------------------
# GraphNode
# ---------------------------------------------------------------------------


class TestGraphNode:
    def test_from_entity(self) -> None:
        e = NarrativeEntity(
            name="Eldrin",
            entity_type=EntityType.PERSONAJE,
            custom_type_id="ct_123",
            domain_ids=["mundo"],
            layer_ids=["geografia"],
            tags=["wizard"],
        )
        node = GraphNode(
            id=e.id,
            label=e.name,
            entity_type=e.entity_type.value,
            custom_type_id=e.custom_type_id,
            canon_state=e.canon_state.value,
            visibility_state=e.visibility_state.value,
            domain_ids=e.domain_ids,
            layer_ids=e.layer_ids,
            tags=e.tags,
            is_archived=(e.canon_state == CanonState.ARCHIVADO),
            metadata={"brief": e.brief_description[:100]},
        )
        assert node.id == e.id
        assert node.label == "Eldrin"
        assert node.entity_type == "personaje"
        assert node.custom_type_id == "ct_123"
        assert node.domain_ids == ["mundo"]
        assert node.layer_ids == ["geografia"]
        assert node.tags == ["wizard"]
        assert node.is_archived is False

    def test_archived_node(self) -> None:
        e = NarrativeEntity(name="Dead", entity_type=EntityType.PERSONAJE)
        e.canon_state = CanonState.ARCHIVADO
        node = GraphNode(
            id=e.id, label=e.name, entity_type=e.entity_type.value,
            canon_state=e.canon_state.value,
            is_archived=(e.canon_state == CanonState.ARCHIVADO),
        )
        assert node.is_archived is True

    def test_to_dict(self) -> None:
        node = GraphNode(id="n1", label="Test", entity_type="personaje",
                         domain_ids=["mundo"], tags=["tag1"])
        d = node.to_dict()
        assert d["id"] == "n1"
        assert d["entity_type"] == "personaje"
        assert d["domain_ids"] == ["mundo"]
        assert d["tags"] == ["tag1"]
        json.dumps(d)  # must be JSON-serializable


# ---------------------------------------------------------------------------
# GraphEdge
# ---------------------------------------------------------------------------


class TestGraphEdge:
    def test_from_relation(self) -> None:
        r = NarrativeRelation(
            source_id="e1", target_id="e2",
            relation_type=RelationType.ES_ALIADO_DE,
            custom_relation_type_id="crt_1",
            layer_ids=["geografia"],
        )
        edge = GraphEdge(
            id=r.id, source_id=r.source_id, target_id=r.target_id,
            label=r.relation_type.value, relation_type=r.relation_type.value,
            custom_relation_type_id=r.custom_relation_type_id,
            direction=r.direction.value, canon_state=r.canon_state.value,
            visibility_state=r.visibility_state.value,
            intensity=r.intensity.value, certainty=r.certainty_level.value,
            layer_ids=r.layer_ids,
            is_archived=(r.canon_state == CanonState.ARCHIVADO),
        )
        assert edge.id == r.id
        assert edge.source_id == "e1"
        assert edge.target_id == "e2"
        assert edge.relation_type == "es_aliado_de"
        assert edge.custom_relation_type_id == "crt_1"
        assert edge.layer_ids == ["geografia"]
        assert edge.is_broken is False

    def test_broken_edge(self) -> None:
        edge = GraphEdge(id="e1", source_id="exists", target_id="missing",
                         relation_type="es_aliado_de", is_broken=True)
        assert edge.is_broken is True

    def test_to_dict(self) -> None:
        edge = GraphEdge(id="e1", source_id="a", target_id="b",
                         relation_type="es_aliado_de", is_broken=False)
        d = edge.to_dict()
        assert d["source_id"] == "a"
        assert d["is_broken"] is False
        json.dumps(d)


# ---------------------------------------------------------------------------
# GraphPath
# ---------------------------------------------------------------------------


class TestGraphPath:
    def test_found_path(self) -> None:
        n1 = GraphNode(id="a", label="A")
        n2 = GraphNode(id="b", label="B")
        e1 = GraphEdge(id="e1", source_id="a", target_id="b",
                       relation_type="es_aliado_de")
        path = GraphPath(nodes=[n1, n2], edges=[e1], length=1, found=True)
        assert path.found is True
        assert path.length == 1
        assert len(path.nodes) == 2

    def test_not_found_path(self) -> None:
        path = GraphPath(found=False)
        assert path.found is False
        assert path.nodes == []
        assert path.length == 0

    def test_to_dict(self) -> None:
        n1 = GraphNode(id="a", label="A")
        e1 = GraphEdge(id="e1", source_id="a", target_id="b",
                       relation_type="es_aliado_de")
        path = GraphPath(nodes=[n1], edges=[e1], length=1, found=True)
        d = path.to_dict()
        assert d["found"] is True
        assert len(d["nodes"]) == 1
        json.dumps(d)


# ---------------------------------------------------------------------------
# GraphFilters
# ---------------------------------------------------------------------------


class TestGraphFilters:
    def test_defaults(self) -> None:
        gf = GraphFilters()
        assert gf.entity_type is None
        assert gf.include_archived is False
        assert gf.include_broken is True
        assert gf.max_nodes == 200
        assert gf.max_edges == 500

    def test_active_filter_labels(self) -> None:
        gf = GraphFilters(entity_type="personaje", domain_id="mundo",
                          include_archived=True)
        labels = gf.active_filter_labels()
        assert "entity_type=personaje" in labels
        assert "domain_id=mundo" in labels
        assert "include_archived" in labels
        assert "exclude_broken" not in labels  # include_broken=True is default

    def test_canon_state_list(self) -> None:
        gf = GraphFilters(canon_state=["canonico", "borrador"])
        labels = gf.active_filter_labels()
        assert any("canon_state" in lb for lb in labels)
        assert "canonico" in labels[0]

    def test_to_dict(self) -> None:
        gf = GraphFilters(entity_type="personaje", canon_state=["canonico"],
                          max_nodes=50)
        d = gf.to_dict()
        assert d["entity_type"] == "personaje"
        assert d["canon_state"] == ["canonico"]
        assert d["max_nodes"] == 50
        json.dumps(d)


# ---------------------------------------------------------------------------
# GraphView
# ---------------------------------------------------------------------------


class TestGraphView:
    def test_empty(self) -> None:
        view = GraphView()
        assert view.nodes == []
        assert view.edges == []
        assert view.hidden_node_count == 0

    def test_with_content(self) -> None:
        n = GraphNode(id="a", label="A")
        e = GraphEdge(id="e1", source_id="a", target_id="b",
                      relation_type="es_aliado_de")
        stats = GraphStats(candidate_nodes=1, visible_nodes=1)
        view = GraphView(
            nodes=[n], edges=[e], hidden_node_count=0, hidden_edge_count=0,
            filters_applied=["entity_type=personaje"], stats=stats,
        )
        assert len(view.nodes) == 1
        assert len(view.edges) == 1
        assert view.filters_applied == ["entity_type=personaje"]

    def test_to_dict(self) -> None:
        n = GraphNode(id="a", label="A")
        view = GraphView(nodes=[n], stats=GraphStats(candidate_nodes=1))
        d = view.to_dict()
        assert len(d["nodes"]) == 1
        assert d["stats"]["candidate_nodes"] == 1
        json.dumps(d)


# ---------------------------------------------------------------------------
# GraphStats
# ---------------------------------------------------------------------------


class TestGraphStats:
    def test_defaults(self) -> None:
        stats = GraphStats()
        assert stats.candidate_nodes == 0
        assert stats.visible_nodes == 0
        assert stats.active_nodes == 0

    def test_counts(self) -> None:
        stats = GraphStats(
            candidate_nodes=10,
            visible_nodes=8,
            hidden_nodes=2,
            archived_nodes=3,
            broken_edges=1,
            active_nodes=7,   # 10 - 3
            active_edges=12,
        )
        assert stats.candidate_nodes == 10
        assert stats.visible_nodes == 8
        assert stats.hidden_nodes == 2
        assert stats.archived_nodes == 3
        assert stats.broken_edges == 1

    def test_to_dict(self) -> None:
        stats = GraphStats(candidate_nodes=5, visible_nodes=5, active_nodes=4,
                           archived_nodes=1, broken_edges=0,
                           candidate_edges=3, visible_edges=3, active_edges=3,
                           hidden_nodes=0, hidden_edges=0, archived_edges=0)
        d = stats.to_dict()
        assert d["candidate_nodes"] == 5
        assert d["active_nodes"] == 4
        json.dumps(d)
