"""
CLI source commands — ``source create``, ``list``, ``show``,
``link-entity``, and ``link-relation`` (B07-T03).

Registered by :func:`register_source_commands` and dispatched via
:func:`handle_source_command`.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from packages.domain.result import Error
from packages.domain.source_history import SourceType
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)


def register_source_commands(subparsers: Any) -> None:
    """Register the ``source`` subcommand under *subparsers*."""
    src_parser = subparsers.add_parser("source", help="Source commands")
    src_subs = src_parser.add_subparsers(dest="source_command", required=True)

    # source create <name> --type <type> [--reference ...] [--fragment ...]
    p_create = src_subs.add_parser("create", help="Create a new source")
    p_create.add_argument("name", help="Source name")
    p_create.add_argument(
        "--type", required=True, metavar="TYPE",
        help="Source type (entrada_manual, documento_importado, ...)",
    )
    p_create.add_argument("--reference", default=None, help="Reference / citation")
    p_create.add_argument("--fragment", default=None, help="Text fragment")

    # source list [--entity <id>]
    p_list = src_subs.add_parser("list", help="List sources")
    p_list.add_argument("--entity", default=None, help="Filter by linked entity ID")

    # source show <id>
    p_show = src_subs.add_parser("show", help="Show source details")
    p_show.add_argument("id", help="Source ID")

    # source link-entity <source_id> <entity_id>
    p_link_e = src_subs.add_parser("link-entity", help="Link a source to an entity")
    p_link_e.add_argument("source_id", help="Source ID")
    p_link_e.add_argument("entity_id", help="Entity ID")

    # source link-relation <source_id> <relation_id>
    p_link_r = src_subs.add_parser("link-relation", help="Link a source to a relation")
    p_link_r.add_argument("source_id", help="Source ID")
    p_link_r.add_argument("relation_id", help="Relation ID")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_source_type(value: str) -> SourceType:
    """Parse *value* into SourceType, case-insensitive. Exit on invalid."""
    lowered = value.lower()
    try:
        return SourceType(lowered)
    except ValueError:
        valid = ", ".join(sorted(e.value for e in SourceType))
        print(
            f"error: Invalid source type '{value}'. Valid: {valid}",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def handle_source_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch to the correct source subcommand handler."""
    cmd = args.source_command
    if cmd == "create":
        _cmd_create(args, session)
    elif cmd == "list":
        _cmd_list(args, session)
    elif cmd == "show":
        _cmd_show(args, session)
    elif cmd == "link-entity":
        _cmd_link_entity(args, session)
    elif cmd == "link-relation":
        _cmd_link_relation(args, session)
    else:
        print(f"error: Unknown source command '{cmd}'", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _cmd_create(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, *_ = _bootstrap_services(project_path)

    stype = _parse_source_type(args.type)
    data: dict[str, Any] = {"name": args.name, "source_type": stype}
    if args.reference is not None:
        data["reference"] = args.reference
    if args.fragment is not None:
        data["fragment"] = args.fragment

    result = ss.create_source(data)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    source = result.value
    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(
            f"error: Source created but save failed: {save_result.error}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Source '{source.name}' ({source.id}) created [{stype.value}]")


def _cmd_list(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, *_ = _bootstrap_services(project_path)

    if args.entity is not None:
        result = ss.get_sources_for_entity(args.entity)
    else:
        result = ss.list_all()

    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    sources = result.value
    if not sources:
        print("No sources found.")
        return

    entity_label = f' for entity "{args.entity[:8]}..."' if args.entity else ""
    print(f"Sources{entity_label} ({len(sources)}):")
    for s in sources:
        st = s.source_type.value if hasattr(s, "source_type") else "?"
        print(f"  {s.id}  {s.name:<30} ({st})")


def _cmd_show(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, *_ = _bootstrap_services(project_path)

    result = ss.get_by_id(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    s = result.value
    print("═" * 50)
    print(f"  Source: {s.name}")
    print("═" * 50)
    print(f"ID:           {s.id}")
    st = s.source_type.value if hasattr(s, "source_type") else "?"
    print(f"Type:         {st}")
    if s.reference:
        print(f"Reference:    {s.reference}")
    if s.fragment:
        print(f"Fragment:     {s.fragment[:200]}")
    if s.derived_entity_ids:
        print(f"Entities:     {', '.join(s.derived_entity_ids)}")
    if s.derived_relation_ids:
        print(f"Relations:    {', '.join(s.derived_relation_ids)}")
    print("═" * 50)


def _cmd_link_entity(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, *_ = _bootstrap_services(project_path)

    result = ss.link_to_entity(args.source_id, args.entity_id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(
            f"error: Source linked but save failed: {save_result.error}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Source '{args.source_id}' linked to entity '{args.entity_id}'")


def _cmd_link_relation(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, *_ = _bootstrap_services(project_path)

    result = ss.link_to_relation(args.source_id, args.relation_id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(
            f"error: Source linked but save failed: {save_result.error}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"Source '{args.source_id}' linked to relation '{args.relation_id}'"
    )
