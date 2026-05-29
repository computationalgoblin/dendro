"""
CLI relation commands — ``relation create``, ``edit``, ``archive``,
``list``, and ``show`` (B07-T03).

Registered by :func:`register_relation_commands` and dispatched via
:func:`handle_relation_command`.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from packages.domain.entity import CanonState
from packages.domain.relation import RelationType
from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)


def register_relation_commands(subparsers: Any) -> None:
    """Register the ``relation`` subcommand under *subparsers*."""
    rel_parser = subparsers.add_parser("relation", help="Relation commands")
    rel_subs = rel_parser.add_subparsers(dest="relation_command", required=True)

    # relation create <source_id> <target_id> --type <t> [--desc ...] [--direction ...]
    p_create = rel_subs.add_parser("create", help="Create a new relation")
    p_create.add_argument("source_id", help="Source entity ID")
    p_create.add_argument("target_id", help="Target entity ID")
    p_create.add_argument(
        "--type", required=True, metavar="TYPE",
        help="Relation type (es_aliado_de, pertenece_a, ...)",
    )
    p_create.add_argument("--desc", default=None, help="Description")
    p_create.add_argument(
        "--direction", default="unidireccional",
        choices=["unidireccional", "bidireccional"],
        help="Direction (default: unidireccional)",
    )

    # relation edit <id> [--desc ...]
    p_edit = rel_subs.add_parser("edit", help="Edit a relation")
    p_edit.add_argument("id", help="Relation ID")
    p_edit.add_argument("--desc", default=None, help="New description")

    # relation archive <id>
    p_archive = rel_subs.add_parser("archive", help="Archive a relation (soft delete)")
    p_archive.add_argument("id", help="Relation ID")

    # relation list [--entity <id>] [--type <t>]
    p_list = rel_subs.add_parser("list", help="List relations")
    p_list.add_argument("--entity", default=None, help="Filter by entity ID")
    p_list.add_argument("--type", default=None, metavar="TYPE", help="Filter by relation type")

    # relation show <id>
    p_show = rel_subs.add_parser("show", help="Show relation details")
    p_show.add_argument("id", help="Relation ID")

    # relation set-field <relation-id> <field-id> <value>
    p_setf = rel_subs.add_parser("set-field", help="Set a custom field value")
    p_setf.add_argument("relation_id", help="Relation ID")
    p_setf.add_argument("field_id", help="Field definition ID")
    p_setf.add_argument("value", help="Value")

    # relation remove-field <relation-id> <field-id>
    p_rmf = rel_subs.add_parser("remove-field", help="Remove a custom field value")
    p_rmf.add_argument("relation_id", help="Relation ID")
    p_rmf.add_argument("field_id", help="Field definition ID")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_relation_type(value: str) -> RelationType:
    """Parse *value* into RelationType, case-insensitive. Exit on invalid."""
    lowered = value.lower()
    try:
        return RelationType(lowered)
    except ValueError:
        valid = ", ".join(sorted(e.value for e in RelationType))
        print(
            f"error: Invalid relation type '{value}'. Valid: {valid}",
            file=sys.stderr,
        )
        sys.exit(1)


def _relation_row(r: Any, index: int | None = None) -> str:
    """Format one relation as a compact row."""
    prefix = f"{index:>3}. " if index is not None else ""
    archived = " [ARCHIVED]" if r.canon_state == CanonState.ARCHIVADO else ""
    return (
        f"{prefix}{r.id}  {r.relation_type.value:<22} "
        f"{r.source_id[:8]} → {r.target_id[:8]}{archived}"
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def handle_relation_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch to the correct relation subcommand handler."""
    cmd = args.relation_command
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
    elif cmd == "set-field":
        _cmd_set_field(args, session)
    elif cmd == "remove-field":
        _cmd_remove_field(args, session)
    else:
        print(f"error: Unknown relation command '{cmd}'", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _cmd_create(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    rtype = _parse_relation_type(args.type)
    data: dict[str, Any] = {}
    if args.desc:
        data["description"] = args.desc
    data["direction"] = args.direction

    result = rs.create_relation(
        source_id=args.source_id,
        target_id=args.target_id,
        relation_type=rtype,
        data=data,
        history_service=hs,
    )
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    relation = result.value
    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(
            f"error: Relation created but save failed: {save_result.error}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"Relation '{relation.id}' ({relation.relation_type.value}) "
        f"created: {relation.source_id[:8]} → {relation.target_id[:8]}"
    )


def _cmd_edit(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    data: dict[str, Any] = {}
    if args.desc is not None:
        data["description"] = args.desc

    if not data:
        print("error: No fields to edit. Provide --desc.", file=sys.stderr)
        sys.exit(1)

    result = rs.update_relation(args.id, data, history_service=hs)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(
            f"error: Relation updated but save failed: {save_result.error}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Relation '{args.id}' updated")


def _cmd_archive(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = rs.archive_relation(args.id, history_service=hs)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(
            f"error: Relation archived but save failed: {save_result.error}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Relation '{args.id}' archived")


def _cmd_list(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, *_ = _bootstrap_services(project_path)

    if args.entity is not None:
        incoming = rs.get_incoming(args.entity)
        outgoing = rs.get_outgoing(args.entity)
        incoming_list = incoming.value if not isinstance(incoming, Error) else []
        outgoing_list = outgoing.value if not isinstance(outgoing, Error) else []
        relations = incoming_list + outgoing_list
    else:
        result = rs.list_all()
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        relations = result.value

    # Filter by type if requested
    if args.type is not None:
        rtype = _parse_relation_type(args.type)
        relations = [r for r in relations if r.relation_type == rtype]

    if not relations:
        print("No relations found.")
        return

    active = sum(1 for r in relations if r.canon_state != CanonState.ARCHIVADO)
    archived = len(relations) - active
    print(f"Relations: {len(relations)} total ({active} active, {archived} archived)")
    for i, r in enumerate(relations, 1):
        print(_relation_row(r, index=i))


def _cmd_show(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, *_ = _bootstrap_services(project_path)

    result = rs.get_by_id(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    r = result.value
    print("═" * 55)
    print(f"  Relation: {r.id}")
    print("═" * 55)
    print(f"Type:         {r.relation_type.value}")
    print(f"Source:       {r.source_id}")
    print(f"Target:       {r.target_id}")
    print(f"Canon:        {r.canon_state.value}")
    print(f"Visibility:   {r.visibility_state.value}")
    if hasattr(r, "direction"):
        print(f"Direction:    {r.direction}")
    if r.description:
        print(f"Description:  {r.description}")
    if hasattr(r, "custom_relation_type_id") and r.custom_relation_type_id:
        print(f"Custom type:  {r.custom_relation_type_id}")
    if hasattr(r, "custom_fields") and r.custom_fields:
        print(f"Custom fields:")
        for cf in r.custom_fields:
            print(f"  {cf.field_id}: {cf.value}")
    print("═" * 55)


def _relation_convert_value(raw: str) -> Any:
    """Convert a CLI string value to the best typed equivalent."""
    import json as _json
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if raw.startswith("{") or raw.startswith("["):
        try:
            return _json.loads(raw)
        except _json.JSONDecodeError:
            pass
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _cmd_set_field(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, *_ = _bootstrap_services(project_path)
    from packages.application.custom_type_service import CustomTypeService
    cts = CustomTypeService(project_service=ps)

    value = _relation_convert_value(args.value)

    result = rs.set_custom_field(
        args.relation_id, args.field_id, value, custom_type_service=cts,
    )
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Field set but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)
    print(f"Custom field '{args.field_id}' set on relation '{args.relation_id}'")


def _cmd_remove_field(args: argparse.Namespace, session: SessionContext) -> None:
    from packages.application.custom_type_service import CustomTypeService

    project_path = require_project_path(args, session)
    ps, es, rs, *_ = _bootstrap_services(project_path)

    result = rs.remove_custom_field(args.relation_id, args.field_id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Field removed but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)
    print(f"Custom field '{args.field_id}' removed from relation '{args.relation_id}'")
