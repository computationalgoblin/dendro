"""
CLI history commands — ``history entity`` and ``history recent`` (B07-T03).

Registered by :func:`register_history_commands` and dispatched via
:func:`handle_history_command`.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)


def register_history_commands(subparsers: Any) -> None:
    """Register the ``history`` subcommand under *subparsers*."""
    hist_parser = subparsers.add_parser("history", help="History commands")
    hist_subs = hist_parser.add_subparsers(dest="history_command", required=True)

    # history entity <id> [--limit <n>]
    p_entity = hist_subs.add_parser("entity", help="Show entity history")
    p_entity.add_argument("id", help="Entity ID")
    p_entity.add_argument("--limit", type=int, default=20, help="Max events (default: 20)")

    # history recent [--limit <n>]
    p_recent = hist_subs.add_parser("recent", help="Show recent history events")
    p_recent.add_argument("--limit", type=int, default=20, help="Max events (default: 20)")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def handle_history_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch to the correct history subcommand handler."""
    cmd = args.history_command
    if cmd == "entity":
        _cmd_entity(args, session)
    elif cmd == "recent":
        _cmd_recent(args, session)
    else:
        print(f"error: Unknown history command '{cmd}'", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _cmd_entity(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    # Get entity name for display
    entity_result = es.get_by_id(args.id)
    entity_name = args.id
    if not isinstance(entity_result, Error):
        entity_name = entity_result.value.name

    result = hs.get_for_entity(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    events = result.value
    if args.limit:
        events = events[-args.limit:]

    print(f'History for "{entity_name}" ({len(events)} events):')
    if not events:
        return

    for h in events:
        ts = h.timestamp.isoformat(timespec="seconds") if hasattr(h, "timestamp") else "?"
        desc = ""
        if h.new_value and isinstance(h.new_value, str):
            desc = f"  → {h.new_value[:80]}"
        elif h.reason:
            desc = f"  ({h.reason})"
        print(
            f"  {ts}  {h.event_type.value if hasattr(h, 'event_type') else '?'}"
            f"{desc}"
        )


def _cmd_recent(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = hs.get_recent(limit=args.limit)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    events = result.value
    print(f"Recent events ({len(events)}):")
    if not events:
        return

    for h in events:
        ts = h.timestamp.isoformat(timespec="seconds") if hasattr(h, "timestamp") else "?"
        desc = ""
        if h.new_value and isinstance(h.new_value, str):
            desc = f"  → {h.new_value[:80]}"
        elif h.reason:
            desc = f"  ({h.reason})"
        entity_hint = ""
        if hasattr(h, "affected_entity_id") and h.affected_entity_id:
            entity_hint = f" [{h.affected_entity_id[:8]}]"
        elif hasattr(h, "affected_relation_id") and h.affected_relation_id:
            entity_hint = f" [rel:{h.affected_relation_id[:8]}]"
        print(
            f"  {ts}  {h.event_type.value if hasattr(h, 'event_type') else '?'}"
            f"{entity_hint}{desc}"
        )
