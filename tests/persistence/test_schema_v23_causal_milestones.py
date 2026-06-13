import json

import pytest

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v22_to_v23,
    validate_project_structure,
)
from packages.persistence.store import ProjectStore, load_project_data


@pytest.mark.persistence
def test_schema_version_bumped_to_23_for_causal_milestones():
    assert CURRENT_SCHEMA_VERSION >= 23
    assert MAX_SUPPORTED_VERSION >= 23


@pytest.mark.persistence
def test_migration_v22_to_v23_adds_empty_causal_milestones_collection():
    old_data = Project(id="proj-v22", name="Legacy B40").to_dict()
    old_data["schema_version"] = 22
    old_data.pop("causal_milestones", None)

    migrated = _apply_migration_v22_to_v23(old_data)

    assert migrated["schema_version"] == 23
    assert migrated["causal_milestones"] == []
    assert migrated["name"] == "Legacy B40"


@pytest.mark.persistence
def test_validate_project_structure_rejects_non_list_causal_milestones():
    data = Project(id="proj-bad", name="Bad").to_dict()
    data["schema_version"] = 23
    data["causal_milestones"] = {"bad": "not-list"}

    error = validate_project_structure(data)

    assert error == "Project collection 'causal_milestones' must be a JSON array, got dict"


@pytest.mark.persistence
def test_load_project_data_migrates_v22_and_project_store_roundtrips_milestones(tmp_path):
    old_data = Project(id="proj-v22", name="Legacy B40").to_dict()
    old_data["schema_version"] = 22
    old_data.pop("causal_milestones", None)
    legacy_path = tmp_path / "legacy-v22.json"
    legacy_path.write_text(json.dumps(old_data), encoding="utf-8")

    loaded_raw = load_project_data(legacy_path)

    assert isinstance(loaded_raw, Ok)
    assert loaded_raw.value["schema_version"] == CURRENT_SCHEMA_VERSION
    assert loaded_raw.value["causal_milestones"] == []

    project = Project(id="proj-b41", name="B41")
    project.causal_milestones.append(
        CausalMilestone(id="hito-1", title="Fundación del Pacto de Peso")
    )
    project_path = tmp_path / "b41.json"
    store = ProjectStore()

    save_result = store.save(project, project_path)
    assert isinstance(save_result, Ok)

    load_result = store.load(project_path)
    assert isinstance(load_result, Ok)
    assert load_result.value.causal_milestones[0].title == "Fundación del Pacto de Peso"
