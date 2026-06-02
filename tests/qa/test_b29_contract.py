from __future__ import annotations

import copy
import json
import os
import shlex
from tests._helpers import _split_cli
import subprocess
import sys
from pathlib import Path

from packages.application.diagnostic_service import DiagnosticService
from packages.application.project_maintenance_service import ProjectMaintenanceService
from packages.application.repair_plan_service import RepairPlanService
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.persistence.store import ProjectStore
from scripts.generate_large_project import build_large_project

WORKSPACE = Path(__file__).resolve().parents[2]


def _cli(args: str, *, project: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(WORKSPACE)}
    cmd = [sys.executable, "-m", "narrative_architect"]
    if project is not None:
        cmd.extend(["--project", str(project)])
    cmd.extend(_split_cli(args))
    return subprocess.run(cmd, cwd=WORKSPACE, env=env, text=True, capture_output=True, check=False)


def test_b29_migration_v18_to_current_adds_saved_graph_views(tmp_path: Path) -> None:
    path = tmp_path / "legacy_v18.json"
    legacy = Project(id="p", name="Legacy").to_dict()
    legacy["schema_version"] = 18
    legacy.pop("saved_graph_views", None)
    path.write_text(json.dumps(legacy), encoding="utf-8")

    result = ProjectStore().load(path)

    assert isinstance(result, Ok)
    project = result.value
    assert project.saved_graph_views == []


def test_b29_backup_restore_diagnostic_and_repair_plan_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "large.json"
    project = build_large_project(entity_count=60, relation_count=120, history_count=40)
    save_result = ProjectStore().save(project, path)
    assert isinstance(save_result, Ok)

    maintenance = ProjectMaintenanceService()
    backup = maintenance.create_backup(path)
    assert isinstance(backup, Ok)
    assert backup.value.exists()

    before = path.read_text(encoding="utf-8")
    path.write_text('{"schema_version": 19, "id": "broken"}', encoding="utf-8")
    restore = maintenance.restore_backup(path, backup.value)
    assert isinstance(restore, Ok)
    assert path.read_text(encoding="utf-8") == before

    loaded = ProjectStore().load(path)
    assert isinstance(loaded, Ok)
    report = DiagnosticService().diagnose(loaded.value)
    assert isinstance(report, Ok)
    assert report.value.counts["entities"] == 60
    assert report.value.counts["relations"] == 120

    snapshot = copy.deepcopy(loaded.value.to_dict())
    plan = RepairPlanService().build_plan(loaded.value)
    assert isinstance(plan, Ok)
    assert plan.value.mutates_project is False
    assert plan.value.requires_explicit_apply is True
    assert plan.value.requires_backup_before_apply is True
    assert loaded.value.to_dict() == snapshot


def test_b29_cli_diagnostic_export_and_repair_plan_are_parseable(tmp_path: Path) -> None:
    project_path = tmp_path / "project.json"
    diagnostic_path = tmp_path / "diagnostic.json"
    created = _cli(f"project create QA --path {project_path}")
    assert created.returncode == 0, created.stderr + created.stdout

    exported = _cli(
        f"maintenance export-diagnostic --output {diagnostic_path} --json",
        project=project_path,
    )
    assert exported.returncode == 0, exported.stderr
    export_payload = json.loads(exported.stdout)
    assert export_payload["output"] == str(diagnostic_path)
    assert json.loads(diagnostic_path.read_text(encoding="utf-8"))["project_name"] == "QA"

    plan = _cli("maintenance repair-plan --json", project=project_path)
    assert plan.returncode == 0, plan.stderr
    plan_payload = json.loads(plan.stdout)
    assert plan_payload["mutates_project"] is False
    assert plan_payload["requires_explicit_apply"] is True
    assert plan_payload["requires_backup_before_apply"] is True
