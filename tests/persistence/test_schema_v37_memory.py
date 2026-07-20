"""BETA2-MEM-02: migración v36→v37 y persistencia de narrative_memories."""

import json

import pytest

from packages.domain.narrative_memory import (
    MemoryCitation,
    MemoryFreshness,
    MemoryIssue,
    MemoryIssueKind,
    MemoryRevisionProposal,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v36_to_v37,
    validate_project_structure,
)
from packages.persistence.store import ProjectStore, load_project_data


@pytest.mark.persistence
def test_schema_is_at_least_v37():
    # La memoria aterrizó en v37; versiones posteriores (v38 @menciones, …) no la
    # rompen. Pin forward-compatible: >= evita re-romper en cada bump.
    assert CURRENT_SCHEMA_VERSION >= 37


@pytest.mark.persistence
def test_migration_v36_to_v37_adds_empty_collection_without_autogeneration():
    data = {"schema_version": 36, "name": "Legacy", "entities": [{"id": "e1"}]}

    migrated = _apply_migration_v36_to_v37(data)

    assert migrated["schema_version"] == 37
    # No autogenera memoria: colección vacía (proyecto queda "Sin memoria").
    assert migrated["narrative_memories"] == []
    # Sin pérdida del resto de datos.
    assert migrated["entities"] == [{"id": "e1"}]


@pytest.mark.persistence
def test_migration_v36_to_v37_preserves_existing_memories():
    existing = [NarrativeMemory(target_kind=MemoryTargetKind.PROJECT).to_dict()]
    data = {"schema_version": 36, "narrative_memories": existing}

    migrated = _apply_migration_v36_to_v37(data)

    assert migrated["narrative_memories"] == existing
    assert migrated["schema_version"] == 37


@pytest.mark.persistence
def test_load_project_data_migrates_v36_to_v37(tmp_path):
    old = Project(id="proj-v36", name="Legacy v36").to_dict()
    old["schema_version"] = 36
    old.pop("narrative_memories", None)
    path = tmp_path / "legacy-v36.json"
    path.write_text(json.dumps(old, default=str), encoding="utf-8")

    loaded = load_project_data(path)

    assert isinstance(loaded, Ok)
    assert loaded.value["schema_version"] == CURRENT_SCHEMA_VERSION
    assert loaded.value["narrative_memories"] == []


@pytest.mark.persistence
def test_store_roundtrips_memory_block(tmp_path):
    project = Project(id="proj-mem", name="Mem")
    block = NarrativeMemory(
        target_kind=MemoryTargetKind.ENTITY,
        target_id="reina",
        resumen_editorial="La reina exiliada.",
        issues=[
            MemoryIssue(
                kind=MemoryIssueKind.CONTRADICCION,
                texto="Muere dos veces",
                anclado_a=[MemoryCitation(ref_kind=MemoryTargetKind.MILESTONE, ref_id="h1")],
            )
        ],
        citations=[MemoryCitation(ref_kind=MemoryTargetKind.ENTITY, ref_id="rey")],
        freshness=MemoryFreshness.FALTA_REGAR,
        pending_revision=MemoryRevisionProposal(after={"resumen_editorial": "nuevo"}),
    )
    project.narrative_memories.append(block)
    path = tmp_path / "mem.json"

    store = ProjectStore()
    assert isinstance(store.save(project, path), Ok)
    loaded = store.load(path)

    assert isinstance(loaded, Ok)
    restored = loaded.value.narrative_memories[0]
    assert restored.target_key() == ("entity", "reina", "")
    assert restored.resumen_editorial == "La reina exiliada."
    assert restored.issues[0].kind == MemoryIssueKind.CONTRADICCION
    assert restored.issues[0].anclado_a[0].ref_id == "h1"
    assert restored.citations[0].ref_id == "rey"
    assert restored.freshness == MemoryFreshness.FALTA_REGAR
    assert restored.pending_revision.after == {"resumen_editorial": "nuevo"}


@pytest.mark.persistence
def test_new_project_has_empty_memories_collection():
    project = Project(id="new", name="New")
    assert project.narrative_memories == []
    assert "narrative_memories" in project.to_dict()


@pytest.mark.persistence
def test_validate_rejects_non_list_memories():
    data = {
        "id": "x",
        "name": "n",
        "created_at": "t",
        "updated_at": "t",
        "narrative_memories": {"not": "a list"},
    }
    error = validate_project_structure(data)
    assert error is not None
    assert "narrative_memories" in error
