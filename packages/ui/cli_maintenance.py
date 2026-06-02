"""CLI maintenance commands for diagnostics, backups and non-destructive plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from packages.application.diagnostic_service import DiagnosticService
from packages.application.project_maintenance_service import ProjectMaintenanceService
from packages.domain.result import Error
from packages.persistence.store import ProjectStore
from packages.ui.cli import SessionContext, _bootstrap_services, require_project_path


def register_maintenance_commands(subparsers: Any) -> None:
    """Register maintenance subcommands."""
    parser = subparsers.add_parser("maintenance", help="Project diagnostics, backup and restore tools")
    subs = parser.add_subparsers(dest="maintenance_command", required=True)

    p_doctor = subs.add_parser("doctor", help="Run read-only project diagnostics")
    p_doctor.add_argument("--json", action="store_true", help="Emit parseable JSON")

    p_size = subs.add_parser("size", help="Show project file and serialized size")
    p_size.add_argument("--json", action="store_true", help="Emit parseable JSON")

    p_backup = subs.add_parser("backup", help="Create a validated numbered backup")
    p_backup.add_argument("--json", action="store_true", help="Emit parseable JSON")

    p_backups = subs.add_parser("backups", help="List backups newest-first")
    p_backups.add_argument("--json", action="store_true", help="Emit parseable JSON")

    p_restore = subs.add_parser("restore", help="Restore from a validated backup")
    p_restore.add_argument("--backup", required=True, help="Backup file to restore from")
    p_restore.add_argument("--json", action="store_true", help="Emit parseable JSON")

    p_export = subs.add_parser("export-diagnostic", help="Write diagnostic report to JSON file")
    p_export.add_argument("--output", required=True, help="Output JSON path")
    p_export.add_argument("--json", action="store_true", help="Emit parseable JSON confirmation")

    p_plan = subs.add_parser("repair-plan", help="Generate a non-destructive repair/cleanup plan")
    p_plan.add_argument("--json", action="store_true", help="Emit parseable JSON")


def handle_maintenance_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch maintenance command."""
    cmd = args.maintenance_command
    project_path = require_project_path(args, session)

    if cmd == "backup":
        _cmd_backup(args, project_path)
        return
    if cmd == "backups":
        _cmd_backups(args, project_path)
        return
    if cmd == "restore":
        _cmd_restore(args, project_path)
        return

    ps, *_ = _bootstrap_services(project_path)
    project = ps.active_project
    if project is None:
        print("error: No active project", file=sys.stderr)
        sys.exit(1)

    if cmd == "doctor":
        _cmd_doctor(args, project)
        return
    if cmd == "size":
        _cmd_size(args, project_path, project)
        return
    if cmd == "export-diagnostic":
        _cmd_export_diagnostic(args, project)
        return
    if cmd == "repair-plan":
        _cmd_repair_plan(args, project)
        return

    print(f"error: Unknown maintenance command '{cmd}'", file=sys.stderr)
    sys.exit(1)


def _diagnose(project: Any):
    result = DiagnosticService().diagnose(project)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    return result.value


def _maintenance_service() -> ProjectMaintenanceService:
    return ProjectMaintenanceService(store=ProjectStore())


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    sys.exit(0)


def _cmd_doctor(args: argparse.Namespace, project: Any) -> None:
    report = _diagnose(project)
    if args.json:
        _print_json(report.to_dict())
    print(report.to_markdown())
    sys.exit(0)


def _cmd_size(args: argparse.Namespace, project_path: Path, project: Any) -> None:
    report = _diagnose(project)
    try:
        file_bytes = project_path.stat().st_size
    except OSError:
        file_bytes = 0
    payload = {
        "project_path": str(project_path),
        "file_bytes": file_bytes,
        "diagnostic": report.size,
        "counts": report.counts,
    }
    if args.json:
        _print_json(payload)
    print(f"Project file: {file_bytes} bytes")
    print(f"Serialized JSON: {report.size['serialized_json_bytes']} bytes")
    sys.exit(0)


def _cmd_backup(args: argparse.Namespace, project_path: Path) -> None:
    result = _maintenance_service().create_backup(project_path)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    payload = {"project_path": str(project_path), "backup_path": str(result.value)}
    if args.json:
        _print_json(payload)
    print(f"Backup created: {result.value}")
    sys.exit(0)


def _cmd_backups(args: argparse.Namespace, project_path: Path) -> None:
    rows = _maintenance_service().backup_metadata(project_path)
    payload = {"project_path": str(project_path), "backups": rows}
    if args.json:
        _print_json(payload)
    if not rows:
        print("No backups found.")
    for row in rows:
        print(f"{row['path']} ({row['bytes']} bytes)")
    sys.exit(0)


def _cmd_restore(args: argparse.Namespace, project_path: Path) -> None:
    backup_path = Path(args.backup)
    result = _maintenance_service().restore_backup(project_path, backup_path)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    payload = {
        "project_path": str(project_path),
        "restored_from": str(backup_path),
        "pre_restore_backup": str(result.value),
    }
    if args.json:
        _print_json(payload)
    print(f"Restored {project_path} from {backup_path}")
    print(f"Current file preserved first as {result.value}")
    sys.exit(0)


def _cmd_export_diagnostic(args: argparse.Namespace, project: Any) -> None:
    output = Path(args.output)
    report = _diagnose(project)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.to_json(), encoding="utf-8")
    payload = {"output": str(output), "project_id": report.project_id, "error_count": report.error_count}
    if args.json:
        _print_json(payload)
    print(f"Diagnostic exported: {output}")
    sys.exit(0)


def _cmd_repair_plan(args: argparse.Namespace, project: Any) -> None:
    report = _diagnose(project)
    actions = []
    for item in [*report.items, *report.recommendations]:
        actions.append({
            "code": item.code,
            "severity": item.severity.value,
            "collection": item.collection,
            "object_id": item.object_id,
            "reference_id": item.reference_id,
            "message": item.message,
            "action": _suggest_action(item.code),
            "mutates_project": False,
        })
    payload = {
        "project_id": report.project_id,
        "project_name": report.project_name,
        "mutates_project": False,
        "requires_explicit_apply": True,
        "requires_backup_before_apply": True,
        "actions": actions,
    }
    if args.json:
        _print_json(payload)
    print("Repair plan (non-destructive):")
    if not actions:
        print("- No actions recommended.")
    for action in actions:
        print(f"- {action['code']}: {action['action']}")
    sys.exit(0)


def _suggest_action(code: str) -> str:
    suggestions = {
        "broken_relation_source": "Review relation and either reconnect source entity or archive relation in a future explicit repair step.",
        "broken_relation_target": "Review relation and either reconnect target entity or archive relation in a future explicit repair step.",
        "broken_issue_entity": "Review issue references and remove or replace the missing entity reference in a future explicit repair step.",
        "broken_issue_relation": "Review issue references and remove or replace the missing relation reference in a future explicit repair step.",
        "broken_issue_source": "Review issue references and remove or replace the missing source reference in a future explicit repair step.",
        "obsolete_entity": "Review obsolete entity and decide whether to archive, keep or supersede explicitly.",
    }
    if code.startswith("cleanup_") or code.startswith("review_"):
        return "Review accumulated collection and compact only after explicit approval and backup."
    return suggestions.get(code, "Review manually; no automatic mutation is performed.")


__all__ = ["register_maintenance_commands", "handle_maintenance_command"]
