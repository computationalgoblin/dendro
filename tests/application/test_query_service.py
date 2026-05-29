"""Tests for B06-T01: QueryService, EntityCard, GraphNeighborhood."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from packages.application.entity_service import EntityService
from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.query_service import (
    EntityCard,
    GraphNeighborhood,
    QueryService,
)
from packages.application.relation_service import RelationService
from packages.application.source_service import SourceService
from packages.domain.candidate_issue import Candidate, CandidateState, Issue, IssueState
from packages.domain.entity import CertaintyLevel, EntityType, NarrativeImportance
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


def _setup(tmp_path: Path):
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Test World")
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    ss = SourceService(project_service=ps, store=store)
    hs = HistoryService(project_service=ps)
    qs = QueryService(entity_service=es, relation_service=rs,
                       source_service=ss, history_service=hs)
    return qs, es, rs, ss, hs, ps


# -----------------------------------------------------------------------
# New §6.2 filters
# -----------------------------------------------------------------------


class TestFilters:
    def test_filter_by_importance(self, tmp_path: Path):
        qs, es, _, _, _, _ = _setup(tmp_path)
        es.create_entity({"name": "Critical", "entity_type": "personaje"})
        e = es.create_entity({"name": "Minor", "entity_type": "nota"}).value
        e.narrative_importance = NarrativeImportance.MENOR

        r = qs.filter_by_importance(NarrativeImportance.MEDIO)
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_filter_by_certainty(self, tmp_path: Path):
        qs, es, _, _, _, _ = _setup(tmp_path)
        es.create_entity({"name": "Confirmed", "entity_type": "personaje"})
        e = es.create_entity({"name": "Doubtful", "entity_type": "nota"}).value
        e.certainty_level = CertaintyLevel.DUDOSO

        r = qs.filter_by_certainty(CertaintyLevel.PROBABLE)
        assert isinstance(r, Ok)
        assert len(r.value) == 1

    def test_filter_by_modified_since(self, tmp_path: Path):
        qs, es, _, _, _, _ = _setup(tmp_path)
        import time
        es.create_entity({"name": "Old", "entity_type": "nota"})
        time.sleep(0.01)
        cutoff = datetime.now(timezone.utc)
        time.sleep(0.01)
        es.create_entity({"name": "New", "entity_type": "nota"})

        r = qs.filter_by_modified_since(cutoff)
        assert isinstance(r, Ok)
        assert len(r.value) == 1
        assert r.value[0].name == "New"

    def test_filter_by_modified_before(self, tmp_path: Path):
        qs, es, _, _, _, _ = _setup(tmp_path)
        import time
        es.create_entity({"name": "Old", "entity_type": "nota"})
        time.sleep(0.01)
        cutoff = datetime.now(timezone.utc)
        time.sleep(0.01)
        es.create_entity({"name": "New", "entity_type": "nota"})

        r = qs.filter_by_modified_before(cutoff)
        assert isinstance(r, Ok)
        assert len(r.value) == 1
        assert r.value[0].name == "Old"

    def test_get_orphan_entities(self, tmp_path: Path):
        qs, es, rs, _, _, _ = _setup(tmp_path)
        e1 = es.create_entity({"name": "Connected", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "AlsoConnected", "entity_type": "personaje"}).value
        es.create_entity({"name": "Orphan", "entity_type": "nota"})
        rs.create_relation(e1.id, e2.id)

        r = qs.get_orphan_entities()
        assert isinstance(r, Ok)
        assert len(r.value) == 1
        assert r.value[0].name == "Orphan"

    def test_get_pending_candidates(self, tmp_path: Path):
        qs, es, _, _, _, ps = _setup(tmp_path)
        ps.active_project.candidates.append(
            Candidate(title="P1", state=CandidateState.PENDIENTE)
        )
        ps.active_project.candidates.append(
            Candidate(title="P2", state=CandidateState.ACEPTADO)
        )

        r = qs.get_pending_candidates()
        assert isinstance(r, Ok)
        assert len(r.value) == 1
        assert r.value[0].title == "P1"

    def test_get_open_issues(self, tmp_path: Path):
        qs, _, _, _, _, ps = _setup(tmp_path)
        ps.active_project.issues.append(
            Issue(title="Open", state=IssueState.ABIERTA)
        )
        ps.active_project.issues.append(
            Issue(title="InProgress", state=IssueState.EN_PROGRESO)
        )
        ps.active_project.issues.append(
            Issue(title="Resolved", state=IssueState.RESUELTA)
        )

        r = qs.get_open_issues()
        assert isinstance(r, Ok)
        assert len(r.value) == 2


# -----------------------------------------------------------------------
# Combined query
# -----------------------------------------------------------------------


class TestCombinedQuery:
    def test_combined_filters(self, tmp_path: Path):
        qs, es, _, _, _, _ = _setup(tmp_path)
        es.create_entity({"name": "A", "entity_type": "personaje"})
        es.create_entity({"name": "B", "entity_type": "localizacion"})
        es.create_entity({"name": "C", "entity_type": "personaje"})

        r = qs.query(entity_type="personaje", sort_by="name")
        assert isinstance(r, Ok)
        assert len(r.value) == 2
        assert r.value[0].name == "A"

    def test_query_with_limit(self, tmp_path: Path):
        qs, es, _, _, _, _ = _setup(tmp_path)
        for name in ["A", "B", "C", "D", "E"]:
            es.create_entity({"name": name, "entity_type": "nota"})

        r = qs.query(limit=3)
        assert isinstance(r, Ok)
        assert len(r.value) == 3

    def test_query_no_filters_returns_all(self, tmp_path: Path):
        qs, es, _, _, _, _ = _setup(tmp_path)
        es.create_entity({"name": "X", "entity_type": "nota"})
        es.create_entity({"name": "Y", "entity_type": "nota"})

        r = qs.query()
        assert isinstance(r, Ok)
        assert len(r.value) == 2


# -----------------------------------------------------------------------
# EntityCard
# -----------------------------------------------------------------------


class TestEntityCard:
    def test_builds_card(self, tmp_path: Path):
        qs, es, rs, ss, hs, _ = _setup(tmp_path)
        e = es.create_entity({"name": "Eldrin", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "Gandalf", "entity_type": "personaje"}).value
        rs.create_relation(e2.id, e.id)

        # Add a source and an issue
        src = ss.create_source({"name": "Manual"}).value
        ss.link_to_entity(src.id, e.id)
        qs.entity_service.project_service.active_project.issues.append(
            Issue(title="Bug", affected_entity_id=e.id, state=IssueState.ABIERTA)
        )

        card = qs.get_entity_card(e.id)
        assert isinstance(card, Ok)
        c = card.value
        assert c.entity.name == "Eldrin"
        assert len(c.incoming_relations) == 1
        assert len(c.sources) == 1
        assert len(c.open_issues) == 1

    def test_card_nonexistent_entity(self, tmp_path: Path):
        qs, _, _, _, _, _ = _setup(tmp_path)
        r = qs.get_entity_card("nonexistent")
        assert isinstance(r, Error)


# -----------------------------------------------------------------------
# GraphNeighborhood
# -----------------------------------------------------------------------


class TestGraphNeighborhood:
    def test_builds_neighborhood(self, tmp_path: Path):
        qs, es, rs, _, _, _ = _setup(tmp_path)
        e1 = es.create_entity({"name": "Center", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "Neighbor1", "entity_type": "localizacion"}).value
        e3 = es.create_entity({"name": "Neighbor2", "entity_type": "personaje"}).value
        rs.create_relation(e1.id, e2.id)
        rs.create_relation(e3.id, e1.id)

        hood = qs.build_graph_neighborhood(e1.id)
        assert isinstance(hood, Ok)
        h = hood.value
        assert h.center.name == "Center"
        assert len(h.neighbors) == 2
        assert len(h.relations) == 2
        assert h.node_count == 3
        assert h.edge_count == 2

    def test_neighborhood_nonexistent(self, tmp_path: Path):
        qs, _, _, _, _, _ = _setup(tmp_path)
        r = qs.build_graph_neighborhood("nonexistent")
        assert isinstance(r, Error)


# -----------------------------------------------------------------------
# Read-only guarantee
# -----------------------------------------------------------------------


class TestReadOnly:
    def test_filters_do_not_mutate(self, tmp_path: Path):
        qs, es, _, _, _, _ = _setup(tmp_path)
        es.create_entity({"name": "A", "entity_type": "personaje"})
        before = len(es.list_all().value)

        qs.filter_by_importance(NarrativeImportance.MEDIO)
        qs.filter_by_certainty(CertaintyLevel.PROBABLE)
        qs.get_orphan_entities()
        qs.query()

        after = len(es.list_all().value)
        assert before == after, "QueryService mutated project state!"
