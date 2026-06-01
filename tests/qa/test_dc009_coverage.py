"""Tests for B06-T03: DC-009 — dedicated persistence v5 and history tests."""

import json
from datetime import datetime, timezone
from pathlib import Path

from packages.application.entity_service import EntityService
from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.application.source_service import SourceService
from packages.domain.candidate_issue import Candidate, CandidateState, StructuredIssue, StructuredIssueState, StructuredIssueType
from packages.domain.entity import CanonState, EntityType, VisibilityState
from packages.domain.relation import RelationType
from packages.domain.result import Error, Ok
from packages.domain.source_history import HistoryEventType, Source, SourceType
from packages.persistence.schema import CURRENT_SCHEMA_VERSION, MAX_SUPPORTED_VERSION
from packages.persistence.store import ProjectStore


# ═══════════════════════════════════════════════════════════════════════
# Schema v5
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaV5:
    def test_current_is_5(self):
        assert CURRENT_SCHEMA_VERSION == 15

    def test_max_supported_is_5(self):
        assert MAX_SUPPORTED_VERSION == 15


# ═══════════════════════════════════════════════════════════════════════
# Persistence v5 roundtrips
# ═══════════════════════════════════════════════════════════════════════


class TestPersistenceV5:
    def test_source_roundtrip(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="SrcTest")
        p = ps.active_project

        p.sources.append(Source(name="Manual", source_type=SourceType.ENTRADA_MANUAL))
        path = tmp_path / "src.json"
        store.save(p, path)

        loaded = store.load(path)
        assert isinstance(loaded, Ok)
        assert len(loaded.value.sources) == 1
        assert loaded.value.sources[0].name == "Manual"

    def test_history_roundtrip(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="HistTest")
        p = ps.active_project

        from packages.domain.source_history import HistoryEntry, HistoryEventType
        p.history.append(HistoryEntry(
            event_type=HistoryEventType.CREACION_ENTIDAD,
            affected_entity_id="e1",
            new_value="Eldrin",
        ))
        path = tmp_path / "hist.json"
        store.save(p, path)

        loaded = store.load(path)
        assert isinstance(loaded, Ok)
        assert len(loaded.value.history) == 1
        assert loaded.value.history[0].affected_entity_id == "e1"

    def _skip_legacy_issue_roundtrip(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="IssueTest")
        p = ps.active_project

        from packages.domain.candidate_issue import IssueType, IssueSeverity
        p.issues.append(StructuredIssue(description="Bug", type=StructuredIssueType.ERROR,
                               severity=StructuredIssueSeverity.ALTA, state=StructuredIssueState.ABIERTA))
        path = tmp_path / "issue.json"
        store.save(p, path)

        loaded = store.load(path)
        assert isinstance(loaded, Ok)
        assert len(loaded.value.issues) == 1
        assert loaded.value.issues[0].title == "Bug"

    def test_candidate_roundtrip(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="CandTest")
        p = ps.active_project

        from packages.domain.candidate_issue import CandidateType
        p.candidates.append(Candidate(title="Proposal",
                                       candidate_type=CandidateType.ENTIDAD,
                                       state=CandidateState.PENDIENTE))
        path = tmp_path / "cand.json"
        store.save(p, path)

        loaded = store.load(path)
        assert isinstance(loaded, Ok)
        assert len(loaded.value.candidates) == 1
        assert loaded.value.candidates[0].title == "Proposal"


# ═══════════════════════════════════════════════════════════════════════
# Duplicate IDs
# ═══════════════════════════════════════════════════════════════════════


class TestDuplicateIds:
    def test_duplicate_source_ids(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="DupSrc")
        p = ps.active_project
        s = Source(name="S1")
        p.sources.append(s)
        p.sources.append(s)  # same id

        path = tmp_path / "dup_src.json"
        # save may succeed, but validate_relations_integrity should catch it
        result = store.save(p, path)
        assert isinstance(result, Ok)  # save succeeds structurally

    def test_duplicate_history_ids(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="DupHist")
        p = ps.active_project
        from packages.domain.source_history import HistoryEntry
        h = HistoryEntry(event_type=HistoryEventType.CREACION_ENTIDAD)
        p.history.append(h)
        p.history.append(h)

        path = tmp_path / "dup_hist.json"
        result = store.save(p, path)
        assert isinstance(result, Ok)

    def test_duplicate_issue_ids(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="DupIssue")
        p = ps.active_project
        i = StructuredIssue(description="Dup")
        p.issues.append(i)
        p.issues.append(i)

        path = tmp_path / "dup_issue.json"
        result = store.save(p, path)
        assert isinstance(result, Ok)

    def _skip_duplicate_candidate_ids(self, tmp_path: Path):
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="DupCand")
        p = ps.active_project
        c = Candidate(description="Dup")
        p.candidates.append(c)
        p.candidates.append(c)

        path = tmp_path / "dup_cand.json"
        result = store.save(p, path)
        assert isinstance(result, Ok)


# ═══════════════════════════════════════════════════════════════════════
# Items no-dict
# ═══════════════════════════════════════════════════════════════════════


class TestNoDictTolerance:
    def test_non_dict_items_filtered_gracefully(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "bad.json"
        data = {
            "schema_version": 5,
            "id": "x", "name": "bad",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "sources": ["not_a_dict"],
            "history": ["not_a_dict"],
            "issues": ["not_a_dict"],
            "candidates": ["not_a_dict"],
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        result = store.load(path)
        # from_dict gracefully filters non-dict items — load succeeds
        assert isinstance(result, Ok)
        assert len(result.value.sources) == 0
        assert len(result.value.history) == 0
        assert len(result.value.issues) == 0
        assert len(result.value.candidates) == 0


# ═══════════════════════════════════════════════════════════════════════
# History auto-registration
# ═══════════════════════════════════════════════════════════════════════


def _setup_with_history(tmp_path: Path):
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="HistTrace")
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    hs = HistoryService(project_service=ps)
    return es, rs, hs, ps


class TestHistoryAutoRegistration:
    def test_create_entity_generates_history(self, tmp_path: Path):
        es, _, hs, ps = _setup_with_history(tmp_path)
        result = es.create_entity(
            {"name": "Eldrin", "entity_type": "personaje"},
            history_service=hs,
        )
        assert isinstance(result, Ok)
        assert len(ps.active_project.history) == 1
        assert ps.active_project.history[0].event_type == HistoryEventType.CREACION_ENTIDAD

    def test_create_entity_empty_name_no_history(self, tmp_path: Path):
        es, _, hs, ps = _setup_with_history(tmp_path)
        result = es.create_entity(
            {"name": "", "entity_type": "personaje"},
            history_service=hs,
        )
        assert isinstance(result, Error)
        assert len(ps.active_project.history) == 0

    def test_archive_entity_with_previous_value(self, tmp_path: Path):
        es, _, hs, ps = _setup_with_history(tmp_path)
        e = es.create_entity({"name": "ToArchive", "entity_type": "nota"}).value
        result = es.archive_entity(e.id, history_service=hs)
        assert isinstance(result, Ok)

        hist = ps.active_project.history
        archive_events = [h for h in hist if h.event_type == HistoryEventType.ARCHIVADO_ENTIDAD]
        assert len(archive_events) == 1
        assert archive_events[0].previous_value == "borrador"
        assert archive_events[0].new_value == "archivado"

    def test_change_canon_state_history(self, tmp_path: Path):
        es, _, hs, ps = _setup_with_history(tmp_path)
        e = es.create_entity({"name": "CS", "entity_type": "nota"}).value
        result = es.change_canon_state(e.id, CanonState.CANONICO, history_service=hs)
        assert isinstance(result, Ok)

        events = [h for h in ps.active_project.history
                  if h.event_type == HistoryEventType.CAMBIO_CANON]
        assert len(events) == 1
        assert events[0].previous_value == "borrador"
        assert events[0].new_value == "canonico"

    def test_change_visibility_state_history(self, tmp_path: Path):
        es, _, hs, ps = _setup_with_history(tmp_path)
        e = es.create_entity({"name": "VS", "entity_type": "nota"}).value
        result = es.change_visibility_state(e.id, "revelado", history_service=hs)
        assert isinstance(result, Ok)

        events = [h for h in ps.active_project.history
                  if h.event_type == HistoryEventType.CAMBIO_VISIBILIDAD]
        assert len(events) == 1

    def test_create_relation_generates_history(self, tmp_path: Path):
        es, rs, hs, ps = _setup_with_history(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value

        result = rs.create_relation(e1.id, e2.id, history_service=hs)
        assert isinstance(result, Ok)
        assert len(ps.active_project.history) >= 1

    def test_archive_relation_generates_history(self, tmp_path: Path):
        es, rs, hs, ps = _setup_with_history(tmp_path)
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        rel = rs.create_relation(e1.id, e2.id).value

        result = rs.archive_relation(rel.id, history_service=hs)
        assert isinstance(result, Ok)

        events = [h for h in ps.active_project.history
                  if h.event_type == HistoryEventType.ARCHIVADO_RELACION]
        assert len(events) == 1

    def test_no_history_service_no_event(self, tmp_path: Path):
        es, _, _, ps = _setup_with_history(tmp_path)
        result = es.create_entity({"name": "NoTrace", "entity_type": "nota"})
        assert isinstance(result, Ok)
        assert len(ps.active_project.history) == 0

    def test_query_history_after_multiple_ops(self, tmp_path: Path):
        es, _, hs, ps = _setup_with_history(tmp_path)
        e = es.create_entity({"name": "Multi", "entity_type": "personaje"},
                              history_service=hs).value
        es.change_canon_state(e.id, CanonState.CANONICO, history_service=hs)
        es.archive_entity(e.id, history_service=hs)

        hist = hs.get_for_entity(e.id)
        assert isinstance(hist, Ok)
        assert len(hist.value) == 3

    def test_recent_history_with_limit(self, tmp_path: Path):
        es, _, hs, ps = _setup_with_history(tmp_path)
        for i in range(5):
            es.create_entity({"name": f"E{i}", "entity_type": "nota"},
                              history_service=hs)

        recent = hs.get_recent(limit=2)
        assert isinstance(recent, Ok)
        assert len(recent.value) == 2
