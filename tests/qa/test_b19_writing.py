"""B19-T05 QA tests — writing layer integration, regression and smoke."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.application.writing_service import WritingService
from packages.application.project_service import ProjectService
from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.application.history_service import HistoryService
from packages.application.source_service import SourceService
from packages.application.candidate_service import CandidateService
from packages.domain.candidate_issue import Candidate, CandidateType, CandidateState, StructuredIssue
from packages.domain.entity import EntityType
from packages.domain.result import Error, Ok
from packages.domain.writing_models import WritingUnit, WritingUnitType, RevisionState
from packages.persistence.schema import (
    _apply_migration_v12_to_v13, _validate_writing_units,
    CURRENT_SCHEMA_VERSION,
)
from packages.persistence.store import ProjectStore


# ── Helpers ──────────────────────────────────────────────────────────


def _bootstrap(path: Path):
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.open(path)
    hs = HistoryService(project_service=ps)
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    ss = SourceService(project_service=ps, store=store)
    ws = WritingService(ps, entity_service=es, source_service=ss)
    return ps, es, rs, ss, hs, ws


@pytest.fixture
def svc(tmp_path):
    path = tmp_path / "test.json"
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Test")
    ps.save(path)
    _, es, _, _, _, ws = _bootstrap(path)
    # Create test entities
    es.create_entity({"name": "Eldrin", "entity_type": EntityType.PERSONAJE})
    es.create_entity({"name": "Torre", "entity_type": EntityType.LOCALIZACION})
    es.create_entity({"name": "Gandalf", "entity_type": EntityType.PERSONAJE})
    ps.save(path)
    return ws, ps, es, path


# ── Domain model tests (1-5) ───────────────────────────────────────


class TestWritingUnitType:
    def test_18_values(self):
        assert len(WritingUnitType) == 18

    def test_roundtrip(self):
        for wt in WritingUnitType:
            assert WritingUnitType(wt.value) == wt


class TestRevisionState:
    def test_4_values(self):
        assert len(RevisionState) == 4

    def test_roundtrip(self):
        for rs in RevisionState:
            assert RevisionState(rs.value) == rs


class TestWritingUnit:
    def test_21_fields_roundtrip(self):
        wu = WritingUnit(
            id="wu-1", name="Cap 1", unit_type=WritingUnitType.CAPITULO,
            content="Once upon a time...", summary="Opening chapter",
            parent_id="story-1", order=1,
            entity_ids=["e1", "e2"], framework_ids=["fw1"],
            domain_ids=["mundo"], layer_ids=["l1"],
            timeline_event_ids=["t1"], source_ids=["s1"],
            revision_state=RevisionState.BORRADOR, author_notes="Draft",
            canon_state="borrador", visibility_state="visible_usuario",
            tags=["fantasy"], metadata={"key": "value"},
        )
        d = wu.to_dict()
        assert len(d) == 21
        wu2 = WritingUnit.from_dict(d)
        assert wu2.id == "wu-1"
        assert wu2.name == "Cap 1"
        assert wu2.unit_type == WritingUnitType.CAPITULO
        assert wu2.entity_ids == ["e1", "e2"]
        assert wu2.domain_ids == ["mundo"]
        assert wu2.timeline_event_ids == ["t1"]
        assert wu2.revision_state == RevisionState.BORRADOR
        assert wu2.metadata == {"key": "value"}

    def test_domain_ids_present(self):
        wu = WritingUnit.from_dict({"id": "w1", "name": "X", "unit_type": "escena"})
        assert wu.domain_ids == []

    def test_timeline_event_ids_present(self):
        wu = WritingUnit.from_dict({"id": "w1", "name": "X", "unit_type": "escena"})
        assert wu.timeline_event_ids == []

    def test_empty_dict_defaults(self):
        wu = WritingUnit.from_dict({})
        assert wu.name == ""
        assert wu.entity_ids == []
        assert wu.domain_ids == []
        assert wu.revision_state == RevisionState.BORRADOR


# ── Service tests (6-29) ───────────────────────────────────────────


class TestWritingServiceCRUD:
    def test_create_unit(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Historia", "unit_type": WritingUnitType.HISTORIA})
        assert not isinstance(r, Error)
        assert r.value.name == "Historia"
        assert r.value.unit_type == WritingUnitType.HISTORIA

    def test_create_unit_invalid_parent(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "X", "unit_type": "escena", "parent_id": "no-existe"})
        assert isinstance(r, Error)

    def test_list_by_type(self, svc):
        ws, ps, es, path = svc
        ws.create_unit({"name": "H", "unit_type": "historia"})
        ws.create_unit({"name": "E", "unit_type": "escena"})
        units = ws.list_units({"unit_type": WritingUnitType.ESCENA})
        assert len(units) == 1
        assert units[0].name == "E"

    def test_list_by_parent(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Padre", "unit_type": "historia"})
        pid = r.value.id
        ws.create_unit({"name": "Hijo", "unit_type": "capitulo", "parent_id": pid})
        units = ws.list_units({"parent_id": pid})
        assert len(units) == 1

    def test_list_by_entity(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Escena", "unit_type": "escena"})
        # Link first entity
        proj = ps.active_project
        entities = getattr(proj, "entities", [])
        if entities:
            ws.link_entity(r.value.id, entities[0].id)
            ps.save(path)
            units = ws.list_units({"entity_id": entities[0].id})
            assert len(units) >= 1

    def test_list_by_revision(self, svc):
        ws, ps, es, path = svc
        ws.create_unit({"name": "Draft", "unit_type": "escena", "revision_state": "borrador"})
        ws.create_unit({"name": "Final", "unit_type": "escena", "revision_state": "final"})
        units = ws.list_units({"revision_state": RevisionState.FINAL})
        assert len(units) == 1

    def test_list_excludes_archived(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Keep", "unit_type": "escena"})
        r2 = ws.create_unit({"name": "Bin", "unit_type": "escena"})
        ws.archive_unit(r2.value.id)
        ps.save(path)
        units = ws.list_units()
        names = {u.name for u in units}
        assert "Keep" in names
        assert "Bin" not in names

    def test_list_include_archived(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Bin", "unit_type": "escena"})
        ws.archive_unit(r.value.id)
        ps.save(path)
        units = ws.list_units({"include_archived": True})
        names = {u.name for u in units}
        assert "Bin" in names

    def test_get_tree_3_levels(self, svc):
        ws, ps, es, path = svc
        r1 = ws.create_unit({"name": "Story", "unit_type": "historia"})
        r2 = ws.create_unit({"name": "Arc", "unit_type": "arco_narrativo", "parent_id": r1.value.id})
        r3 = ws.create_unit({"name": "Chap", "unit_type": "capitulo", "parent_id": r2.value.id})
        ps.save(path)
        tree = ws.get_tree(r1.value.id)
        assert tree["unit"].name == "Story"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["unit"].name == "Arc"
        assert len(tree["children"][0]["children"]) == 1
        assert tree["children"][0]["children"][0]["unit"].name == "Chap"

    def test_reorder(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "X", "unit_type": "escena", "order": 1})
        ws.reorder_unit(r.value.id, 5)
        ps.save(path)
        u = ws.get_unit(r.value.id).value
        assert u.order == 5

    def test_reparent(self, svc):
        ws, ps, es, path = svc
        r1 = ws.create_unit({"name": "A", "unit_type": "historia"})
        r2 = ws.create_unit({"name": "B", "unit_type": "historia"})
        c = ws.create_unit({"name": "Child", "unit_type": "escena", "parent_id": r1.value.id})
        ws.reparent_unit(c.value.id, r2.value.id)
        ps.save(path)
        u = ws.get_unit(c.value.id).value
        assert u.parent_id == r2.value.id

    def test_reparent_rejects_cycle(self, svc):
        ws, ps, es, path = svc
        r1 = ws.create_unit({"name": "Parent", "unit_type": "historia"})
        c = ws.create_unit({"name": "Child", "unit_type": "escena", "parent_id": r1.value.id})
        err = ws.reparent_unit(r1.value.id, c.value.id)
        assert isinstance(err, Error)

    def test_archive_soft_delete(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Old", "unit_type": "escena"})
        ws.archive_unit(r.value.id)
        ps.save(path)
        u = ws.get_unit(r.value.id).value
        assert u.revision_state == RevisionState.ARCHIVADO

    def test_link_entity_valid(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena"})
        entities = getattr(ps.active_project, "entities", [])
        if not entities:
            pytest.skip("No entities created")
        rr = ws.link_entity(r.value.id, entities[0].id)
        assert not isinstance(rr, Error)
        ps.save(path)
        u = ws.get_unit(r.value.id).value
        assert entities[0].id in u.entity_ids

    def test_link_entity_invalid(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena"})
        rr = ws.link_entity(r.value.id, "no-existe")
        assert isinstance(rr, Error)

    def test_unlink_no_error_if_not_linked(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena"})
        rr = ws.unlink_entity(r.value.id, "no-existe")
        assert not isinstance(rr, Error)

    def test_get_linked_entities(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena"})
        entities = getattr(ps.active_project, "entities", [])
        if entities:
            ws.link_entity(r.value.id, entities[0].id)
            ps.save(path)
            linked = ws.get_linked_entities(r.value.id)
            assert len(linked) >= 1
            assert hasattr(linked[0], "name")

    def test_get_entity_coverage(self, svc):
        ws, ps, es, path = svc
        entities = getattr(ps.active_project, "entities", [])
        if not entities:
            pytest.skip()
        r = ws.create_unit({"name": "X", "unit_type": "escena"})
        ws.link_entity(r.value.id, entities[0].id)
        ps.save(path)
        units = ws.get_entity_coverage(entities[0].id)
        assert len(units) >= 1

    def test_coverage_summary(self, svc):
        ws, ps, es, path = svc
        s = ws.get_coverage_summary()
        assert "total" in s
        assert "covered" in s
        assert "uncovered" in s
        assert "by_type" in s
        assert isinstance(s["total"], int)

    def test_get_unlinked_entities(self, svc):
        ws, ps, es, path = svc
        unlinked = ws.get_unlinked_entities()
        assert isinstance(unlinked, list)


# ── IA assistance tests (30-38) ─────────────────────────────────────


class TestIASimulated:
    def test_expand_creates_candidate(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena", "content": "Test"})
        rr = ws.expand_unit(r.value.id, "Add tension")
        assert not isinstance(rr, Error)
        cand = rr.value
        assert isinstance(cand, Candidate)
        assert cand.source == "ia"
        assert cand.metadata.get("ai_mode") == "writing_expand"
        assert cand.metadata.get("writing_unit_id") == r.value.id

    def test_expand_does_not_mutate_content(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena", "content": "Original"})
        ws.expand_unit(r.value.id, "hint")
        u = ws.get_unit(r.value.id).value
        assert u.content == "Original"

    def test_candidate_is_sugerencia_ia(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena"})
        rr = ws.expand_unit(r.value.id)
        assert not isinstance(rr, Error)
        assert rr.value.candidate_type == CandidateType.SUGERENCIA_IA

    def test_summarize_returns_text(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena", "content": "Long story..."})
        rr = ws.summarize_unit(r.value.id)
        assert not isinstance(rr, Error)
        assert isinstance(rr.value, str)

    def test_critique_creates_candidate(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena", "content": "Test"})
        rr = ws.critique_unit(r.value.id)
        assert not isinstance(rr, Error)
        assert isinstance(rr.value, Candidate)
        assert rr.value.metadata.get("ai_mode") == "writing_critique"

    def test_rewrite_creates_candidate(self, svc):
        ws, ps, es, path = svc
        r = ws.create_unit({"name": "Scene", "unit_type": "escena", "content": "Test"})
        rr = ws.rewrite_unit(r.value.id, "gothic")
        assert not isinstance(rr, Error)
        assert isinstance(rr.value, Candidate)
        assert rr.value.metadata.get("ai_mode") == "writing_rewrite"


# ── Issue detection tests (39-45) ──────────────────────────────────


class TestDetectWritingIssues:
    def test_unlinked_unit(self, svc):
        ws, ps, es, path = svc
        ws.create_unit({"name": "No entities", "unit_type": "escena"})
        ps.save(path)
        issues = ws.detect_writing_issues()
        unlinked = [i for i in issues if "no linked entities" in i.description.lower()
                    or "WRITING_UNIT_UNLINKED" in str(i.metadata.get("subtype", ""))]
        assert len(unlinked) >= 1

    def test_order_duplicate(self, svc):
        ws, ps, es, path = svc
        ws.create_unit({"name": "A", "unit_type": "escena", "order": 1})
        ws.create_unit({"name": "B", "unit_type": "escena", "order": 1})
        ps.save(path)
        issues = ws.detect_writing_issues()
        dup = [i for i in issues if "WRITING_ORDER_DUPLICATE" in str(i.metadata.get("subtype", ""))]
        assert len(dup) >= 1

    def test_parent_missing(self, svc):
        ws, ps, es, path = svc
        # Create normally, then set a broken parent directly (simulating corrupted data)
        r = ws.create_unit({"name": "Child", "unit_type": "escena"})
        # Directly mutate parent_id to bypass creation validation
        proj = ps.active_project
        u = ws.get_unit(r.value.id).value
        u.parent_id = "no-parent"
        ps.save(path)
        issues = ws.detect_writing_issues()
        parent_issues = [i for i in issues
                         if "parent_id" in i.description.lower()
                         or "WRITING_PARENT_MISSING" in str(i.metadata.get("subtype", ""))]
        assert len(parent_issues) >= 1

    def test_entity_uncovered(self, svc):
        ws, ps, es, path = svc
        # Entities already exist but not linked — should appear as uncovered
        ps.save(path)
        issues = ws.detect_writing_issues()
        uncov = [i for i in issues if "WRITING_ENTITY_UNCOVERED" in str(i.metadata.get("subtype", ""))]
        assert len(uncov) >= 1

    def test_structured_issue_not_legacy(self, svc):
        ws, ps, es, path = svc
        ws.create_unit({"name": "X", "unit_type": "escena"})
        ps.save(path)
        issues = ws.detect_writing_issues()
        for iss in issues:
            assert isinstance(iss, StructuredIssue)

    def test_deterministic_source_and_validator(self, svc):
        ws, ps, es, path = svc
        ws.create_unit({"name": "X", "unit_type": "escena"})
        ps.save(path)
        issues = ws.detect_writing_issues()
        for iss in issues:
            assert iss.metadata.get("source") == "deterministic"
            assert iss.metadata.get("validator") == "writing"


# ── Persistence / schema tests (51-54) ─────────────────────────────


class TestSchemaV13:
    def test_migration_v12_to_v13(self):
        v12 = {"schema_version": 12, "id": "x", "name": "X",
               "created_at": "2026-01-01T00:00:00+00:00",
               "updated_at": "2026-01-01T00:00:00+00:00",
               "entities": [], "relations": [], "sources": [], "history": [],
               "issues": []}
        result = _apply_migration_v12_to_v13(v12)
        assert result["schema_version"] == 13
        assert "writing_units" in result
        assert result["writing_units"] == []

    def test_roundtrip_with_writing_unit(self, tmp_path):
        path = tmp_path / "rt.json"
        store = ProjectStore()
        ps = ProjectService(store=store)
        ps.create(name="RT")
        ps.save(path)
        # Open with services, create unit, save with same store
        ps2 = ProjectService(store=store)
        ps2.open(path)
        from packages.application.entity_service import EntityService
        from packages.application.relation_service import RelationService
        from packages.application.history_service import HistoryService
        from packages.application.source_service import SourceService
        hs = HistoryService(project_service=ps2)
        es = EntityService(project_service=ps2, store=store)
        rs = RelationService(project_service=ps2, store=store)
        ss = SourceService(project_service=ps2, store=store)
        ws = WritingService(ps2, entity_service=es, source_service=ss)
        ws.create_unit({"name": "Scene", "unit_type": "escena"})
        ps2.save(path)
        # Reload
        store3 = ProjectStore()
        ps3 = ProjectService(store=store3)
        ps3.open(path)
        proj = ps3.active_project
        assert len(proj.writing_units) == 1
        assert proj.writing_units[0].name == "Scene"

    def test_validate_writing_units_dup_ids(self):
        data = [
            {"id": "a", "unit_type": "escena", "revision_state": "borrador"},
            {"id": "a", "unit_type": "capitulo", "revision_state": "borrador"},
        ]
        errors = _validate_writing_units(data)
        assert any("duplicate" in e.lower() for e in errors)

    def test_validate_writing_units_bad_parent(self):
        data = [
            {"id": "a", "unit_type": "escena", "revision_state": "borrador",
             "parent_id": "no-existe"}
        ]
        errors = _validate_writing_units(data)
        assert any("does not exist" in e.lower() for e in errors)

    def test_validate_writing_units_cycle(self):
        data = [
            {"id": "a", "unit_type": "escena", "revision_state": "borrador", "parent_id": "b"},
            {"id": "b", "unit_type": "escena", "revision_state": "borrador", "parent_id": "a"},
        ]
        errors = _validate_writing_units(data)
        assert any("cycle" in e.lower() for e in errors)


# ── Regression tests (55-60) ───────────────────────────────────────


class TestRegression:
    def test_entity_show_extended(self, svc):
        ws, ps, es, path = svc
        entities = getattr(ps.active_project, "entities", [])
        if entities:
            e = entities[0]
            assert hasattr(e, "name")
            assert hasattr(e, "entity_type")

    def test_ai_generate_entity(self, svc):
        ws, ps, es, path = svc
        # Just verify the project service can access entities
        proj = ps.active_project
        assert proj is not None
        assert hasattr(proj, "entities")

    def test_timeline_list(self, svc):
        ws, ps, es, path = svc
        proj = ps.active_project
        assert hasattr(proj, "timeline_events")

    def test_import_basket(self, svc):
        ws, ps, es, path = svc
        proj = ps.active_project
        assert hasattr(proj, "import_baskets")

    def test_graph_summary(self, svc):
        ws, ps, es, path = svc
        proj = ps.active_project
        assert hasattr(proj, "entities")
        assert hasattr(proj, "relations")

    def test_issue_list(self, svc):
        ws, ps, es, path = svc
        proj = ps.active_project
        assert hasattr(proj, "issues")
