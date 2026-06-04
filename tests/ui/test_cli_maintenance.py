from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def _cli(args: str, *, project: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(WORKSPACE)}
    cmd = [sys.executable, "-m", "narrative_architect"]
    if project is not None:
        cmd.extend(["--project", str(project)])
    cmd.extend(shlex.split(args))
    return subprocess.run(cmd, cwd=WORKSPACE, env=env, text=True, capture_output=True, check=False)


def _create_project(path: Path) -> None:
    result = _cli(f"project create Smoke --path {path}")
    assert result.returncode == 0, result.stderr + result.stdout
    assert path.exists()


def test_maintenance_help_and_dispatch_are_registered() -> None:
    root = _cli("--help")
    assert root.returncode == 0
    assert "maintenance" in root.stdout

    help_result = _cli("maintenance --help")
    assert help_result.returncode == 0
    assert "doctor" in help_result.stdout
    assert "repair-plan" in help_result.stdout


def test_doctor_size_and_export_diagnostic_json_are_parseable(tmp_path: Path) -> None:
    project = tmp_path / "project.json"
    output = tmp_path / "diagnostic.json"
    _create_project(project)

    doctor = _cli("maintenance doctor --json", project=project)
    assert doctor.returncode == 0, doctor.stderr
    data = json.loads(doctor.stdout)
    assert data["project_name"] == "Smoke"
    assert data["counts"]["entities"] == 0

    size = _cli("maintenance size --json", project=project)
    assert size.returncode == 0, size.stderr
    size_data = json.loads(size.stdout)
    assert size_data["file_bytes"] > 0
    assert size_data["diagnostic"]["serialized_json_bytes"] > 0

    exported = _cli(f"maintenance export-diagnostic --output {output} --json", project=project)
    assert exported.returncode == 0, exported.stderr
    exported_data = json.loads(exported.stdout)
    assert exported_data["output"] == str(output)
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["project_name"] == "Smoke"


def test_backup_restore_and_list_json(tmp_path: Path) -> None:
    project = tmp_path / "project.json"
    _create_project(project)

    backup = _cli("maintenance backup --json", project=project)
    assert backup.returncode == 0, backup.stderr
    backup_data = json.loads(backup.stdout)
    backup_path = Path(backup_data["backup_path"])
    assert backup_path.exists()

    project.write_text('{"schema_version": 20, "id": "broken"}', encoding="utf-8")
    restore = _cli(f"maintenance restore --backup {backup_path} --json", project=project)
    assert restore.returncode == 0, restore.stderr
    restore_data = json.loads(restore.stdout)
    assert restore_data["restored_from"] == str(backup_path)
    assert json.loads(project.read_text(encoding="utf-8"))["name"] == "Smoke"

    listed = _cli("maintenance backups --json", project=project)
    assert listed.returncode == 0, listed.stderr
    listed_data = json.loads(listed.stdout)
    assert any(row["path"] == str(backup_path) for row in listed_data["backups"])


def test_repair_plan_is_parseable_and_non_destructive(tmp_path: Path) -> None:
    project = tmp_path / "project.json"
    _create_project(project)
    before = project.read_text(encoding="utf-8")

    result = _cli("maintenance repair-plan --json", project=project)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["mutates_project"] is False
    assert data["requires_explicit_apply"] is True
    assert project.read_text(encoding="utf-8") == before
