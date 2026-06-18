"""AIContextActionService — BETA1-AI02.

The context menu / detail panel are shortcuts into the SAME command-bar job
pipeline (gateway → provider.chat). Output policy by intent family:
  - generative intents  → staged candidates persisted for review
  - analytical intents   → report surfaced as a preview (no candidate)
  - text intents         → inline text (no candidate)
No path mutates canon automatically.
"""
from packages.application.ai_context_actions import AIContextActionService
from packages.application.candidate_service import CandidateService
from packages.domain.candidate_issue import CandidateType
from packages.domain.entity import CanonState, EntityType, NarrativeEntity, VisibilityState
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


class FakeProvider:
    """Stand-in real provider: returns a fixed chat response, records calls."""
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, response: str = "{}"):
        self.response = response
        self.calls: list[dict] = []

    def chat(self, system_prompt, user_message, timeout=None, *, temperature=None, max_tokens=None, json_mode=False):
        self.calls.append({"json_mode": json_mode, "user": user_message})
        return self.response, None


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


def test_node_action_creates_non_canon_entity_candidate_through_pipeline():
    project = _project()
    provider = FakeProvider(response='{"hojas": [{"name": "Aliada propuesta", "entity_type": "personaje"}]}')
    service = _service(project, provider)

    result = service.run_node_action("ent_1", "create_candidate", prompt_hint="una aliada")

    assert isinstance(result, Ok)
    assert len(project.entities) == 2  # canon untouched
    assert len(project.candidates) == 1
    created = result.value.candidates[0]
    assert created.source == "ia"
    assert created.candidate_type == CandidateType.ENTIDAD
    assert created.metadata["action_type"] == "create_candidate"
    assert created.metadata["target_type"] == "node"
    assert created.metadata["target_id"] == "ent_1"
    assert created.metadata["context_hash"] == result.value.context_hash
    assert created.proposed_data["canonical_status"] == "candidate_non_canon"
    # The call went through the gateway/provider with json_mode (structured).
    assert provider.calls and provider.calls[-1]["json_mode"] is True


def test_relation_action_creates_relation_candidate_without_mutating_relations():
    project = _project()
    provider = FakeProvider(
        response='{"relations": [{"source_id": "ent_1", "target_id": "ent_2", "relation_type": "es_aliado_de"}]}'
    )
    service = _service(project, provider)

    result = service.run_relation_action("rel_1", "create_candidate")

    assert isinstance(result, Ok)
    assert len(project.relations) == 1  # canon untouched
    created = result.value.candidates[0]
    assert created.candidate_type == CandidateType.RELACION
    assert created.affected_relation_ids == ["rel_1"]
    assert created.metadata["target_type"] == "relation"


def test_detect_action_returns_preview_not_candidate():
    project = _project()
    provider = FakeProvider(response='{"report": "Posible contradicción detectada", "issues": []}')
    service = _service(project, provider)

    result = service.run_node_action("ent_1", "detect_contradictions")

    assert isinstance(result, Ok)
    assert result.value.candidates == []
    assert len(project.candidates) == 0
    assert result.value.previews[0]["canonical_status"] == "preview_non_canon"
    assert result.value.previews[0]["context_hash"] == result.value.context_hash
    assert "contradicción" in result.value.raw_text


def test_node_text_suggestion_returns_inline_text_no_candidate():
    project = _project()
    provider = FakeProvider(response="Ariadna camina entre ruinas con paso firme y mirada inquieta.")
    service = _service(project, provider)

    result = service.run_node_text_suggestion("ent_1", prompt_hint="más poético")

    assert isinstance(result, Ok)
    assert result.value.candidates == []
    assert len(project.candidates) == 0
    assert "Ariadna" in result.value.raw_text
    # Text intents do not request JSON mode.
    assert provider.calls and provider.calls[-1]["json_mode"] is False


def test_player_audience_redacted_target_does_not_call_provider():
    project = _project()
    project.entities[0].visibility_state = VisibilityState.SECRETO_MUNDO
    provider = FakeProvider()
    service = _service(project, provider)

    result = service.run_node_action("ent_1", "create_candidate", audience="player")

    assert isinstance(result, Error)
    assert provider.calls == []
    assert len(project.candidates) == 0
