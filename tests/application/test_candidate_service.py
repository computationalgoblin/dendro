"""Tests for CandidateService (B15.8-T02 — DC-022)."""
from pathlib import Path
import tempfile, os

from packages.application.candidate_service import CandidateService
from packages.application.project_service import ProjectService
from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.domain.candidate_issue import CandidateType, CandidateState
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneType
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

    def test_accept_entity_stamps_created_entity_id(self):
        # SEM02: accept_candidate expone el id de la entidad creada en metadata
        # para que la UI pueda «germinar» (foco + glow) el nodo nuevo.
        ps, svc, es, _ = _setup()
        c = svc.create_candidate({
            "title": "Eldrin", "candidate_type": "entidad",
            "proposed_data": {"name": "Eldrin", "entity_type": "personaje"},
        }).value
        result = svc.accept_candidate(c.id)
        assert not isinstance(result, Error)
        created_id = ps.active_project.entities[0].id
        assert c.metadata.get("created_entity_id") == created_id

    def test_accept_relation_stamps_created_relation_id(self):
        # SEM03: relaciones estampan created_relation_id (bloom de arista), no entity_id.
        ps, svc, es, rs = _setup()
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        c = svc.create_candidate({
            "title": "Link", "candidate_type": "relacion",
            "proposed_data": {
                "source_id": e1.id, "target_id": e2.id, "relation_type": "es_aliado_de",
            },
        }).value
        svc.accept_candidate(c.id)
        created_id = ps.active_project.relations[0].id
        assert c.metadata.get("created_relation_id") == created_id
        assert "created_entity_id" not in (c.metadata or {})

    def test_accept_ring_template_stamps_created_ring_id(self):
        # SEM03: anillos estampan created_ring_id (bloom de banda).
        ps, svc, _, _ = _setup()
        c = svc.create_candidate({
            "title": "Anillo propuesto: Materia", "candidate_type": "sugerencia_ia",
            "proposed_data": {"kind": "ring_template", "ring_name": "Materia", "order": 1},
        }).value
        svc.accept_candidate(c.id)
        new_layer = ps.active_project.world_layers[-1]
        assert c.metadata.get("created_ring_id") == new_layer.id

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

    def test_accept_ring_template_creates_world_layer(self):
        ps, svc, _, _ = _setup()
        before = len(ps.active_project.world_layers)
        c = svc.create_candidate({
            "title": "Anillo propuesto: Materia",
            "candidate_type": "sugerencia_ia",
            "proposed_data": {
                "kind": "ring_template",
                "ring_name": "Materia",
                "description": "Sustrato físico",
                "order": 1,
                "domain": "Materia",
                "derived_from": "",
            },
        }).value
        result = svc.accept_candidate(c.id)
        assert not isinstance(result, Error)
        assert len(ps.active_project.world_layers) == before + 1
        new_layer = ps.active_project.world_layers[-1]
        assert new_layer.name == "Materia"
        assert new_layer.order == 1
        assert new_layer.is_default is False
        assert new_layer.metadata.get("origin") == "ai_ring_template"

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

    def test_create_causal_milestone_candidate_is_review_only(self):
        ps, svc, _, _ = _setup()
        milestone = CausalMilestone(
            title="Fundación del Pacto de Peso",
            description="Las ciudades aceptan venerar la gravedad como equilibrio.",
            milestone_type=CausalMilestoneType.FUNDACION,
            affected_entity_ids=["ent_cultura"],
            caused_relation_ids=["rel_deriva"],
            layer_ids=["layer_historia"],
            rationale="Explica una institución desde causas superiores.",
        )

        result = svc.create_causal_milestone_candidate(
            milestone,
            source="ia",
            confidence=0.8,
            justification="Propuesta descendente desde worldbuilding.",
        )

        assert not isinstance(result, Error)
        candidate = result.value
        assert candidate.candidate_type == CandidateType.SUGERENCIA_IA
        assert candidate.state == CandidateState.PENDIENTE
        assert candidate.title == "Hito: Fundación del Pacto de Peso"
        assert candidate.proposed_data["kind"] == "causal_milestone"
        assert candidate.proposed_data["milestone"]["title"] == "Fundación del Pacto de Peso"
        assert candidate.affected_entity_ids == ["ent_cultura"]
        assert candidate.affected_relation_ids == ["rel_deriva"]
        assert candidate.metadata["review_required"] is True
        assert candidate.metadata["canonizes_automatically"] is False
        assert len(ps.active_project.causal_milestones) == 0
