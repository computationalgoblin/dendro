"""Tests for CandidateService (B15.8-T02 — DC-022)."""
from pathlib import Path
import tempfile, os

from packages.application.candidate_service import CandidateService
from packages.application.project_service import ProjectService
from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.domain.candidate_issue import CandidateType, CandidateState
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.relation import RelationType
from packages.domain.result import Error
from packages.persistence.store import ProjectStore


def _setup():
    store = ProjectStore()
    ps = ProjectService(store=store)
    proj = ps.create(name="Test")
    es = EntityService(project_service=ps)
    rs = RelationService(project_service=ps)
    return ps, CandidateService(ps, es, rs), es, rs


class TestCandidateService:
    def test_create_and_get(self):
        ps, svc, _, _ = _setup()
        c = svc.create_candidate({"title": "Test", "candidate_type": "entidad"}).value
        assert c.title == "Test"
        c2 = svc.get_candidate(c.id).value
        assert c2.id == c.id

    def test_accept_entity_creates_real_entity(self):
        ps, svc, es, _ = _setup()
        c = svc.create_candidate({
            "title": "Eldrin", "candidate_type": "entidad",
            "proposed_data": {"name": "Eldrin", "entity_type": "personaje"},
        }).value
        result = svc.accept_candidate(c.id)
        assert not isinstance(result, Error)
        assert c.state == CandidateState.ACEPTADO
        assert len(ps.active_project.entities) == 1
        assert ps.active_project.entities[0].name == "Eldrin"

    def test_accept_relation_creates_real_relation(self):
        ps, svc, es, rs = _setup()
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        c = svc.create_candidate({
            "title": "Link", "candidate_type": "relacion",
            "proposed_data": {"source_id": e1.id, "target_id": e2.id, "relation_type": "es_aliado_de"},
        }).value
        result = svc.accept_candidate(c.id)
        assert not isinstance(result, Error)
        assert len(ps.active_project.relations) == 1

    def test_reject_no_mutation(self):
        ps, svc, es, _ = _setup()
        c = svc.create_candidate({"title": "Bad", "candidate_type": "entidad", "proposed_data": {"name": "Bad"}}).value
        result = svc.reject_candidate(c.id, "nope")
        assert not isinstance(result, Error)
        assert c.state == CandidateState.RECHAZADO
        assert len(ps.active_project.entities) == 0

    def test_partial_accept(self):
        ps, svc, _, _ = _setup()
        c = svc.create_candidate({"title": "Part", "candidate_type": "entidad"}).value
        result = svc.partial_accept_candidate(c.id, {"name": "Half"}, "partial")
        assert not isinstance(result, Error)
        assert c.state == CandidateState.PARCIALMENTE_ACEPTADO

    def test_merge(self):
        ps, svc, es, _ = _setup()
        e = es.create_entity({"name": "Target", "entity_type": "personaje"}).value
        c = svc.create_candidate({"title": "Extra", "candidate_type": "entidad", "proposed_data": {"brief_description": "Extra info"}}).value
        result = svc.merge_candidate(c.id, e.id)
        assert not isinstance(result, Error)
        assert c.state == CandidateState.FUSIONADO
        assert e.brief_description == "Extra info"

    def test_convert(self):
        ps, svc, _, _ = _setup()
        c = svc.create_candidate({"title": "X", "candidate_type": "entidad"}).value
        result = svc.convert_candidate(c.id, "relacion")
        assert not isinstance(result, Error)
        assert c.candidate_type == CandidateType.RELACION

    def test_archive(self):
        ps, svc, _, _ = _setup()
        c = svc.create_candidate({"title": "Old", "candidate_type": "entidad"}).value
        result = svc.archive_candidate(c.id)
        assert not isinstance(result, Error)
        assert c.state == CandidateState.ARCHIVADO

    def test_confidence_validation(self):
        ps, svc, _, _ = _setup()
        c = svc.create_candidate({"title": "X", "candidate_type": "entidad", "confidence": 0.5}).value
        assert c.confidence == 0.5
        result = svc.update_candidate(c.id, {"confidence": 1.5})
        assert isinstance(result, Error)

    def test_relation_endpoint_validation(self):
        ps, svc, es, _ = _setup()
        c = svc.create_candidate({
            "title": "BadLink", "candidate_type": "relacion",
            "proposed_data": {"source_id": "fake", "target_id": "fake2", "relation_type": "es_aliado_de"},
        }).value
        result = svc.accept_candidate(c.id)
        assert isinstance(result, Error)
