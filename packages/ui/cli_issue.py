"""
CLI issue commands — list, show, entity, review, accept, resolve,
discard, intentional, note, validate (B12-T04).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from packages.application.issue_service import IssueService
from packages.domain.result import Error
from packages.ui.cli import (
    _bootstrap_services,
    require_project_path,
)


def register_issue_commands(subparsers: Any) -> None:
    ip = subparsers.add_parser("issue", help="Issue commands")
    iss = ip.add_subparsers(dest="issue_command", required=True)

    p_list = iss.add_parser("list", help="List issues")
    p_list.add_argument("--state", default=None)
    p_list.add_argument("--type", default=None, dest="itype")
    p_list.add_argument("--severity", default=None)

    p_show = iss.add_parser("show", help="Show issue detail")
    p_show.add_argument("id", help="Issue ID")

    p_ent = iss.add_parser("entity", help="Issues for an entity")
    p_ent.add_argument("id", help="Entity ID")

    for cmd in ("review", "accept"):
        p = iss.add_parser(cmd, help=f"Mark as {cmd.upper()}")
        p.add_argument("id", help="Issue ID")

    for cmd in ("resolve", "discard", "intentional"):
        p = iss.add_parser(cmd, help=f"Mark as {cmd.upper()}")
        p.add_argument("id", help="Issue ID")
        p.add_argument("--note", default="")

    p_note = iss.add_parser("note", help="Add resolution note")
    p_note.add_argument("id", help="Issue ID")
    p_note.add_argument("text", help="Note text")

    p_val = iss.add_parser("validate", help="Run validators")
    p_val.add_argument("--entity-id", default=None)
    p_val.add_argument("--check", default=None)


def _get_svc(project_path):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    return ps, IssueService(project_service=ps)


def handle_issue_command(args, session):
    project_path = require_project_path(args, session)
    cmd = args.issue_command

    if cmd == "list":
        ps, svc = _get_svc(project_path)
        result = svc.list_issues(
            state=getattr(args, "state", None),
            itype=getattr(args, "itype", None),
            severity=getattr(args, "severity", None),
        )
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        issues = result.value
        if not issues:
            print("No issues found")
            return
        by_state: dict[str, int] = {}
        for i in issues:
            by_state[i.state.value] = by_state.get(i.state.value, 0) + 1
        state_summary = ", ".join(
            f"{c} {s}" for s, c in sorted(by_state.items())
        )
        print(f"Issues: {len(issues)} ({state_summary})")
        for i in issues:
            print(
                f"  [{i.severity.value.upper():6s}] {i.type.value:<25s} "
                f"{i.state.value:<12s} {i.description[:40]:40s} {i.id}"
            )

    elif cmd == "show":
        ps, svc = _get_svc(project_path)
        result = svc.get_issue(args.id)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        i = result.value
        print(f"Issue: {i.id}")
        print(f"  Type: {i.type.value}")
        print(f"  Severity: {i.severity.value.upper()}")
        print(f"  State: {i.state.value}")
        print(f"  Description: {i.description}")
        if i.affected_entity_ids:
            print(f"  Affected entities: {', '.join(i.affected_entity_ids)}")
        if i.affected_relation_ids:
            print(f"  Affected relations: {', '.join(i.affected_relation_ids)}")
        if i.evidence:
            print(f"  Evidence: {i.evidence}")
        print(f"  Detected: {i.detected_at}")
        print(f"  Reviewed: {i.reviewed_at or '—'}")
        print(f"  Resolution: {i.resolution or '—'}")
        print(f"  Intentional: {'Yes' if i.is_intentional else 'No'}")
        if i.possible_solutions:
            print("  Possible solutions:")
            for s in i.possible_solutions:
                print(f"    - {s}")

    elif cmd == "entity":
        ps, svc = _get_svc(project_path)
        result = svc.list_issues_by_entity(args.id)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        issues = result.value
        if not issues:
            print(f"No issues for entity {args.id[:8]}")
            return
        print(f"Issues for entity {args.id[:8]}: {len(issues)}")
        for i in issues:
            print(f"  [{i.severity.value.upper()}] {i.type.value}: {i.description}")

    elif cmd in ("review", "accept", "resolve", "discard", "intentional"):
        ps, svc = _get_svc(project_path)
        note = getattr(args, "note", "")
        if cmd == "review":
            result = svc.review_issue(args.id)
        elif cmd == "accept":
            result = svc.accept_issue(args.id)
        elif cmd == "resolve":
            result = svc.resolve_issue(args.id, note)
        elif cmd == "discard":
            result = svc.discard_issue(args.id, note)
        else:
            result = svc.mark_intentional(args.id, note)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        ps_svc = ps
        save_result = ps_svc.save(Path(project_path))
        if isinstance(save_result, Error):
            print(f"error: {save_result.error}", file=sys.stderr)
            sys.exit(1)
        print(f"Issue '{args.id[:8]}' -> {result.value.state.value}")

    elif cmd == "note":
        ps, svc = _get_svc(project_path)
        result = svc.add_resolution_note(args.id, args.text)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        ps_svc = ps
        ps_svc.save(Path(project_path))
        print(f"Note added to issue '{args.id[:8]}'")

    elif cmd == "validate":
        ps, svc = _get_svc(project_path)
        result = svc.run_validation(entity_id=args.entity_id)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        summary = result.value
        ps_svc = ps
        ps_svc.save(Path(project_path))
        print(
            f"Validation complete: {summary['new']} new, "
            f"{summary['skipped']} skipped "
            f"({summary['total']} total)"
        )
