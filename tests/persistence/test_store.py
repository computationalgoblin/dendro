"""
Tests for project persistence: schema versioning, atomic save/load, and error handling.

Covers the 5 required test scenarios from B01-T05:
1. Guardar y cargar proyecto vacio
2. Guardado atomico (simular error en escritura)
3. Deteccion de version desconocida
4. Error en archivo faltante
5. Error en archivo corrupto
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    detect_schema_version,
    validate_schema_version,
)
from packages.persistence.store import (
    BACKUP_SUFFIX,
    MAX_BACKUPS,
    ProjectStore,
    _create_backup,
    _read_json,
    _rotate_backups,
    _write_json_atomic,
    load_project_data,
    save_project_data,
)
from tests.persistence.conftest import write_raw_json

# =========================================================================
# Schema version tests
# =========================================================================


class TestSchemaVersioning:
    """Schema version detection and validation."""

    def test_current_version_is_positive(self):
        assert CURRENT_SCHEMA_VERSION >= 1

    def test_detect_version_present(self):
        result = detect_schema_version({"schema_version": 1})
        assert result == 1

    def test_detect_version_missing(self):
        result = detect_schema_version({})
        assert result == 0

    def test_detect_version_invalid_type(self):
        result = detect_schema_version({"schema_version": "abc"})
        assert result == 0

    def test_validate_current_version(self):
        assert validate_schema_version(CURRENT_SCHEMA_VERSION) is None

    def test_validate_legacy_version(self):
        assert validate_schema_version(1) is None

    def test_validate_future_version(self):
        error = validate_schema_version(MAX_SUPPORTED_VERSION + 1)
        assert error is not None
        assert "update" in error.lower()

    def test_validate_zero_version(self):
        error = validate_schema_version(0)
        assert error is not None

    def test_validate_negative_version(self):
        error = validate_schema_version(-1)
        assert error is not None


# =========================================================================
# JSON I/O tests
# =========================================================================


class TestJsonIO:
    """Low-level JSON read/write operations."""

    def test_read_json_valid(self, tmp_path: Path, sample_project_data: dict):
        path = tmp_path / "valid.json"
        write_raw_json(path, sample_project_data)
        result = _read_json(path)
        assert isinstance(result, Ok), f"Expected Ok, got {result}"
        assert result.value["id"] == sample_project_data["id"]

    def test_read_json_missing_file(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        result = _read_json(path)
        assert isinstance(result, Error), f"Expected Error, got {result}"
        assert "not found" in result.error

    def test_read_json_corrupt(self, tmp_path: Path):
        path = tmp_path / "corrupt.json"
        path.write_text("{invalid json", encoding="utf-8")
        result = _read_json(path)
        assert isinstance(result, Error), f"Expected Error, got {result}"
        assert "corrupt" in result.error.lower() or "invalid" in result.error.lower()

    def test_write_json_atomic(self, tmp_path: Path, sample_project_data: dict):
        path = tmp_path / "project.json"
        result = _write_json_atomic(sample_project_data, path)
        assert isinstance(result, Ok), f"Expected Ok, got {result}"
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["id"] == sample_project_data["id"]

    def test_write_json_atomic_no_intermediate_file_leak(self, tmp_path: Path):
        """After a successful write, .tmp file should not exist."""
        path = tmp_path / "clean.json"
        result = _write_json_atomic({"a": 1}, path)
        assert isinstance(result, Ok), f"Expected Ok, got {result}"
        assert not path.with_suffix(path.suffix + ".tmp").exists()


# =========================================================================
# Atomic save tests
# =========================================================================


class TestAtomicSave:
    """Atomic save guarantees (SCENARIO 2: simular corte)."""

    def test_save_and_load_roundtrip(
        self, tmp_project_dir: Path, project_file: Path, sample_project: Project
    ):
        """SCENARIO 1: guardar y cargar proyecto."""
        store = ProjectStore()

        save_result = store.save(sample_project, project_file)
        assert isinstance(save_result, Ok), (
            f"Save failed: {save_result.error}"
        )

        load_result = store.load(project_file)
        assert isinstance(load_result, Ok), (
            f"Load failed: {load_result.error}"
        )

        loaded = load_result.value
        assert loaded.id == sample_project.id
        assert loaded.name == sample_project.name
        assert loaded.metadata == sample_project.metadata

    def test_save_overwrites_previous(
        self, project_file: Path
    ):
        """Saving twice should overwrite with latest data."""
        store = ProjectStore()
        p1 = Project(id="aaa", name="First")
        p2 = Project(id="bbb", name="Second")

        store.save(p1, project_file)
        store.save(p2, project_file)

        result = store.load(project_file)
        assert isinstance(result, Ok), (
            f"Load failed: {result.error}"
        )
        assert result.value.id == "bbb"
        assert result.value.name == "Second"

    def test_backup_created_on_save(
        self, project_file: Path, sample_project: Project
    ):
        """Saving should create a backup of the previous version."""
        store = ProjectStore()

        # First save - no backup yet
        store.save(sample_project, project_file)
        assert len(store.get_backup_paths(project_file)) == 0

        # Second save - should create backup of first version
        p2 = Project(id="xyz", name="Version 2")
        store.save(p2, project_file)

        backups = store.get_backup_paths(project_file)
        assert len(backups) >= 1

    def test_backup_rotation(
        self, project_file: Path
    ):
        """After MAX_BACKUPS+ saves, old backups are pruned."""
        store = ProjectStore()
        for i in range(MAX_BACKUPS + 2):
            store.save(Project(id=f"v{i:03d}", name=f"Version {i}"), project_file)

        backups = store.get_backup_paths(project_file)
        assert len(backups) <= MAX_BACKUPS

    def test_save_preserves_json_structure(
        self, project_file: Path, sample_project: Project
    ):
        """Saved file should be valid JSON with schema_version."""
        store = ProjectStore()
        store.save(sample_project, project_file)

        raw = json.loads(project_file.read_text(encoding="utf-8"))
        assert "schema_version" in raw
        assert raw["schema_version"] == CURRENT_SCHEMA_VERSION
        assert raw["id"] == sample_project.id
        assert raw["name"] == sample_project.name

    def test_save_atomicity_partial_write(self, tmp_path: Path, sample_project: Project):
        """Simulate a write failure by making the .tmp destination unwritable.

        The atomic write protocol guarantees: if writing the .tmp file fails,
        the original destination file is never touched.

        Strategy: create the .tmp path as an unwritable directory before
        calling _write_json_atomic directly.
        """
        project_file = tmp_path / "project.json"
        store = ProjectStore()

        # First save the project normally
        assert isinstance(store.save(sample_project, project_file), Ok)

        # Create an unwritable .tmp path: make it a directory
        tmp_path_hijack = project_file.with_suffix(project_file.suffix + ".tmp")
        tmp_path_hijack.mkdir()
        tmp_path_hijack.chmod(0o444)  # read-only directory

        try:
            # Try atomic write — should fail because .tmp path is occupied
            result = _write_json_atomic(
                {"id": "new", "name": "Should fail"},
                project_file,
            )
            assert isinstance(result, Error), (
                f"Expected atomic write to fail, got {result}"
            )
        finally:
            tmp_path_hijack.chmod(0o755)
            tmp_path_hijack.rmdir()

        # The original file must still contain the original project
        loaded = store.load(project_file)
        assert isinstance(loaded, Ok), f"Original file corrupted: {loaded}"
        assert loaded.value.id == sample_project.id


# =========================================================================
# Load error handling tests
# =========================================================================


class TestLoadErrors:
    """Error handling when loading projects."""

    def test_load_missing_file(self, tmp_project_dir: Path):
        """SCENARIO 4: error en archivo faltante."""
        store = ProjectStore()
        path = tmp_project_dir / "ghost.json"
        result = store.load(path)
        assert isinstance(result, Error), f"Expected Error, got {result}"
        assert "not found" in result.error

    def test_load_corrupt_file(self, corrupt_project_file: Path):
        """SCENARIO 5: error en archivo corrupto."""
        store = ProjectStore()
        result = store.load(corrupt_project_file)
        assert isinstance(result, Error), f"Expected Error, got {result}"
        assert "corrupt" in result.error.lower() or "invalid" in result.error.lower()

    def test_load_unknown_version(self, project_file: Path):
        """SCENARIO 3: deteccion de version desconocida."""
        future_version = MAX_SUPPORTED_VERSION + 1
        write_raw_json(project_file, {
            "schema_version": future_version,
            "id": "future-proj",
            "name": "Future",
            "created_at": "2026-05-29T10:00:00+00:00",
            "updated_at": "2026-05-29T10:00:00+00:00",
        })
        store = ProjectStore()
        result = store.load(project_file)
        assert isinstance(result, Error), f"Expected Error, got {result}"
        assert "update" in result.error.lower()

    def test_load_empty_file(self, project_file: Path):
        """Loading an empty file should give a clear error."""
        project_file.write_text("", encoding="utf-8")
        store = ProjectStore()
        result = store.load(project_file)
        assert isinstance(result, Error), f"Expected Error, got {result}"

    def test_load_not_a_dict(self, project_file: Path):
        """File containing a JSON array should fail."""
        project_file.write_text('["not", "a", "dict"]', encoding="utf-8")
        store = ProjectStore()
        result = store.load(project_file)
        assert isinstance(result, Error), f"Expected Error, got {result}"


# =========================================================================
# data-level I/O tests
# =========================================================================


class TestDataLevelIO:
    """save_project_data / load_project_data (without Project model)."""

    def test_save_and_load_data(self, tmp_path: Path):
        data = {"id": "test", "name": "Raw Data"}
        path = tmp_path / "data.json"
        result = save_project_data(data, path)
        assert isinstance(result, Ok), f"Save failed: {result}"

        loaded = load_project_data(path)
        assert isinstance(loaded, Ok), f"Load failed: {loaded}"
        assert loaded.value["id"] == "test"
        assert loaded.value["schema_version"] == CURRENT_SCHEMA_VERSION

    def test_load_data_missing(self, tmp_path: Path):
        result = load_project_data(tmp_path / "nope.json")
        assert isinstance(result, Error), f"Expected Error, got {result}"

    def test_load_data_corrupt(self, tmp_path: Path):
        path = tmp_path / "bad.json"
        path.write_text("{{{", encoding="utf-8")
        result = load_project_data(path)
        assert isinstance(result, Error), f"Expected Error, got {result}"

    def test_load_data_future_version(self, tmp_path: Path):
        path = tmp_path / "future.json"
        write_raw_json(path, {
            "schema_version": MAX_SUPPORTED_VERSION + 5,
            "id": "future",
        })
        result = load_project_data(path)
        assert isinstance(result, Error), f"Expected Error, got {result}"


# =========================================================================
# Project domain tests
# =========================================================================


class TestProjectModel:
    """Project domain model basics."""

    def test_project_auto_id(self):
        p = Project()
        assert len(p.id) == 12
        assert isinstance(p.id, str)

    def test_project_name_default(self):
        p = Project()
        assert p.name == ""

    def test_project_to_dict_roundtrip(self):
        p1 = Project(id="test123", name="Roundtrip")
        d = p1.to_dict()
        p2 = Project.from_dict(d)
        assert p2.id == p1.id
        assert p2.name == p1.name

    def test_project_touch_updates_timestamp(self):
        p = Project()
        original = p.updated_at
        p.touch()
        assert p.updated_at >= original

    def test_project_metadata(self):
        p = Project(metadata={"author": "Alice", "version": "1.0"})
        d = p.to_dict()
        assert d["metadata"]["author"] == "Alice"
        assert d["metadata"]["version"] == "1.0"


# =========================================================================
# Backup management tests
# =========================================================================


class TestBackupManagement:
    """Backup creation and rotation."""

    def test_create_backup(self, project_file: Path, sample_project_data: dict):
        write_raw_json(project_file, sample_project_data)
        _create_backup(project_file)
        backups = list(project_file.parent.glob(f"{project_file.name}{BACKUP_SUFFIX}*"))
        assert len(backups) >= 1

    def test_rotate_backups_keeps_max(self, tmp_path: Path):
        base = tmp_path / "proj.json"
        base.write_text("original", encoding="utf-8")

        # Create more than MAX_BACKUPS backups
        for i in range(1, MAX_BACKUPS + 3):
            bak = Path(f"{str(base)}{BACKUP_SUFFIX}.{i}")
            bak.write_text(f"backup-{i}", encoding="utf-8")

        _rotate_backups(base)
        remaining = list(base.parent.glob(f"{base.name}{BACKUP_SUFFIX}*"))
        assert len(remaining) <= MAX_BACKUPS

    def test_backup_preserves_content(
        self, project_file: Path, sample_project: Project
    ):
        """Backup should contain the previous project data."""
        store = ProjectStore()
        store.save(sample_project, project_file)

        # Overwrite with new data
        p2 = Project(id="new-id", name="New")
        store.save(p2, project_file)

        # Verify backup exists
        backups = store.get_backup_paths(project_file)
        assert len(backups) >= 1

        # Load backup and verify it contains original project
        backup = load_project_data(backups[0])
        assert isinstance(backup, Ok), f"Could not load backup: {backup}"
        assert backup.value["id"] == sample_project.id


# =========================================================================
# Exists and metadata tests
# =========================================================================


class TestProjectStoreMetadata:
    """ProjectStore utility methods."""

    def test_exists_returns_true(self, project_file: Path, sample_project: Project):
        store = ProjectStore()
        assert not store.exists(project_file)
        store.save(sample_project, project_file)
        assert store.exists(project_file)

    def test_exists_returns_false(self, tmp_project_dir: Path):
        store = ProjectStore()
        assert not store.exists(tmp_project_dir / "nope.json")

    def test_get_backup_paths_empty(self, project_file: Path):
        store = ProjectStore()
        assert store.get_backup_paths(project_file) == []

    def test_get_backup_paths_after_saves(
        self, project_file: Path, sample_project: Project
    ):
        store = ProjectStore()
        store.save(sample_project, project_file)
        store.save(Project(id="v2"), project_file)
        backups = store.get_backup_paths(project_file)
        assert len(backups) >= 1
        # Newest backup should come first
        assert backups[0].suffixes[-2] == BACKUP_SUFFIX
