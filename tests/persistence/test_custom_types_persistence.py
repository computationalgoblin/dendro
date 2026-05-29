"""
Tests for custom types persistence (B08-T02) — schema v6, serialization,
roundtrip, and migration.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.domain.custom_types import (
    CustomEntityType,
    CustomFieldDefinition,
    CustomFieldValue,
    CustomRelationType,
    FieldType,
)
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation
from packages.domain.result import Ok
from packages.domain.result import unwrap as _unwrap
from packages.persistence.store import ProjectStore

# ---------------------------------------------------------------------------
# Schema v6
# ---------------------------------------------------------------------------


def test_new_project_has_schema_v6() -> None:
    p = Project(name="Test")
    assert p.custom_entity_types == []
    assert p.custom_field_definitions == []
    assert p.custom_relation_types == []


def test_project_to_dict_includes_custom_collections() -> None:
    p = Project(name="Test")
    d = p.to_dict()
    assert "custom_entity_types" in d
    assert "custom_field_definitions" in d
    assert "custom_relation_types" in d
    assert d["custom_entity_types"] == []


# ---------------------------------------------------------------------------
# CustomEntityType persistence
# ---------------------------------------------------------------------------


def test_custom_entity_type_save_load_roundtrip(tmp_path: Path) -> None:
    store = ProjectStore()
    proj_path = tmp_path / "test.json"

    p = Project(name="Test")
    ct = CustomEntityType(
        name="nave_espacial",
        description="Naves del universo",
        base_category=EntityType.OBJETO,
        custom_fields=["f1"],
        is_active=True,
    )
    p.custom_entity_types.append(ct)
    store.save(p, proj_path)

    loaded = store.load(proj_path)
    assert len(loaded.value.custom_entity_types) == 1
    loaded_ct = loaded.value.custom_entity_types[0]
    assert loaded_ct.name == "nave_espacial"
    assert loaded_ct.is_active is True
    assert loaded_ct.custom_fields == ["f1"]


def test_custom_entity_type_soft_delete_persists(tmp_path: Path) -> None:
    store = ProjectStore()
    proj_path = tmp_path / "test.json"

    p = Project(name="Test")
    ct = CustomEntityType(name="obsolete", is_active=False)
    p.custom_entity_types.append(ct)
    store.save(p, proj_path)

    loaded = store.load(proj_path)
    assert loaded.value.custom_entity_types[0].is_active is False


# ---------------------------------------------------------------------------
# CustomFieldDefinition persistence
# ---------------------------------------------------------------------------


def test_field_definition_save_load_roundtrip(tmp_path: Path) -> None:
    store = ProjectStore()
    proj_path = tmp_path / "test.json"

    p = Project(name="Test")
    fd = CustomFieldDefinition(
        name="potencia",
        field_type=FieldType.NUMBER,
        min_value=0,
        max_value=9000,
    )
    p.custom_field_definitions.append(fd)
    store.save(p, proj_path)

    loaded = store.load(proj_path)
    assert len(loaded.value.custom_field_definitions) == 1
    loaded_fd = loaded.value.custom_field_definitions[0]
    assert loaded_fd.name == "potencia"
    assert loaded_fd.field_type == FieldType.NUMBER
    assert loaded_fd.min_value == 0


def test_field_definition_with_options(tmp_path: Path) -> None:
    store = ProjectStore()
    proj_path = tmp_path / "test.json"

    p = Project(name="Test")
    fd = CustomFieldDefinition(
        name="color",
        field_type=FieldType.SINGLE_SELECT,
        options=["rojo", "azul"],
    )
    p.custom_field_definitions.append(fd)
    store.save(p, proj_path)

    loaded = store.load(proj_path)
    assert loaded.value.custom_field_definitions[0].options == ["rojo", "azul"]


# ---------------------------------------------------------------------------
# CustomRelationType persistence
# ---------------------------------------------------------------------------


def test_relation_type_save_load_roundtrip(tmp_path: Path) -> None:
    store = ProjectStore()
    proj_path = tmp_path / "test.json"

    p = Project(name="Test")
    crt = CustomRelationType(
        name="forma_parte_de",
        allowed_source_types=["PERSONAJE"],
        allowed_target_types=["FACCION"],
        custom_fields=["f1"],
    )
    p.custom_relation_types.append(crt)
    store.save(p, proj_path)

    loaded = store.load(proj_path)
    assert len(loaded.value.custom_relation_types) == 1
    loaded_crt = loaded.value.custom_relation_types[0]
    assert loaded_crt.name == "forma_parte_de"
    assert loaded_crt.allowed_source_types == ["PERSONAJE"]


# ---------------------------------------------------------------------------
# Custom fields on entities
# ---------------------------------------------------------------------------


def test_entity_custom_field_value_persists(tmp_path: Path) -> None:
    store = ProjectStore()
    proj_path = tmp_path / "test.json"

    p = Project(name="Test")
    e = NarrativeEntity(
        name="TestEntity",
        custom_type_id="type_X",
    )
    e.custom_fields.append(CustomFieldValue(field_id="f1", value=42))
    p.entities.append(e)
    store.save(p, proj_path)

    loaded = store.load(proj_path)
    loaded_entity = loaded.value.entities[0]
    assert loaded_entity.custom_type_id == "type_X"
    assert len(loaded_entity.custom_fields) == 1
    assert loaded_entity.custom_fields[0].field_id == "f1"
    assert loaded_entity.custom_fields[0].value == 42


def test_entity_multiple_custom_fields_persist(tmp_path: Path) -> None:
    store = ProjectStore()
    proj_path = tmp_path / "test.json"

    p = Project(name="Test")
    e = NarrativeEntity(name="Multi")
    e.custom_fields.append(CustomFieldValue(field_id="f1", value="hello"))
    e.custom_fields.append(CustomFieldValue(field_id="f2", value=True))
    p.entities.append(e)
    store.save(p, proj_path)

    loaded = store.load(proj_path)
    loaded_entity = loaded.value.entities[0]
    assert len(loaded_entity.custom_fields) == 2
    assert loaded_entity.custom_fields[1].value is True


def test_entity_without_custom_fields_still_loads(tmp_path: Path) -> None:
    """Backward compat: entities without custom fields survive roundtrip."""
    store = ProjectStore()
    proj_path = tmp_path / "test.json"

    p = Project(name="Test")
    e = NarrativeEntity(name="Plain")
    p.entities.append(e)
    store.save(p, proj_path)

    loaded = store.load(proj_path)
    assert loaded.value.entities[0].custom_type_id is None
    assert loaded.value.entities[0].custom_fields == []


# ---------------------------------------------------------------------------
# Custom fields on relations
# ---------------------------------------------------------------------------


def test_relation_custom_field_value_persists(tmp_path: Path) -> None:
    store = ProjectStore()
    proj_path = tmp_path / "test.json"

    p = Project(name="Test")
    r = NarrativeRelation(
        source_id="a", target_id="b",
        custom_relation_type_id="crt_1",
    )
    r.custom_fields.append(CustomFieldValue(field_id="f1", value="test"))
    p.relations.append(r)
    store.save(p, proj_path)

    loaded = store.load(proj_path)
    loaded_rel = loaded.value.relations[0]
    assert loaded_rel.custom_relation_type_id == "crt_1"
    assert loaded_rel.custom_fields[0].value == "test"


# ---------------------------------------------------------------------------
# Migration v5 → v6
# ---------------------------------------------------------------------------


def test_migration_v5_to_v6_adds_empty_collections(tmp_path: Path) -> None:
    """A v5 project (without custom type collections) migrates cleanly."""
    store = ProjectStore()
    proj_path = tmp_path / "v5_project.json"

    # Write raw v5 data manually
    v5_data = {
        "id": "test123",
        "name": "Legacy",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "schema_version": 5,
        "entities": [],
        "relations": [],
        "sources": [],
        "history": [],
        "issues": [],
        "candidates": [],
    }
    proj_path.write_text(json.dumps(v5_data))

    result = store.load(proj_path)
    assert isinstance(result, Ok), f"Expected Ok, got {result}"
    project = result.value

    # Migrated collections exist and are empty
    assert project.custom_entity_types == []
    assert project.custom_field_definitions == []
    assert project.custom_relation_types == []


def test_full_roundtrip_all_custom_types(tmp_path: Path) -> None:
    """Create a project with all custom collections, save, reload."""
    store = ProjectStore()
    proj_path = tmp_path / "full.json"

    p = Project(name="Full")
    p.custom_entity_types.append(CustomEntityType(name="Starship"))
    p.custom_field_definitions.append(
        CustomFieldDefinition(name="speed", field_type=FieldType.NUMBER)
    )
    p.custom_relation_types.append(CustomRelationType(name="docks_at"))

    e = NarrativeEntity(name="Enterprise", custom_type_id=p.custom_entity_types[0].id)
    e.custom_fields.append(CustomFieldValue(
        field_id=p.custom_field_definitions[0].id, value=9000,
    ))
    p.entities.append(e)
    store.save(p, proj_path)

    result = store.load(proj_path)
    assert isinstance(result, Ok), f"Expected Ok, got {result}"
    loaded = _unwrap(result)
    assert len(loaded.custom_entity_types) == 1
    assert len(loaded.custom_field_definitions) == 1
    assert len(loaded.custom_relation_types) == 1
    assert loaded.entities[0].custom_type_id == p.custom_entity_types[0].id
    assert loaded.entities[0].custom_fields[0].value == 9000
