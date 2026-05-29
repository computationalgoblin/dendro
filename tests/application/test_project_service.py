"""Tests for B02-T02: ProjectService — application-layer project lifecycle.

Covers:
- create with defaults and config overrides
- open from file (success + error cases)
- save / save_as
- close (with and without active project)
- validate (empty name, etc.)
- get_config / update_config (nested paths)
- modify → save → reload roundtrip
- get_schema_version
"""

import json
from pathlib import Path

from packages.application.project_service import ProjectService
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    def test_create_with_defaults(self):
        svc = ProjectService()
        result = svc.create()
        assert isinstance(result, Ok)
        p = result.value
        assert p.name == ""
        assert p.primary_language == "es"
        assert p.description == ""

    def test_create_with_name(self):
        svc = ProjectService()
        result = svc.create(name="Fantasy World")
        assert isinstance(result, Ok)
        assert result.value.name == "Fantasy World"

    def test_create_sets_active_project(self):
        svc = ProjectService()
        assert svc.active_project is None
        svc.create(name="Test")
        assert svc.active_project is not None
        assert svc.active_project.name == "Test"

    def test_create_with_config_overrides(self):
        svc = ProjectService()
        result = svc.create(
            name="Overridden",
            config_overrides={
                "description": "A test world",
                "primary_language": "en",
                "secondary_languages": ["fr"],
                "general.theme": "cyberpunk",
                "tone.narrative_tone": "dark",
                "ai.enabled": True,
            },
        )
        assert isinstance(result, Ok)
        p = result.value
        assert p.description == "A test world"
        assert p.primary_language == "en"
        assert p.secondary_languages == ["fr"]
        assert p.general.theme == "cyberpunk"
        assert p.tone.narrative_tone == "dark"
        assert p.ai.enabled is True

    def test_create_with_invalid_config_path(self):
        svc = ProjectService()
        result = svc.create(
            config_overrides={"nonexistent.field": "value"}
        )
        assert isinstance(result, Error)
        assert "nonexistent" in result.error


# ---------------------------------------------------------------------------
# open
# ---------------------------------------------------------------------------


class TestOpen:
    def test_open_existing_file(self, tmp_path: Path):
        store = ProjectStore()
        svc = ProjectService(store=store)
        svc.create(name="ToSave")

        path = tmp_path / "project.json"
        store.save(svc.active_project, path)
        svc.close()

        result = svc.open(path)
        assert isinstance(result, Ok)
        assert result.value.name == "ToSave"
        assert svc.active_project is not None

    def test_open_file_not_found(self):
        svc = ProjectService()
        result = svc.open(Path("/tmp/nonexistent_b02t02_test.json"))
        assert isinstance(result, Error)

    def test_open_corrupt_file(self, tmp_path: Path):
        svc = ProjectService()
        path = tmp_path / "corrupt.json"
        path.write_text("not valid json {{{", encoding="utf-8")
        result = svc.open(path)
        assert isinstance(result, Error)

    def test_open_sets_active_project(self, tmp_path: Path):
        store = ProjectStore()
        svc = ProjectService(store=store)
        svc.create(name="Before")
        path = tmp_path / "proj.json"
        store.save(svc.active_project, path)
        svc.close()

        assert svc.active_project is None
        svc.open(path)
        assert svc.active_project is not None


# ---------------------------------------------------------------------------
# save / save_as
# ---------------------------------------------------------------------------


class TestSave:
    def test_save_creates_file(self, tmp_path: Path):
        svc = ProjectService()
        svc.create(name="SaveTest")
        path = tmp_path / "save.json"

        result = svc.save(path)
        assert isinstance(result, Ok)
        assert path.is_file()

    def test_save_with_no_active_project(self):
        svc = ProjectService()
        result = svc.save(Path("/tmp/irrelevant.json"))
        assert isinstance(result, Error)
        assert "No active project" in result.error

    def test_save_as_new_path(self, tmp_path: Path):
        svc = ProjectService()
        svc.create(name="SaveAsTest")

        path1 = tmp_path / "original.json"
        path2 = tmp_path / "copy.json"

        svc.save(path1)
        result = svc.save_as(path2)
        assert isinstance(result, Ok)
        assert path2.is_file()


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    def test_close_clears_active_project(self):
        svc = ProjectService()
        svc.create(name="ToClose")
        assert svc.active_project is not None

        result = svc.close()
        assert isinstance(result, Ok)
        assert svc.active_project is None

    def test_close_when_no_active_is_noop(self):
        svc = ProjectService()
        assert svc.active_project is None

        result = svc.close()
        assert isinstance(result, Ok)
        assert svc.active_project is None

    def test_close_is_idempotent(self):
        svc = ProjectService()
        svc.close()
        svc.close()
        assert svc.active_project is None


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidate:
    def test_valid_project_no_issues(self):
        svc = ProjectService()
        svc.create(name="Valid Project")
        result = svc.validate()
        assert isinstance(result, Ok)
        assert result.value == []

    def test_empty_name_detected(self):
        svc = ProjectService()
        svc.create(name="")
        result = svc.validate()
        assert isinstance(result, Ok)
        assert len(result.value) == 1
        assert "name" in result.value[0].lower()

    def test_whitespace_name_detected(self):
        svc = ProjectService()
        svc.create(name="   ")
        result = svc.validate()
        assert isinstance(result, Ok)
        assert len(result.value) == 1

    def test_validate_with_explicit_project(self):
        svc = ProjectService()
        svc.create(name="Active")
        result = svc.validate(svc.active_project)
        assert isinstance(result, Ok)
        assert result.value == []

    def test_validate_no_project(self):
        svc = ProjectService()
        result = svc.validate()
        assert isinstance(result, Error)
        assert "No project" in result.error


# ---------------------------------------------------------------------------
# get_config
# ---------------------------------------------------------------------------


class TestGetConfig:
    def test_get_top_level(self):
        svc = ProjectService()
        svc.create(name="ConfigTest")
        result = svc.get_config("primary_language")
        assert isinstance(result, Ok)
        assert result.value == "es"

    def test_get_nested_one_level(self):
        svc = ProjectService()
        svc.create()
        result = svc.get_config("general.theme")
        assert isinstance(result, Ok)
        assert result.value == ""

    def test_get_nested_two_levels(self):
        svc = ProjectService()
        svc.create()
        # ai is a dataclass with boolean enabled field
        result = svc.get_config("ai.enabled")
        assert isinstance(result, Ok)
        assert result.value is False

    def test_get_invalid_path(self):
        svc = ProjectService()
        svc.create()
        result = svc.get_config("nonexistent.field")
        assert isinstance(result, Error)

    def test_get_with_explicit_project(self):
        svc = ProjectService()
        from packages.domain.project import Project

        p = Project(name="Explicit", description="test desc")
        result = svc.get_config("description", project=p)
        assert isinstance(result, Ok)
        assert result.value == "test desc"

    def test_get_no_project(self):
        svc = ProjectService()
        result = svc.get_config("name")
        assert isinstance(result, Error)
        assert "No project" in result.error


# ---------------------------------------------------------------------------
# update_config
# ---------------------------------------------------------------------------


class TestUpdateConfig:
    def test_update_top_level(self):
        svc = ProjectService()
        svc.create()
        result = svc.update_config("description", "New description")
        assert isinstance(result, Ok)
        assert svc.active_project.description == "New description"

    def test_update_nested(self):
        svc = ProjectService()
        svc.create()
        result = svc.update_config("general.theme", "steampunk")
        assert isinstance(result, Ok)
        assert svc.active_project.general.theme == "steampunk"

    def test_update_invalid_path(self):
        svc = ProjectService()
        svc.create()
        result = svc.update_config("nonexistent.field", "val")
        assert isinstance(result, Error)

    def test_update_with_persist(self, tmp_path: Path):
        store = ProjectStore()
        svc = ProjectService(store=store)
        svc.create(name="PersistTest")
        path = tmp_path / "persist.json"

        result = svc.update_config(
            "general.theme", "horror", path=path
        )
        assert isinstance(result, Ok)

        # Verify persisted
        loaded = store.load(path)
        assert isinstance(loaded, Ok)
        assert loaded.value.general.theme == "horror"


# ---------------------------------------------------------------------------
# modify → save → reload roundtrip
# ---------------------------------------------------------------------------


class TestModifySaveReloadRoundtrip:
    def test_full_cycle(self, tmp_path: Path):
        store = ProjectStore()
        svc = ProjectService(store=store)
        svc.create(name="CycleTest")

        # Modify multiple configs
        svc.update_config("general.theme", "dark fantasy")
        svc.update_config("genre.primary_genre", "Fantasy")
        svc.update_config("ai.enabled", True)
        svc.update_config("project_metadata.author", "Tolkien")
        svc.update_config("description", "Middle Earth")

        # Save, close, open, verify
        path = tmp_path / "cycle.json"
        svc.save(path)
        svc.close()

        result = svc.open(path)
        assert isinstance(result, Ok)
        p = result.value
        assert p.name == "CycleTest"
        assert p.description == "Middle Earth"
        assert p.general.theme == "dark fantasy"
        assert p.genre.primary_genre == "Fantasy"
        assert p.ai.enabled is True
        assert p.project_metadata.author == "Tolkien"


# ---------------------------------------------------------------------------
# get_schema_version
# ---------------------------------------------------------------------------


class TestGetSchemaVersion:
    def test_returns_four(self):
        svc = ProjectService()
        assert svc.get_schema_version() == 5
