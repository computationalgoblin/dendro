"""BETA2-SUB-01: migración v35→v36 + validación de contención de subhitos."""

import json

import pytest

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v35_to_v36,
    _validate_causal_milestones,
)
from packages.persistence.store import ProjectStore, load_project_data


@pytest.mark.persistence
def test_schema_is_at_least_v36():
    # Los subhitos aterrizaron en v36; versiones posteriores (v37 memoria, …) no
    # rompen la contención. Pin forward-compatible: >= evita re-romper en cada bump.
    assert CURRENT_SCHEMA_VERSION >= 36


@pytest.mark.persistence
def test_migration_v35_to_v36_backfills_parent_and_preserves_data():
    hito = {"id": "hito-1", "title": "Guerra de los Cien Años"}
    data = {"schema_version": 35, "causal_milestones": [hito]}

    migrated = _apply_migration_v35_to_v36(data)

    assert migrated["schema_version"] == 36
    assert migrated["causal_milestones"][0]["parent_milestone_id"] is None
    # sin pérdida del resto de campos
    assert migrated["causal_milestones"][0]["title"] == "Guerra de los Cien Años"


@pytest.mark.persistence
def test_migration_v35_to_v36_is_idempotent_and_keeps_existing_parent():
    data = {
        "schema_version": 35,
        "causal_milestones": [{"id": "batalla", "parent_milestone_id": "guerra"}],
    }
    once = _apply_migration_v35_to_v36(data)
    twice = _apply_migration_v35_to_v36(dict(once))

    assert twice["causal_milestones"][0]["parent_milestone_id"] == "guerra"
    assert twice["schema_version"] == 36


@pytest.mark.persistence
def test_load_project_data_migrates_v35_to_v36(tmp_path):
    old = Project(id="proj-v35", name="Legacy v35").to_dict()
    old["schema_version"] = 35
    old["causal_milestones"] = [CausalMilestone(id="hito-1", title="Guerra").to_dict()]
    old["causal_milestones"][0].pop("parent_milestone_id", None)
    path = tmp_path / "legacy-v35.json"
    path.write_text(json.dumps(old), encoding="utf-8")

    loaded = load_project_data(path)

    assert isinstance(loaded, Ok)
    assert loaded.value["schema_version"] == CURRENT_SCHEMA_VERSION
    assert loaded.value["causal_milestones"][0]["parent_milestone_id"] is None


@pytest.mark.persistence
def test_store_roundtrips_subhito_containment(tmp_path):
    project = Project(id="proj-sub", name="Sub")
    project.causal_milestones.append(
        CausalMilestone(id="guerra", title="La Gran Guerra", year=100)
    )
    project.causal_milestones.append(
        CausalMilestone(
            id="batalla", title="Batalla del Vado", year=102, parent_milestone_id="guerra"
        )
    )
    path = tmp_path / "sub.json"

    store = ProjectStore()
    assert isinstance(store.save(project, path), Ok)
    loaded = store.load(path)

    assert isinstance(loaded, Ok)
    batalla = next(h for h in loaded.value.causal_milestones if h.id == "batalla")
    assert batalla.parent_milestone_id == "guerra"
    assert batalla.is_subhito is True


# ── Validación estructural ───────────────────────────────────────────────────


@pytest.mark.persistence
def test_validate_accepts_valid_one_level_containment():
    hitos = [
        {"id": "guerra"},
        {"id": "batalla", "parent_milestone_id": "guerra"},
    ]
    assert _validate_causal_milestones(hitos) == []


@pytest.mark.persistence
def test_validate_rejects_nonexistent_parent():
    hitos = [{"id": "batalla", "parent_milestone_id": "fantasma"}]
    errors = _validate_causal_milestones(hitos)
    assert any("no existe" in e for e in errors)


@pytest.mark.persistence
def test_validate_rejects_self_reference():
    hitos = [{"id": "x", "parent_milestone_id": "x"}]
    errors = _validate_causal_milestones(hitos)
    assert any("sí mismo" in e for e in errors)


@pytest.mark.persistence
def test_validate_rejects_two_level_nesting():
    hitos = [
        {"id": "guerra"},
        {"id": "batalla", "parent_milestone_id": "guerra"},
        {"id": "escaramuza", "parent_milestone_id": "batalla"},
    ]
    errors = _validate_causal_milestones(hitos)
    assert any(">1 nivel" in e for e in errors)


@pytest.mark.persistence
def test_store_rejects_two_level_nesting_on_load(tmp_path):
    project = Project(id="proj-bad", name="Bad")
    project.causal_milestones.append(CausalMilestone(id="guerra", title="Guerra", year=1))
    project.causal_milestones.append(
        CausalMilestone(id="batalla", title="Batalla", year=2, parent_milestone_id="guerra")
    )
    project.causal_milestones.append(
        CausalMilestone(id="escaramuza", title="Escaramuza", year=3, parent_milestone_id="batalla")
    )
    path = tmp_path / "bad.json"
    ProjectStore().save(project, path)

    loaded = ProjectStore().load(path)

    assert isinstance(loaded, Error)
    assert ">1 nivel" in loaded.error
