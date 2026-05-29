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

    # relation show <id> [--extended] [--json]
    p_show = rel_subs.add_parser("show", help="Show relation details")
    p_show.add_argument("id", help="Relation ID")
    p_show.add_argument(
        "--extended", action="store_true",
        help="Show full relation card",
    )
    p_show.add_argument(
        "--json", action="store_true",
        help="JSON output",
    )

    # relation set-field <relation-id> <field-id> <value>
    p_setf = rel_subs.add_parser("set-field", help="Set a custom field value")
    p_setf.add_argument("relation_id", help="Relation ID")
    p_setf.add_argument("field_id", help="Field definition ID")
    p_setf.add_argument("value", help="Value")

    # relation remove-field <relation-id> <field-id>
    p_rmf = rel_subs.add_parser("remove-field", help="Remove a custom field value")
    p_rmf.add_argument("relation_id", help="Relation ID")
    p_rmf.add_argument("field_id", help="Field definition ID")

    # relation assign-layer <id> <layer-id>
    p_al = rel_subs.add_parser("assign-layer", help="Assign a world layer")
    p_al.add_argument("id", help="Relation ID")
    p_al.add_argument("layer_id", help="World layer ID (e.g. layer_geografia)")

    # relation remove-layer <id> <layer-id>
    p_rl = rel_subs.add_parser("remove-layer", help="Remove a world layer")
    p_rl.add_argument("id", help="Relation ID")
    p_rl.add_argument("layer_id", help="World layer ID")


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
    elif cmd == "assign-layer":
        _cmd_assign_layer(args, session)
    elif cmd == "remove-layer":
        _cmd_remove_layer(args, session)
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
    """Show a relation, optionally extended."""
    import json as _json

    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = rs.get_by_id(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    r = result.value

    # Resolve entity names
    src_name = _rel_resolve_name(es, r.source_id)
    tgt_name = _rel_resolve_name(es, r.target_id)

    if args.json:
        payload = {
            "id": r.id,
            "relation_type": r.relation_type.value,
            "source_id": r.source_id,
            "source_name": src_name,
            "target_id": r.target_id,
            "target_name": tgt_name,
            "direction": r.direction.value if hasattr(r, "direction") else None,
            "description": r.description,
            "intensity": r.intensity.value if hasattr(r, "intensity") else None,
            "temporality": r.temporality if hasattr(r, "temporality") else None,
            "causality": r.causality if hasattr(r, "causality") else None,
            "canon_state": r.canon_state.value,
            "visibility_state": r.visibility_state.value,
            "certainty_level": r.certainty_level.value,
            "validity_conditions": list(r.validity_conditions) if hasattr(r, "validity_conditions") else [],
            "custom_relation_type_id": r.custom_relation_type_id if hasattr(r, "custom_relation_type_id") else None,
            "custom_fields": [
                {"field_id": cf.field_id, "value": cf.value}
                if hasattr(cf, "field_id") else cf
                for cf in (r.custom_fields if hasattr(r, "custom_fields") else [])
            ],
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        print(_json.dumps(payload, indent=2, ensure_ascii=False))
        return

    # ── Compact / extended text display ──
    print("═" * 55)
    print(f"  Relation: {r.id}")
    print("═" * 55)
    print(f"Type:         {r.relation_type.value}")
    print(f"Source:       {r.source_id} ({src_name})")
    print(f"Target:       {r.target_id} ({tgt_name})")
    print(f"Canon:        {r.canon_state.value}")
    print(f"Visibility:   {r.visibility_state.value}")
    if hasattr(r, "direction"):
        print(f"Direction:    {r.direction}")
    if r.description:
        print(f"Description:  {r.description}")

    # --- extended-only fields ---
    if args.extended:
        if hasattr(r, "intensity"):
            print(f"Intensity:    {r.intensity.value}")
        if hasattr(r, "certainty_level"):
            print(f"Certainty:    {r.certainty_level.value}")
        if hasattr(r, "temporality") and r.temporality:
            print(f"Temporality:  {r.temporality}")
        if hasattr(r, "causality") and r.causality:
            print(f"Causality:    {r.causality}")
        if hasattr(r, "validity_conditions") and r.validity_conditions:
            print(f"Validity:     {', '.join(r.validity_conditions)}")
        if hasattr(r, "layer_ids") and r.layer_ids:
            from packages.application.world_layer_service import WorldLayerService
            wls = WorldLayerService(ps)
            resolved = []
            for lid in r.layer_ids:
                lr = wls.get_layer(lid)
                if isinstance(lr, __import__('packages.domain.result', fromlist=['Ok']).Ok):
                    resolved.append(lr.value.name)
                else:
                    resolved.append(lid)
            print(f"Layers:       {', '.join(resolved)}")

    # --- shared fields ---
    if hasattr(r, "custom_relation_type_id") and r.custom_relation_type_id:
        print(f"Custom type:  {r.custom_relation_type_id}")
    if hasattr(r, "custom_fields") and r.custom_fields:
        print(f"Custom fields:")
        for cf in r.custom_fields:
            fid = cf.field_id if hasattr(cf, "field_id") else cf
            fval = cf.value if hasattr(cf, "value") else ""
            print(f"  {fid}: {fval}")

    # --- extended-only: sources & history ---
    if args.extended:
        # Sources linked to this relation
        try:
            src_result = ss.get_sources_for_relation(r.id)
            rel_sources = src_result.value if not isinstance(src_result, Error) else []
        except Exception:
            rel_sources = []
        print(f"Sources ({len(rel_sources)}):")
        if rel_sources:
            for s in rel_sources:
                st = s.source_type.value if hasattr(s, "source_type") else "?"
                print(f"  {s.id}  {s.name} ({st})")
        else:
            print("  (none)")

        # History
        try:
            hist_result = hs.get_for_relation(r.id)
            rel_history = hist_result.value if not isinstance(hist_result, Error) else []
        except Exception:
            rel_history = []
        print(f"History ({len(rel_history)}):")
        if rel_history:
            for h in rel_history[-5:]:
                ts = h.timestamp.isoformat() if hasattr(h, "timestamp") else "?"
                et = h.event_type.value if hasattr(h, "event_type") else "?"
                print(f"  {ts}  {et}")
        else:
            print("  (none)")

    print("═" * 55)


def _rel_resolve_name(es: Any, entity_id: str) -> str:
    """Resolve an entity name from its ID."""
    r = es.get_by_id(entity_id)
    if isinstance(r, Error):
        return f"(no encontrada: {entity_id})"
    return r.value.name


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


def _cmd_assign_layer(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = rs.assign_layer(args.id, args.layer_id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Layer assigned but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Layer '{args.layer_id}' assigned to relation '{args.id}'")


def _cmd_remove_layer(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = rs.remove_layer(args.id, args.layer_id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Layer removed but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Layer '{args.layer_id}' removed from relation '{args.id}'")
