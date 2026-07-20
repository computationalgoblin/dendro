"""BETA2-MEM-03: migración v37→v38 y persistencia de structured_references."""

import json

import pytest

from packages.domain.narrative_memory import MemoryTargetKind
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.domain.structured_reference import ReferenceStatus, StructuredReference
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v37_to_v38,
    validate_project_structure,
)
from packages.persistence.store import ProjectStore, load_project_data


@pytest.mark.persistence
def test_schema_is_v38():
    # Forward-compatible: v38 introdujo structured_references; versiones posteriores
    # (v39 wiki) son aditivas y no rompen esta garantía.
    assert CURRENT_SCHEMA_VERSION >= 38


@pytest.mark.persistence
def test_migration_v37_to_v38_adds_empty_collection_without_loss():
    data = {"schema_version": 37, "name": "L", "entities": [{"id": "e1"}]}
    migrated = _apply_migration_v37_to_v38(data)
    assert migrated["schema_version"] == 38
    assert migrated["structured_references"] == []
    assert migrated["entities"] == [{"id": "e1"}]


@pytest.mark.persistence
def test_migration_v37_to_v38_preserves_existing():
    existing = [StructuredReference(source_id="e1", target_id="e2").to_dict()]
    data = {"schema_version": 37, "structured_references": existing}
    migrated = _apply_migration_v37_to_v38(data)
    assert migrated["structured_references"] == existing


@pytest.mark.persistence
def test_load_project_data_migrates_v37_to_v38(tmp_path):
    old = Project(id="p37", name="Legacy v37").to_dict()
    old["schema_version"] = 37
    old.pop("structured_references", None)
    path = tmp_path / "legacy-v37.json"
    path.write_text(json.dumps(old, default=str), encoding="utf-8")

    loaded = load_project_data(path)

    assert isinstance(loaded, Ok)
    assert loaded.value["schema_version"] == CURRENT_SCHEMA_VERSION
    assert loaded.value["structured_references"] == []


@pytest.mark.persistence
def test_store_roundtrips_references(tmp_path):
    project = Project(id="pref", name="Ref")
    project.structured_references.append(
        StructuredReference(
            source_kind=MemoryTargetKind.ENTITY,
            source_id="e1",
            source_field="brief_description",
            target_kind=MemoryTargetKind.MILESTONE,
            target_id="h1",
            alias="Guerra",
            status=ReferenceStatus.RESUELTA,
        )
    )
    project.structured_references.append(
        StructuredReference(
            source_id="e1", source_field="brief_description", alias="Aria",
            status=ReferenceStatus.AMBIGUA, candidate_target_ids=["a", "b"],
        )
    )
    path = tmp_path / "ref.json"

    store = ProjectStore()
    assert isinstance(store.save(project, path), Ok)
    loaded = store.load(path)

    assert isinstance(loaded, Ok)
    refs = loaded.value.structured_references
    assert len(refs) == 2
    resolved = next(r for r in refs if r.status == ReferenceStatus.RESUELTA)
    assert resolved.target_kind == MemoryTargetKind.MILESTONE
    assert resolved.target_id == "h1"
    ambiguous = next(r for r in refs if r.status == ReferenceStatus.AMBIGUA)
    assert ambiguous.candidate_target_ids == ["a", "b"]


@pytest.mark.persistence
def test_new_project_has_empty_references():
    project = Project(id="new", name="New")
    assert project.structured_references == []
    assert "structured_references" in project.to_dict()


@pytest.mark.persistence
def test_validate_rejects_non_list_references():
    data = {
        "id": "x", "name": "n", "created_at": "t", "updated_at": "t",
        "structured_references": {"not": "list"},
    }
    error = validate_project_structure(data)
    assert error is not None
    assert "structured_references" in error
