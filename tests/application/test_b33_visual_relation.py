from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import Direction, RelationType
from packages.domain.result import Ok


class FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _project():
    project = Project(name="B33 visual relation")
    devian = NarrativeEntity(name="Devian", entity_type=EntityType.PERSONAJE)
    akshan = NarrativeEntity(name="Akshan", entity_type=EntityType.PERSONAJE)
    project.entities.extend([devian, akshan])
    return project, devian, akshan


def test_visual_relation_draft_save_updates_real_relation_fields_and_persists_roundtrip(tmp_path):
    project, devian, akshan = _project()
    service = RelationService(FakeProjectService(project))

    created = service.create_relation(
        devian.id,
        akshan.id,
        "esta_relacionado_con",
        {"custom_metadata": {"_visual_draft": True, "_edge_color": "#A4AEC0"}},
    )
    assert isinstance(created, Ok)
    relation = created.value

    saved = service.update_relation(
        relation.id,
        {
            "source_id": devian.id,
            "target_id": akshan.id,
            "relation_type": "sirve_a",
            "direction": "unidireccional",
            "description": "Devian sirve a Akshan.",
            "custom_metadata": {"_body": "Cuerpo", "_notes": "Notas", "_edge_color": "#7EC8A5"},
        },
    )

    assert isinstance(saved, Ok)
    assert saved.value.source_id == devian.id
    assert saved.value.target_id == akshan.id
    assert saved.value.relation_type == RelationType.SIRVE_A
    assert saved.value.direction == Direction.UNIDIRECCIONAL
    assert saved.value.description == "Devian sirve a Akshan."
    assert saved.value.custom_metadata["_body"] == "Cuerpo"
    assert saved.value.custom_metadata["_notes"] == "Notas"
    assert saved.value.custom_metadata["_edge_color"] == "#7EC8A5"
    assert "_visual_draft" not in saved.value.custom_metadata

    roundtrip = Project.from_dict(project.to_dict())
    restored = roundtrip.relations[0]
    assert restored.source_id == devian.id
    assert restored.target_id == akshan.id
    assert restored.relation_type == RelationType.SIRVE_A
    assert restored.custom_metadata["_body"] == "Cuerpo"
    assert restored.custom_metadata["_notes"] == "Notas"

    project_file = tmp_path / "visual-relation.dendro.json"
    project_service = ProjectService()
    project_service.active_project = project
    assert isinstance(project_service.save(project_file), Ok)
    project_service.close()
    reopened = project_service.open(project_file)
    assert isinstance(reopened, Ok)
    reopened_relation = reopened.value.relations[0]
    assert reopened_relation.source_id == devian.id
    assert reopened_relation.target_id == akshan.id
    assert reopened_relation.relation_type == RelationType.SIRVE_A
    assert reopened_relation.custom_metadata["_edge_color"] == "#7EC8A5"


def test_visual_relation_cancel_can_delete_unsaved_draft():
    project, devian, akshan = _project()
    service = RelationService(FakeProjectService(project))
    created = service.create_relation(devian.id, akshan.id, "esta_relacionado_con")
    assert isinstance(created, Ok)
    assert len(project.relations) == 1

    deleted = service.delete_relation(created.value.id)

    assert isinstance(deleted, Ok)
    assert project.relations == []


def test_visual_relation_reverse_direction_swaps_source_and_target():
    project, devian, akshan = _project()
    service = RelationService(FakeProjectService(project))
    created = service.create_relation(devian.id, akshan.id, "sirve_a")
    assert isinstance(created, Ok)
    relation = created.value

    result = service.update_relation(
        relation.id,
        {
            "source_id": akshan.id,
            "target_id": devian.id,
            "relation_type": "sirve_a",
            "direction": "unidireccional",
        },
    )

    assert isinstance(result, Ok)
    assert result.value.source_id == akshan.id
    assert result.value.target_id == devian.id
