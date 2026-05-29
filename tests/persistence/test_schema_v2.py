"""Tests for B02-T03: Persistencia extendida y esquema v2.

Covers:
- Schema v2 constants and migration v1→v2
- Structural validation (required fields, types)
- ProjectStore v2 roundtrip (full project save/load)
- V1→v2 migration through ProjectStore.load
- Modify config → save → reload → verify
- Corrupt structure detection
- Future version rejection
- Regression: v2 projects save with schema_version=2
"""

import json
from pathlib import Path

from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v1_to_v2,
    validate_project_structure,
)
from packages.persistence.store import ProjectStore, save_project_data


class TestSchemaVersionB02T03:
    def test_current_schema_is_v2(self):
        assert CURRENT_SCHEMA_VERSION == 5

    def test_max_supported_is_v2(self):
        assert MAX_SUPPORTED_VERSION == 5


class TestMigrationV1ToV2:
    def test_migration_adds_scalar_fields(self):
        v1 = {"id": "a", "name": "test"}
        m = _apply_migration_v1_to_v2(v1)
        assert m["description"] == ""
        assert m["primary_language"] == "es"
        assert m["secondary_languages"] == []

    def test_migration_adds_config_sections(self):
        v1 = {"id": "a", "name": "test"}
        m = _apply_migration_v1_to_v2(v1)
        assert isinstance(m["general"], dict)
        assert m["general"]["theme"] == ""
        assert isinstance(m["ai"], dict)
        assert m["ai"]["enabled"] is False
        assert isinstance(m["project_metadata"], dict)
        assert m["project_metadata"]["version"] == "0.1.0"

    def test_migration_adds_empty_collections(self):
        v1 = {"id": "a", "name": "test"}
        m = _apply_migration_v1_to_v2(v1)
        assert m["entities"] == []
        assert m["relations"] == []
        assert m["sources"] == []
        assert m["history"] == []
        assert m["issues"] == []

    def test_migration_preserves_existing_fields(self):
        v1 = {"id": "abc", "name": "original", "metadata": {"k": "v"}}
        m = _apply_migration_v1_to_v2(v1)
        assert m["id"] == "abc"
        assert m["name"] == "original"
        assert m["metadata"] == {"k": "v"}

    def test_migration_does_not_invent_narrative_data(self):
        v1 = {"id": "a", "name": "test"}
        m = _apply_migration_v1_to_v2(v1)
        assert m["entities"] == []
        assert m["relations"] == []
        assert m["history"] == []
        assert m["issues"] == []
        for collection in ("entities", "relations", "history", "issues"):
            assert len(m[collection]) == 0, (
                f"Migration invented data in '{collection}'!"
            )

    def test_migration_does_not_mutate_original(self):
        v1 = {"id": "a", "name": "test"}
        _apply_migration_v1_to_v2(v1)
        assert "description" not in v1
        assert "general" not in v1


class TestStructuralValidation:
    def test_valid_v2_passes(self):
        data = {
            "id": "x", "name": "ok",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "general": {}, "entities": [],
        }
        assert validate_project_structure(data) is None

    def test_missing_id(self):
        data = {
            "name": "no_id",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        err = validate_project_structure(data)
        assert err is not None
        assert "id" in err

    def test_missing_created_at(self):
        data = {
            "id": "x", "name": "no_date",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        err = validate_project_structure(data)
        assert err is not None
        assert "created_at" in err

    def test_config_section_wrong_type(self):
        data = {
            "id": "x", "name": "bad",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "general": "not_a_dict",
        }
        err = validate_project_structure(data)
        assert err is not None
        assert "general" in err

    def test_collection_wrong_type(self):
        data = {
            "id": "x", "name": "bad",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "entities": "not_a_list",
        }
        err = validate_project_structure(data)
        assert err is not None
        assert "entities" in err


class TestProjectStoreV2:
    def test_save_produces_schema_version_2(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="v2test")
        path = tmp_path / "v2.json"
        result = store.save(p, path)
        assert isinstance(result, Ok), f"Save failed: {result}"

        raw = json.loads(path.read_text("utf-8"))
        assert raw.get("schema_version") == 5

    def test_save_load_roundtrip_full_project(self, tmp_path: Path):
        from packages.domain.entity import NarrativeEntity, EntityType

        from packages.domain.relation import NarrativeRelation

        store = ProjectStore()
        p = Project(name="Full", description="All fields")
        p.primary_language = "en"
        p.secondary_languages = ["fr", "de"]
        p.general.theme = "dark fantasy"
        p.tone.narrative_tone = "dark"
        p.genre.primary_genre = "Fantasy"
        p.realism.magic_level = "high"
        p.ai.enabled = True
        p.visibility.default_entity_visibility = "privado"
        p.export.export_format_preference = "pdf"
        p.project_metadata.author = "Alice"
        p.metadata["custom"] = "val"
        p.entities.append(NarrativeEntity(name="Orc", entity_type=EntityType.CRIATURA))
        from packages.domain.source_history import Source, HistoryEntry, HistoryEventType

        p.relations.append(NarrativeRelation(source_id="x", target_id="y"))
        p.sources.append(Source(name="src1"))
        p.history.append(HistoryEntry(event_type=HistoryEventType.CREACION_ENTIDAD))
        from packages.domain.candidate_issue import Issue
        p.issues.append(Issue(title="issue1"))

        path = tmp_path / "full.json"
        save_result = store.save(p, path)
        assert isinstance(save_result, Ok), f"Save failed: {save_result}"

        load_result = store.load(path)
        assert isinstance(load_result, Ok), f"Load failed: {load_result}"

        p2 = load_result.value
        assert p2.name == "Full"
        assert p2.description == "All fields"
        assert p2.primary_language == "en"
        assert p2.secondary_languages == ["fr", "de"]
        assert p2.general.theme == "dark fantasy"
        assert p2.tone.narrative_tone == "dark"
        assert p2.genre.primary_genre == "Fantasy"
        assert p2.realism.magic_level == "high"
        assert p2.ai.enabled is True
        assert p2.visibility.default_entity_visibility == "privado"
        assert p2.export.export_format_preference == "pdf"
        assert p2.project_metadata.author == "Alice"
        assert p2.metadata["custom"] == "val"
        assert len(p2.entities) == 1
        assert p2.entities[0].name == "Orc"
        assert len(p2.relations) == 1
        assert p2.relations[0].source_id == "x"
        assert len(p2.sources) == 1
        assert p2.sources[0].name == "src1"
        assert len(p2.history) == 1
        assert len(p2.issues) == 1
        assert p2.issues[0].title == "issue1"

    def test_save_load_collections_preserved(self, tmp_path: Path):
        from packages.domain.entity import NarrativeEntity, EntityType
        from packages.domain.relation import NarrativeRelation
        from packages.domain.source_history import HistoryEventType, Source, HistoryEntry

        store = ProjectStore()
        p = Project(name="Full")
        p.entities = [NarrativeEntity(name="E1"), NarrativeEntity(name="E2")]
        p.relations = [NarrativeRelation(source_id="a", target_id="b"),
                       NarrativeRelation(source_id="c", target_id="d")]

        path = tmp_path / "colls.json"
        store.save(p, path)
        loaded = store.load(path)
        assert isinstance(loaded, Ok)
        p2 = loaded.value
        assert len(p2.entities) == 2
        assert p2.entities[0].name == "E1"
        assert p2.entities[1].name == "E2"
        assert len(p2.relations) == 2


class TestV1MigrationThroughStore:
    def test_load_v1_project_applies_migration(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "v1_project.json"

        v1_data = {
            "schema_version": 1,
            "id": "abc111222333",
            "name": "legacy_project",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
            "metadata": {"legacy_key": "legacy_val"},
        }
        path.write_text(json.dumps(v1_data), encoding="utf-8")

        result = store.load(path)
        assert isinstance(result, Ok), f"V1 load failed: {result}"

        p = result.value
        assert p.id == "abc111222333"
        assert p.name == "legacy_project"
        assert p.metadata == {"legacy_key": "legacy_val"}
        assert p.description == ""
        assert p.primary_language == "es"
        assert p.secondary_languages == []
        assert p.general.theme == ""
        assert p.ai.enabled is False
        assert p.project_metadata.author == ""
        assert p.entities == []
        assert p.relations == []
        assert p.sources == []
        assert p.history == []
        assert p.issues == []

    def test_load_v1_no_narrative_data_invented(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "v1.json"
        v1_data = {
            "schema_version": 1,
            "id": "abc", "name": "test",
            "created_at": "2026-05-01T00:00:00+00:00",
            "updated_at": "2026-05-01T00:00:00+00:00",
        }
        path.write_text(json.dumps(v1_data), encoding="utf-8")

        result = store.load(path)
        assert isinstance(result, Ok)
        p = result.value
        assert p.entities == []
        assert p.relations == []
        assert p.sources == []
        assert p.history == []
        assert p.issues == []


class TestModifyConfigRoundtrip:
    def test_modify_general_config_persists(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="ModTest")
        path = tmp_path / "mod.json"

        store.save(p, path)
        p.general.theme = "cyberpunk"
        p.general.tags = ["hackers", "megacorps"]
        store.save(p, path)

        result = store.load(path)
        assert isinstance(result, Ok)
        p2 = result.value
        assert p2.general.theme == "cyberpunk"
        assert p2.general.tags == ["hackers", "megacorps"]

    def test_modify_tone_config_persists(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="ToneTest")
        path = tmp_path / "tone.json"

        store.save(p, path)
        p.tone.narrative_tone = "dark"
        p.tone.humor_level = "low"
        store.save(p, path)

        result = store.load(path)
        assert isinstance(result, Ok)
        p2 = result.value
        assert p2.tone.narrative_tone == "dark"
        assert p2.tone.humor_level == "low"
        assert p2.tone.language_formality == "neutral"

    def test_modify_multiple_configs_persists(self, tmp_path: Path):
        store = ProjectStore()
        p = Project(name="MultiTest")
        path = tmp_path / "multi.json"

        store.save(p, path)
        p.general.theme = "steampunk"
        p.genre.primary_genre = "Science Fiction"
        p.realism.technology_level = "high"
        p.ai.enabled = True
        p.visibility.default_entity_visibility = "privado"
        p.project_metadata.author = "Jules Verne"
        store.save(p, path)

        result = store.load(path)
        assert isinstance(result, Ok)
        p2 = result.value
        assert p2.general.theme == "steampunk"
        assert p2.genre.primary_genre == "Science Fiction"
        assert p2.realism.technology_level == "high"
        assert p2.ai.enabled is True
        assert p2.visibility.default_entity_visibility == "privado"
        assert p2.project_metadata.author == "Jules Verne"


class TestLoadStructuralErrors:
    def test_load_missing_required_field(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "missing.json"
        path.write_text(json.dumps({
            "schema_version": 2,
            "name": "no_id",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }), encoding="utf-8")
        result = store.load(path)
        assert isinstance(result, Error)
        assert "id" in result.error

    def test_load_config_section_wrong_type(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "badtype.json"
        path.write_text(json.dumps({
            "schema_version": 3,
            "id": "x", "name": "bad",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "general": "should_be_dict",
        }), encoding="utf-8")
        result = store.load(path)
        assert isinstance(result, Error)
        assert "general" in result.error

    def test_load_collection_wrong_type(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "badcoll.json"
        path.write_text(json.dumps({
            "schema_version": 3,
            "id": "x", "name": "bad",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "entities": "not_a_list",
        }), encoding="utf-8")
        result = store.load(path)
        assert isinstance(result, Error)
        assert "entities" in result.error

    def test_load_future_version_rejected(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "future.json"
        path.write_text(json.dumps({
            "schema_version": 99,
            "id": "x", "name": "future",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }), encoding="utf-8")
        result = store.load(path)
        assert isinstance(result, Error)
        assert "v99" in result.error


class TestRegressionB02T03:
    def test_atomic_save_still_works(self, tmp_path: Path):
        path = tmp_path / "atomic.json"
        data = {
            "id": "atom", "name": "atomic_test",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        result = save_project_data(data, path)
        assert isinstance(result, Ok)
        assert path.is_file()

    def test_backup_rotation_still_works(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "backup.json"

        for i in range(5):
            p = Project(name=f"version_{i}")
            store.save(p, path)

        backup_paths = store.get_backup_paths(path)
        assert len(backup_paths) >= 1

    def test_exists_still_works(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "exists.json"
        assert not store.exists(path)
        p = Project(name="exists")
        store.save(p, path)
        assert store.exists(path)
