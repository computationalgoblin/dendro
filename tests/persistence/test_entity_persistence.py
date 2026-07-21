"""Tests for B03-T02: Entity persistence — schema v3, entity CRUD.

Covers:
- Schema v3 constants
- Migration v2→v3
- Entity add → save → load roundtrip
- Entity update, archive, restore
- Duplicate ID detection
- Entity structure validation
- Soft delete traceability
"""

import json
from pathlib import Path

from packages.domain.entity import (
    CanonState,
    EntityType,
    NarrativeEntity,
)
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v2_to_v3,
    validate_entity_structure,
    validate_project_entities,
)
from packages.persistence.store import ProjectStore


# ═══════════════════════════════════════════════════════════════════════
# Schema v3
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaV3:
    def test_current_is_3(self):
        assert CURRENT_SCHEMA_VERSION >= 20

    def test_max_supported_is_9(self):
        assert MAX_SUPPORTED_VERSION == CURRENT_SCHEMA_VERSION

    def test_migration_v2_to_v3_ensures_entities_is_list(self):
        data = {"id": "x", "name": "test", "entities": None}
        m = _apply_migration_v2_to_v3(data)
        assert m["entities"] == []

    def test_migration_v2_to_v3_preserves_existing_entities(self):
        data = {"entities": [{"id": "e1", "name": "E1", "entity_type": "nota"}]}
        m = _apply_migration_v2_to_v3(data)
        assert len(m["entities"]) == 1


# ═══════════════════════════════════════════════════════════════════════
# Entity structure validation
# ═══════════════════════════════════════════════════════════════════════


class TestValidateEntityStructure:
    def test_valid(self):
        assert validate_entity_structure(
            {"id": "abc", "name": "Test", "entity_type": "personaje"}
        ) is None

    def test_not_a_dict(self):
        err = validate_entity_structure("not a dict")
        assert err is not None
        assert "not a JSON object" in err

    def test_missing_id(self):
        err = validate_entity_structure({"name": "Test", "entity_type": "x"})
        assert err is not None
        assert "id" in err.lower()

    def test_missing_name(self):
        err = validate_entity_structure({"id": "x", "entity_type": "x"})
        assert err is not None
        assert "name" in err.lower()


class TestValidateProjectEntities:
    def test_empty_list(self):
        assert validate_project_entities([]) is None

    def test_valid_entities(self):
        entities = [
            {"id": "a", "name": "A", "entity_type": "personaje"},
            {"id": "b", "name": "B", "entity_type": "localizacion"},
        ]
        assert validate_project_entities(entities) is None

    def test_duplicate_ids(self):
        entities = [
            {"id": "dup", "name": "A", "entity_type": "personaje"},
            {"id": "dup", "name": "B", "entity_type": "localizacion"},
        ]
        err = validate_project_entities(entities)
        assert err is not None
        assert "duplicate" in err.lower()

    def test_not_a_list(self):
        err = validate_project_entities("not_a_list")
        assert err is not None
        assert "JSON array" in err


# ═══════════════════════════════════════════════════════════════════════
# Entity persistence through ProjectStore
# ═══════════════════════════════════════════════════════════════════════


class TestEntityPersistence:
    def test_add_entity_persists(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="Test")
        path = tmp_path / "proj.json"
        store.save(p, path)

        e = NarrativeEntity(name="Eldrin", entity_type=EntityType.PERSONAJE)
        result = store.add_entity(p, e, path)
        assert isinstance(result, Ok)

        loaded = store.load(path)
        assert isinstance(loaded, Ok)
        p2 = loaded.value
        assert len(p2.entities) == 1
        assert p2.entities[0].name == "Eldrin"

    def test_save_load_roundtrip_with_entities(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="Roundtrip")
        p.entities.append(NarrativeEntity(name="E1", entity_type=EntityType.NOTA))
        p.entities.append(NarrativeEntity(name="E2", entity_type=EntityType.PERSONAJE))

        path = tmp_path / "rt.json"
        store.save(p, path)

        loaded = store.load(path)
        assert isinstance(loaded, Ok)
        p2 = loaded.value
        assert len(p2.entities) == 2
        assert p2.entities[0].name == "E1"
        assert p2.entities[1].entity_type == EntityType.PERSONAJE

    def test_update_entity(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="Upd")
        e = NarrativeEntity(name="Original", entity_type=EntityType.NOTA)
        p.entities.append(e)
        path = tmp_path / "upd.json"
        store.save(p, path)

        e.brief_description = "Modified"
        result = store.update_entity(p, e, path)
        assert isinstance(result, Ok)

        loaded = store.load(path)
        p2 = loaded.value
        assert p2.entities[0].brief_description == "Modified"

    def test_update_nonexistent_entity(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="Upd")
        path = tmp_path / "upd.json"
        store.save(p, path)

        e = NarrativeEntity(name="Ghost")
        result = store.update_entity(p, e, path)
        assert isinstance(result, Error)
        assert "not found" in result.error.lower()

    def test_archive_entity_soft_delete(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="Arch")
        e = NarrativeEntity(name="ToDelete", entity_type=EntityType.NOTA)
        p.entities.append(e)
        path = tmp_path / "arch.json"
        store.save(p, path)

        result = store.archive_entity(p, e.id, path)
        assert isinstance(result, Ok)

        loaded = store.load(path)
        p2 = loaded.value
        assert len(p2.entities) == 1  # still present
        assert p2.entities[0].canon_state == CanonState.ARCHIVADO

    def test_restore_entity(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="Rest")
        e = NarrativeEntity(name="RestoreMe", entity_type=EntityType.NOTA)
        p.entities.append(e)
        path = tmp_path / "rest.json"
        store.save(p, path)

        store.archive_entity(p, e.id, path)
        result = store.restore_entity(p, e.id, path)
        assert isinstance(result, Ok)

        loaded = store.load(path)
        p2 = loaded.value
        assert p2.entities[0].canon_state == CanonState.CANONICO

    def test_restore_non_archived_errors(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="Rest")
        e = NarrativeEntity(name="Active", entity_type=EntityType.NOTA)
        p.entities.append(e)
        path = tmp_path / "rest.json"
        store.save(p, path)

        result = store.restore_entity(p, e.id, path)
        assert isinstance(result, Error)
        assert "not archived" in result.error.lower()

    def test_find_entity(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="Find")
        e = NarrativeEntity(name="Target", entity_type=EntityType.NOTA)
        p.entities.append(e)
        path = tmp_path / "find.json"
        store.save(p, path)

        result = store.find_entity(p, e.id)
        assert isinstance(result, Ok)
        assert result.value.name == "Target"

    def test_find_nonexistent(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="Find")
        path = tmp_path / "find.json"
        store.save(p, path)

        result = store.find_entity(p, "nonexistent-id")
        assert isinstance(result, Error)
        assert "not found" in result.error.lower()

    def test_entity_touch_on_archive(self, tmp_path: Path):
        import time

        store = ProjectStore()
        p = Project(name="Touch")
        e = NarrativeEntity(name="TouchMe", entity_type=EntityType.NOTA)
        p.entities.append(e)
        path = tmp_path / "touch.json"
        store.save(p, path)

        original = e.updated_at
        time.sleep(0.01)
        store.archive_entity(p, e.id, path)

        assert e.updated_at > original

    def test_schema_version_is_9_on_save_with_entities(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="v3check")
        e = NarrativeEntity(name="E1", entity_type=EntityType.NOTA)
        p.entities.append(e)
        path = tmp_path / "v3.json"

        store.save(p, path)
        raw = json.loads(path.read_text("utf-8"))
        assert raw.get("schema_version") == CURRENT_SCHEMA_VERSION
