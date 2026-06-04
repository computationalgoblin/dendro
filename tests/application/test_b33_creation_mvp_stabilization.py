from packages.application.ai_context_actions import AIContextActionService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


class CapturingProvider:
    provider_name = "capturing"

    def chat(self, system_prompt, user_prompt, temperature=0.7, max_tokens=2048):
        return "Sugerencia IA no canon", None


def _project():
    project = Project(name="B33-T03")
    a = NarrativeEntity(name="A", entity_type=EntityType.PERSONAJE)
    b = NarrativeEntity(name="B", entity_type=EntityType.PERSONAJE)
    project.entities.extend([a, b])
    return project, a, b


def test_duplicate_relation_create_and_update_are_blocked_without_mutating_state():
    project, a, b = _project()
    service = RelationService(FakeProjectService(project))
    first = service.create_relation(a.id, b.id, "sirve_a", {"direction": "unidireccional"})
    assert isinstance(first, Ok)

    duplicate_create = service.create_relation(a.id, b.id, "sirve_a", {"direction": "unidireccional"})
    assert isinstance(duplicate_create, Error)
    assert len(project.relations) == 1

    second = service.create_relation(a.id, b.id, "enemigo_de", {"direction": "unidireccional"})
    assert isinstance(second, Ok)
    assert len(project.relations) == 2
    before = second.value.to_dict()

    duplicate_update = service.update_relation(
        second.value.id,
        {
            "source_id": a.id,
            "target_id": b.id,
            "relation_type": "sirve_a",
            "direction": "unidireccional",
            "description": "No debe quedar aplicado",
        },
    )

    assert isinstance(duplicate_update, Error)
    assert len(project.relations) == 2
    assert second.value.to_dict() == before


def test_relation_inline_ai_does_not_create_ghost_nodes_relations_or_candidates():
    project, a, b = _project()
    service = RelationService(FakeProjectService(project))
    relation = service.create_relation(a.id, b.id, "sirve_a")
    assert isinstance(relation, Ok)
    ai = AIContextActionService(
        ProjectService(),
        candidate_service=None,
        provider=CapturingProvider(),  # type: ignore[arg-type]
    )
    ai.project_service.active_project = project

    result = ai.run_relation_text_suggestion(
        relation.value.id,
        prompt_hint="No crear nodos ni relaciones fantasma",
        language="es",
    )

    assert isinstance(result, Ok)
    assert result.value.raw_text == "Sugerencia IA no canon"
    assert len(project.entities) == 2
    assert len(project.relations) == 1
    serialized = str(project.to_dict())
    assert "IA improve_text#1" not in serialized
    assert "Concepto" not in serialized
    assert "Sugerencia IA no canon" not in serialized
