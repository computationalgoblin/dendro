"""
CLI entity commands — ``entity create``, ``edit``, ``archive``, ``list``,
``show``, and ``search``.

Registered by :func:`register_entity_commands` and dispatched via
:func:`handle_entity_command`.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from packages.domain.entity import CanonState, EntityType, VisibilityState
from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)


def register_entity_commands(subparsers: Any) -> None:
    """Register the ``entity`` subcommand and its sub-subcommands under *subparsers*."""
    entity_parser = subparsers.add_parser("entity", help="Entity commands")
    entity_subs = entity_parser.add_subparsers(dest="entity_command", required=True)

    # entity create <name> --type <type> [--brief ...] [--extended ...] [--domain ...]
    p_create = entity_subs.add_parser("create", help="Create a new entity")
    p_create.add_argument("name", help="Entity name")
    p_create.add_argument(
        "--type", required=True, metavar="TYPE",
        help="Entity type (personaje, localizacion, ...)",
    )
    p_create.add_argument("--brief", default=None, help="Brief description")
    p_create.add_argument("--extended", default=None, help="Extended description")
    p_create.add_argument("--domain", default=None, help="Domain / world layer")

    # entity edit <id> [--name ...] [--brief ...] [--extended ...] [--domain ...]
    p_edit = entity_subs.add_parser("edit", help="Edit an entity")
    p_edit.add_argument("id", help="Entity ID")
    p_edit.add_argument("--name", default=None, help="New name")
    p_edit.add_argument("--brief", default=None, help="New brief description")
    p_edit.add_argument("--extended", default=None, help="New extended description")
    p_edit.add_argument("--domain", default=None, help="New domain")

    # entity archive <id>
    p_archive = entity_subs.add_parser("archive", help="Archive an entity (soft delete)")
    p_archive.add_argument("id", help="Entity ID")

    # entity list [--type <t>] [--canon <c>] [--visibility <v>] [--tag <t>] [--limit <n>]
    p_list = entity_subs.add_parser("list", help="List/filter entities")
    p_list.add_argument("--type", default=None, metavar="TYPE", help="Filter by entity type")
    p_list.add_argument("--canon", default=None, metavar="STATE", help="Filter by canon state")
    p_list.add_argument(
        "--visibility", default=None, metavar="STATE",
        help="Filter by visibility state",
    )
    p_list.add_argument("--tag", default=None, help="Filter by tag")
    p_list.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")

    # entity show <id>
    p_show = entity_subs.add_parser("show", help="Show entity card")
    p_show.add_argument("id", help="Entity ID")

    # entity search <query> [--no-private]
    p_search = entity_subs.add_parser("search", help="Text search across entities")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument(
        "--no-private", action="store_true",
        help="Exclude private notes from search",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_enum(value: str, enum_cls: type, label: str) -> Any:
    """Parse *value* (case-insensitive) into *enum_cls*, or print error + exit."""
    lowered = value.lower()
    try:
        return enum_cls(lowered)
    except ValueError:
        valid = ", ".join(sorted(e.value for e in enum_cls))
        print(f"error: Invalid {label} '{value}'. Valid: {valid}", file=sys.stderr)
        sys.exit(1)


def _entity_list_row(e: Any, index: int | None = None) -> str:
    """Format one entity as a compact table row."""
    prefix = f"{index:>3}. " if index is not None else ""
    canon_mark = ""
    if e.canon_state == CanonState.ARCHIVADO:
        canon_mark = " [ARCHIVADO]"
    return (
        f"{prefix}{e.id}  {e.name:<30} "
        f"{e.entity_type.value:<18} {e.canon_state.value}{canon_mark}"
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def handle_entity_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch to the correct entity subcommand handler."""
    cmd = args.entity_command
    if cmd == "create":
        _cmd_create(args, session)
    elif cmd == "edit":
        _cmd_edit(args, session)
    elif cmd == "archive":
        _cmd_archive(args, session)
    elif cmd == "list":
        _cmd_list(args, session)
    elif cmd == "show":
        _cmd_show(args, session)
    elif cmd == "search":
        _cmd_search(args, session)
    else:
        print(f"error: Unknown entity command '{cmd}'", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _cmd_create(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, *_ = _bootstrap_services(project_path)

    entity_type = _parse_enum(args.type, EntityType, "entity type")
    data: dict[str, Any] = {"name": args.name, "entity_type": entity_type}
    if args.brief is not None:
        data["brief_description"] = args.brief
    if args.extended is not None:
        data["extended_description"] = args.extended
    if args.domain is not None:
        data["domain"] = args.domain

    result = es.create_entity(data)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    entity = result.value
    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Entity created but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Entity '{entity.name}' ({entity.id}) created [{entity.entity_type.value}]")


def _cmd_edit(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, *_ = _bootstrap_services(project_path)

    data: dict[str, Any] = {}
    if args.name is not None:
        data["name"] = args.name
    if args.brief is not None:
        data["brief_description"] = args.brief
    if args.extended is not None:
        data["extended_description"] = args.extended
    if args.domain is not None:
        data["domain"] = args.domain

    if not data:
        print(
            "error: No fields to edit. "
            "Provide at least one of --name, --brief, --extended, --domain.",
            file=sys.stderr,
        )
        sys.exit(1)

    result = es.update_entity(args.id, data)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Entity updated but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    updated = result.value
    print(f"Entity '{updated.name}' ({updated.id}) updated")


def _cmd_archive(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, *_ = _bootstrap_services(project_path)

    result = es.archive_entity(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Entity archived but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Entity '{args.id}' archived")


def _cmd_list(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    # Parse enum filters
    entity_type = _parse_enum(args.type, EntityType, "entity type") if args.type else None
    canon_state = _parse_enum(args.canon, CanonState, "canon state") if args.canon else None
    visibility = (
        _parse_enum(args.visibility, VisibilityState, "visibility state")
        if args.visibility else None
    )

    result = qs.query(
        entity_type=entity_type,
        canon_state=canon_state,
        visibility_state=visibility,
        tag=args.tag,
        limit=args.limit,
    )
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    entities = result.value
    if not entities:
        print("No entities found.")
        return

    active = sum(1 for e in entities if e.canon_state != CanonState.ARCHIVADO)
    archived = len(entities) - active
    print(f"Entities: {len(entities)} total ({active} active, {archived} archived)")
    for i, e in enumerate(entities, 1):
        print(_entity_list_row(e, index=i))


def _cmd_show(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = qs.get_entity_card(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    card = result.value
    e = card.entity

    # Header
    print("═" * 60)
    print(f"  {e.name}")
    print("═" * 60)
    print(f"ID:           {e.id}")
    print(f"Type:         {e.entity_type.value}")
    print(f"Canon:        {e.canon_state.value}")
    print(f"Visibility:   {e.visibility_state.value}")
    if e.domain:
        print(f"Domain:       {e.domain}")
    if e.brief_description:
        print(f"Brief:        {e.brief_description}")
    if e.extended_description:
        truncated = e.extended_description[:120]
        suffix = "..." if len(e.extended_description) > 120 else ""
        print(f"Extended:     {truncated}{suffix}")
    if e.tags:
        print(f"Tags:         {', '.join(e.tags)}")
    if e.layers:
        print(f"Layers:       {', '.join(e.layers)}")
    print()

    # Relations
    incoming = card.incoming_relations
    outgoing = card.outgoing_relations
    rel_count = len(incoming) + len(outgoing)
    print(f"Relations ({len(incoming)} incoming, {len(outgoing)} outgoing):")
    for r in incoming:
        print(f"  ← {r.relation_type.value} from {r.source_id}")
    for r in outgoing:
        print(f"  → {r.relation_type.value} to {r.target_id}")
    if rel_count == 0:
        print("  (none)")
    print()

    # Sources
    print(f"Sources ({len(card.sources)}):")
    if card.sources:
        for s in card.sources:
            st = s.source_type.value if hasattr(s, "source_type") else "?"
            print(f"  {s.id}  {s.name} ({st})")
    else:
        print("  (none)")
    print()

    # Issues
    print(f"Issues open ({len(card.open_issues)}):")
    if card.open_issues:
        for iss in card.open_issues:
            print(f"  {iss.id}  [{iss.severity}] {iss.title or '(no title)'}")
    else:
        print("  (none)")
    print()

    # History
    print(f"History (last {len(card.history)}):")
    if card.history:
        for h in card.history:
            ts = h.timestamp.isoformat() if hasattr(h, 'timestamp') else "?"
            print(f"  {ts}  {h.event_type.value if hasattr(h, 'event_type') else '?'}")
    else:
        print("  Historial: no disponible")
    print("═" * 60)


def _cmd_search(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    include_private = not args.no_private
    result = ts.search_entities(args.query, include_private=include_private)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    entities = result.value
    if not entities:
        print(f"No entities found matching '{args.query}'.")
        return

    print(f"Found {len(entities)} entities matching '{args.query}':")
    for i, e in enumerate(entities, 1):
        print(_entity_list_row(e, index=i))
