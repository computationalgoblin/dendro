import json

import pytest

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.project import Project
from packages.domain.project_chronology import ProjectChronology
from packages.domain.result import Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v23_to_v24,
    validate_project_structure,
)
from packages.persistence.store import ProjectStore, load_project_data


@pytest.mark.persistence
def test_schema_v24_adds_empty_project_chronology_to_v23_projects():
    old_data = Project(id="proj-v23", name="Legacy B41").to_dict()
    old_data["schema_version"] = 23
    old_data.pop("project_chronology", None)

    migrated = _apply_migration_v23_to_v24(old_data)

    assert migrated["schema_version"] == 24
    assert migrated["project_chronology"]["id"] == "project_chronology"
    assert migrated["project_chronology"]["milestone_ids"] == []


@pytest.mark.persistence
def test_validate_project_structure_rejects_non_dict_project_chronology():
    data = Project(id="proj-bad", name="Bad").to_dict()
    data["schema_version"] = CURRENT_SCHEMA_VERSION
    data["project_chronology"] = ["not-dict"]

    error = validate_project_structure(data)

    assert error == "Project config section 'project_chronology' must be a JSON object, got list"


@pytest.mark.persistence
def test_project_store_roundtrips_chronology_and_causal_milestones(tmp_path):
    project = Project(id="proj-h02", name="H02")
    project.causal_milestones.append(
        CausalMilestone(
            id="hito-1",
            title="Juramento de las Siete Puertas",
            affected_entity_ids=["leaf-1"],
        )
    )
    project.project_chronology = ProjectChronology(
        calendar_name="Calendario de la Frontera",
        description="Cronologia principal de campana.",
        calendar_system="diegetic",
        milestone_ids=["hito-1"],
        metadata={"view": "future-filtered"},
    )
    path = tmp_path / "chronology.json"

    store = ProjectStore()
    save_result = store.save(project, path)
    load_result = store.load(path)

    assert isinstance(save_result, Ok)
    assert isinstance(load_result, Ok)
    assert load_result.value.project_chronology.calendar_name == "Calendario de la Frontera"
    assert load_result.value.project_chronology.milestone_ids == ["hito-1"]
    assert load_result.value.project_chronology.metadata == {"view": "future-filtered"}
    assert load_result.value.causal_milestones[0].title == "Juramento de las Siete Puertas"


@pytest.mark.persistence
def test_project_store_roundtrips_edited_milestone_chronology_fields(tmp_path):
    project = Project(id="proj-h03", name="H03")
    project.causal_milestones.append(
        CausalMilestone(
            id="hito-editado",
            title="Titulo editado",
            description="Resumen editado",
            rationale="Cuerpo editado",
            metadata={
                "sort_index": 4,
                "chronology_key": "Era de ceniza",
                "primary_entity_id": "leaf-1",
                "body": "Cuerpo editado",
            },
            affected_entity_ids=["leaf-1"],
        )
    )
    project.project_chronology = ProjectChronology(milestone_ids=["hito-editado"])
    path = tmp_path / "edited-hito.json"

    store = ProjectStore()
    assert isinstance(store.save(project, path), Ok)
    loaded = store.load(path)

    assert isinstance(loaded, Ok)
    hito = loaded.value.causal_milestones[0]
    assert hito.title == "Titulo editado"
    assert hito.description == "Resumen editado"
    assert hito.rationale == "Cuerpo editado"
    assert hito.metadata["sort_index"] == 4
    assert hito.metadata["chronology_key"] == "Era de ceniza"
    assert hito.metadata["primary_entity_id"] == "leaf-1"


@pytest.mark.persistence
def test_load_project_data_migrates_v23_to_current_schema(tmp_path):
    old_data = Project(id="proj-v23", name="Legacy B41").to_dict()
    old_data["schema_version"] = 23
    old_data.pop("project_chronology", None)
    path = tmp_path / "legacy-v23.json"
    path.write_text(json.dumps(old_data), encoding="utf-8")

    loaded = load_project_data(path)

    assert isinstance(loaded, Ok)
    assert loaded.value["schema_version"] == CURRENT_SCHEMA_VERSION
    assert loaded.value["project_chronology"]["milestone_ids"] == []
