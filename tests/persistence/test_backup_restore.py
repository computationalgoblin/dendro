from __future__ import annotations

import json

from packages.application.project_maintenance_service import ProjectMaintenanceService
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.persistence.schema import CURRENT_SCHEMA_VERSION
from packages.persistence.store import ProjectStore


def test_create_backup_creates_verifiable_versioned_copy(tmp_path) -> None:
    path = tmp_path / "project.json"
    store = ProjectStore()
    assert isinstance(store.save(Project(name="Backup me"), path), Ok)

    result = store.create_backup(path)

    assert isinstance(result, Ok)
    backup_path = result.value
    assert backup_path.exists()
    assert backup_path.name.startswith("project.json.bak.")
    data = json.loads(backup_path.read_text(encoding="utf-8"))
    assert data["name"] == "Backup me"
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION


def test_restore_backup_validates_schema_before_replacing_current_file(tmp_path) -> None:
    path = tmp_path / "project.json"
    invalid_backup = tmp_path / "invalid.json.bak.1"
    store = ProjectStore()
    assert isinstance(store.save(Project(name="Current"), path), Ok)
    invalid_backup.write_text(json.dumps({"schema_version": CURRENT_SCHEMA_VERSION + 1}), encoding="utf-8")

    result = store.restore_backup(path, invalid_backup)

    assert isinstance(result, Error)
    loaded = store.load(path)
    assert isinstance(loaded, Ok)
    assert loaded.value.name == "Current"


def test_restore_backup_replaces_current_only_after_valid_backup_and_preserves_previous(tmp_path) -> None:
    path = tmp_path / "project.json"
    store = ProjectStore()
    assert isinstance(store.save(Project(name="Current"), path), Ok)
    backup = store.create_backup(path).value
    assert isinstance(store.save(Project(name="New"), path), Ok)

    result = store.restore_backup(path, backup)

    assert isinstance(result, Ok)
    loaded = store.load(path)
    assert isinstance(loaded, Ok)
    assert loaded.value.name == "Current"
    restore_safety_backup = result.value
    assert restore_safety_backup.exists()
    assert json.loads(restore_safety_backup.read_text(encoding="utf-8"))["name"] == "New"


def test_project_maintenance_service_wraps_backup_restore_with_clear_results(tmp_path) -> None:
    path = tmp_path / "project.json"
    service = ProjectMaintenanceService(ProjectStore())
    assert isinstance(ProjectStore().save(Project(name="Via service"), path), Ok)

    backup = service.create_backup(path)
    assert isinstance(backup, Ok)
    assert backup.value.exists()

    restore = service.restore_backup(path, backup.value)
    assert isinstance(restore, Ok)
