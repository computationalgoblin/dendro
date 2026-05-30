"""
Tests for GraphService (B11-T02).
"""

from __future__ import annotations

from packages.application.entity_service import EntityService
from packages.application.graph_models import GraphFilters
from packages.application.graph_service import GraphService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.entity import CanonState, EntityType, NarrativeEntity
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


def _setup():
    """Create a project with services and return (ps, es, rs, gs)."""
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="GraphTest")
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    from packages.application.query_service import QueryService
    from packages.application.source_service import SourceService
    from packages.application.history_service import HistoryService
    from packages.application.text_search_service import TextSearchService
    hs = HistoryService(project_service=ps)
    ss = SourceService(project_service=ps, store=store)
    qs = QueryService(entity_service=es, relation_service=rs,
                      source_service=ss, history_service=hs)
    ts = TextSearchService(entity_service=es, relation_service=rs)
    gs = GraphService(query_service=qs, relation_service=rs, entity_service=es)
    return ps, es, rs, gs


def _create_entities(es, names_types):
    """Create entities and return them as a dict name→entity."""
    result = {}
    for name, etype in names_types:
        e = es.create_entity({"name": name, "entity_type": etype}).value
        result[name] = e
    return result


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------


class TestBuildGraph:
    def test_empty_project(self) -> None:
        _, _, _, gs = _setup()
        view = gs.build_graph().value
        assert len(view.nodes) == 0
        assert len(view.edges) == 0
        assert view.stats.candidate_nodes == 0

    def test_two_entities_one_relation(self) -> None:
        _, es, rs, gs = _setup()
        e = _create_entities(es, [("A", "personaje"), ("B", "personaje")])
        rs.create_relation(source_id=e["A"].id, target_id=e["B"].id,
                           relation_type="es_aliado_de")

        view = gs.build_graph().value
        assert len(view.nodes) == 2
        assert len(view.edges) == 1
        assert view.stats.candidate_nodes == 2
        assert view.stats.candidate_edges == 1

    def test_archived_excluded(self) -> None:
        _, es, rs, gs = _setup()
        e = _create_entities(es, [("A", "personaje"), ("B", "personaje")])
        rs.create_relation(source_id=e["A"].id, target_id=e["B"].id,
                           relation_type="es_aliado_de")
        es.archive_entity(e["B"].id)

        view = gs.build_graph().value
        # B is archived and include_archived=False → excluded from nodes
        assert len(view.nodes) == 1
        # archived_nodes counts among ALL entities (pre-filter)
        assert view.stats.archived_nodes == 1

    def test_archived_included(self) -> None:
        _, es, rs, gs = _setup()
        e = _create_entities(es, [("A", "personaje"), ("B", "personaje")])
        rs.create_relation(source_id=e["A"].id, target_id=e["B"].id,
                           relation_type="es_aliado_de")
        es.archive_entity(e["B"].id)

        view = gs.build_graph(GraphFilters(include_archived=True)).value
        assert len(view.nodes) == 2
        assert view.stats.archived_nodes == 1

    def test_filter_by_entity_type(self) -> None:
        _, es, _, gs = _setup()
        _create_entities(es, [("A", "personaje"), ("B", "localizacion")])

        view = gs.build_graph(GraphFilters(entity_type="personaje")).value
        assert len(view.nodes) == 1
        assert view.nodes[0].label == "A"

    def test_broken_edge_detected(self) -> None:
        """Relation to nonexistent entity → is_broken=True."""
        _, es, rs, gs = _setup()
        e = _create_entities(es, [("A", "personaje"), ("B", "personaje")])
        # Create a valid relation first, then break it by removing the target
        rel = rs.create_relation(
            source_id=e["A"].id, target_id=e["B"].id,
            relation_type="es_aliado_de",
        ).value
        # Remove entity B from the project to break the edge
        proj = es._active_project().value
        proj.entities = [ent for ent in proj.entities if ent.id != e["B"].id]

        view = gs.build_graph().value
        broken = [ed for ed in view.edges if ed.is_broken]
        assert len(broken) == 1
        assert view.stats.broken_edges == 1

    def test_max_nodes_truncation(self) -> None:
        _, es, _, gs = _setup()
        for i in range(10):
            es.create_entity({"name": f"E{i}", "entity_type": "personaje"})

        view = gs.build_graph(GraphFilters(max_nodes=5)).value
        assert view.stats.candidate_nodes == 10
        assert view.stats.visible_nodes == 5
        assert view.stats.hidden_nodes == 5


# ---------------------------------------------------------------------------
# build_entity_neighborhood
# ---------------------------------------------------------------------------


class TestNeighborhood:
    def test_depth_1(self) -> None:
        _, es, rs, gs = _setup()
        e = _create_entities(es, [("A", "personaje"), ("B", "personaje"),
                                   ("C", "localizacion")])
        rs.create_relation(source_id=e["A"].id, target_id=e["B"].id,
                           relation_type="es_aliado_de")
        rs.create_relation(source_id=e["A"].id, target_id=e["C"].id,
                           relation_type="pertenece_a")

        view = gs.build_entity_neighborhood(e["A"].id, depth=1).value
        assert len(view.nodes) == 3  # A + B + C
        assert len(view.edges) == 2

    def test_archived_center_error(self) -> None:
        _, es, _, gs = _setup()
        e = _create_entities(es, [("A", "personaje")])
        es.archive_entity(e["A"].id)

        result = gs.build_entity_neighborhood(e["A"].id)
        assert isinstance(result, Error)
        assert "archived" in result.error.lower()

    def test_nonexistent_center_error(self) -> None:
        _, _, _, gs = _setup()
        result = gs.build_entity_neighborhood("does-not-exist")
        assert isinstance(result, Error)


# ---------------------------------------------------------------------------
# build_path_between
# ---------------------------------------------------------------------------


class TestPath:
    def test_path_found(self) -> None:
        _, es, rs, gs = _setup()
        e = _create_entities(es, [("A", "personaje"), ("B", "personaje"),
                                   ("C", "personaje")])
        rs.create_relation(source_id=e["A"].id, target_id=e["B"].id,
                           relation_type="es_aliado_de")
        rs.create_relation(source_id=e["B"].id, target_id=e["C"].id,
                           relation_type="es_aliado_de")

        path = gs.build_path_between(e["A"].id, e["C"].id).value
        assert path.found is True
        assert path.length >= 2

    def test_path_not_found(self) -> None:
        _, es, _, gs = _setup()
        e = _create_entities(es, [("A", "personaje"), ("B", "personaje")])

        path = gs.build_path_between(e["A"].id, e["B"].id).value
        assert path.found is False

    def test_source_not_found(self) -> None:
        _, _, _, gs = _setup()
        result = gs.build_path_between("no-exist", "no-exist2")
        assert isinstance(result, Error)


# ---------------------------------------------------------------------------
# get_graph_stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_match_view(self) -> None:
        _, es, rs, gs = _setup()
        e = _create_entities(es, [("A", "personaje"), ("B", "personaje")])
        rs.create_relation(source_id=e["A"].id, target_id=e["B"].id,
                           relation_type="es_aliado_de")

        stats = gs.get_graph_stats().value
        assert stats.candidate_nodes == 2
        assert stats.candidate_edges == 1
        assert stats.active_nodes == 2

    def test_stats_with_filters(self) -> None:
        _, es, _, gs = _setup()
        _create_entities(es, [("A", "personaje"), ("B", "localizacion")])

        stats = gs.get_graph_stats(
            GraphFilters(entity_type="personaje"),
        ).value
        assert stats.candidate_nodes == 1
