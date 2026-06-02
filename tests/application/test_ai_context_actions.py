from packages.application.ai_context_actions import AIContextActionService
from packages.application.candidate_service import CandidateService
from packages.domain.ai_models import AIResponse
from packages.domain.candidate_issue import CandidateType
from packages.domain.entity import CanonState, EntityType, NarrativeEntity, VisibilityState
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


class FakeProvider:
    provider_name = "fake"

    def __init__(self, candidates=None, raw_text="fake raw", observations=None):
        self.candidates = candidates if candidates is not None else [{"name": "Propuesta IA", "entity_type": "personaje"}]
        self.raw_text = raw_text
        self.observations = observations or []
        self.last_operation = None

    def invoke(self, operation):
        self.last_operation = operation
        return AIResponse(
            id="fake_response",
            operation=operation,
            raw_text=self.raw_text,
            candidates=list(self.candidates),
            observations=list(self.observations),
            provider="fake",
            latency_ms=1.0,
        )


def _project():
    project = Project(name="AI Context Test")
    project.entities.append(NarrativeEntity(
        id="ent_1",
        name="Ariadna",
        entity_type=EntityType.PERSONAJE,
        canon_state=CanonState.CANONICO,
        visibility_state=VisibilityState.VISIBLE_JUGADORES,
        brief_description="Exploradora",
    ))
    project.entities.append(NarrativeEntity(
        id="ent_2",
        name="Namar",
        entity_type=EntityType.LOCALIZACION,
        canon_state=CanonState.CANONICO,
        visibility_state=VisibilityState.VISIBLE_JUGADORES,
    ))
    project.relations.append(NarrativeRelation(
        id="rel_1",
        source_id="ent_1",
        target_id="ent_2",
        relation_type=RelationType.BUSCA,
        canon_state=CanonState.CANONICO,
        visibility_state=VisibilityState.VISIBLE_JUGADORES,
    ))
    return project


def _service(project, provider):
    ps = FakeProjectService(project)
    return AIContextActionService(ps, CandidateService(ps), provider=provider)


def test_node_action_uses_narrative_context_and_creates_non_canon_candidate():
    project = _project()
    provider = FakeProvider(candidates=[{"description": "Texto mejorado", "confidence": 0.8}])
    service = _service(project, provider)

    result = service.run_node_action("ent_1", "improve_text", prompt_hint="más poético")

    assert isinstance(result, Ok)
    created = result.value.candidates[0]
    assert len(project.entities) == 2
    assert len(project.candidates) == 1
    assert created.source == "ia"
    assert created.candidate_type == CandidateType.CAMBIO
    assert created.metadata["action_type"] == "improve_text"
    assert created.metadata["target_type"] == "node"
    assert created.metadata["target_id"] == "ent_1"
    assert created.metadata["context_hash"] == result.value.context_hash
    assert created.proposed_data["canonical_status"] == "candidate_non_canon"
    assert provider.last_operation is not None
    assert provider.last_operation.context.selected_entity_ids == ["ent_1"]
    assert provider.last_operation.context.project_config_snapshot["constraints"]["ai_may_mutate_canon"] is False


def test_relation_action_creates_relation_candidate_without_mutating_relations():
    project = _project()
    provider = FakeProvider(candidates=[{"source_id": "ent_1", "target_id": "ent_2", "relation_type": "es_aliado_de"}])
    service = _service(project, provider)

    result = service.run_relation_action("rel_1", "create_candidate")

    assert isinstance(result, Ok)
    assert len(project.relations) == 1
    created = result.value.candidates[0]
    assert created.candidate_type == CandidateType.RELACION
    assert created.affected_relation_ids == ["rel_1"]
    assert created.metadata["target_type"] == "relation"
    assert provider.last_operation is not None
    assert provider.last_operation.context.selected_relation_ids == ["rel_1"]


def test_detect_action_returns_preview_not_candidate():
    project = _project()
    provider = FakeProvider(candidates=[{"type": "narrative", "description": "Posible contradicción"}], raw_text="Análisis")
    service = _service(project, provider)

    result = service.run_node_action("ent_1", "detect_contradictions")

    assert isinstance(result, Ok)
    assert result.value.candidates == []
    assert len(project.candidates) == 0
    assert result.value.previews[0]["canonical_status"] == "preview_non_canon"
    assert result.value.previews[0]["context_hash"] == result.value.context_hash


def test_player_audience_redacted_target_does_not_call_provider():
    project = _project()
    project.entities[0].visibility_state = VisibilityState.SECRETO_MUNDO
    provider = FakeProvider()
    service = _service(project, provider)

    result = service.run_node_action("ent_1", "improve_text", audience="player")

    assert isinstance(result, Error)
    assert provider.last_operation is None
    assert len(project.candidates) == 0
