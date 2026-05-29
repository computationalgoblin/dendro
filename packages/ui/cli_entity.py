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

    # entity show <id> [--extended] [--json]
    p_show = entity_subs.add_parser("show", help="Show entity card")
    p_show.add_argument("id", help="Entity ID")
    p_show.add_argument(
        "--extended", action="store_true",
        help="Show full entity card (23 fields)",
    )
    p_show.add_argument(
        "--json", action="store_true",
        help="JSON output",
    )

    # entity search <query> [--no-private]
    p_search = entity_subs.add_parser("search", help="Text search across entities")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument(
        "--no-private", action="store_true",
        help="Exclude private notes from search",
    )

    # entity set-field <entity-id> <field-id> <value>
    p_setf = entity_subs.add_parser("set-field", help="Set a custom field value")
    p_setf.add_argument("entity_id", help="Entity ID")
    p_setf.add_argument("field_id", help="Field definition ID")
    p_setf.add_argument("value", help="Value")

    # entity remove-field <entity-id> <field-id>
    p_rmf = entity_subs.add_parser("remove-field", help="Remove a custom field value")
    p_rmf.add_argument("entity_id", help="Entity ID")
    p_rmf.add_argument("field_id", help="Field definition ID")


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
    elif cmd == "set-field":
        _cmd_set_field(args, session)
    elif cmd == "remove-field":
        _cmd_remove_field(args, session)
    else:
        print(f"error: Unknown entity command '{cmd}'", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _cmd_create(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    entity_type = _parse_enum(args.type, EntityType, "entity type")
    data: dict[str, Any] = {"name": args.name, "entity_type": entity_type}
    if args.brief is not None:
        data["brief_description"] = args.brief
    if args.extended is not None:
        data["extended_description"] = args.extended
    if args.domain is not None:
        data["domain"] = args.domain

    result = es.create_entity(data, history_service=hs)
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
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

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

    result = es.update_entity(args.id, data, history_service=hs)
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
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = es.archive_entity(args.id, history_service=hs)
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


def _cmd_set_field(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    from packages.application.custom_type_service import CustomTypeService
    cts = CustomTypeService(project_service=ps)

    value = _convert_field_value(args.value)

    result = es.set_custom_field(
        args.entity_id, args.field_id, value, custom_type_service=cts,
    )
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Field set but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)
    print(f"Custom field '{args.field_id}' set on entity '{args.entity_id}'")


def _cmd_remove_field(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = es.remove_custom_field(args.entity_id, args.field_id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Field removed but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)
    print(f"Custom field '{args.field_id}' removed from entity '{args.entity_id}'")


def _convert_field_value(raw: str) -> Any:
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

def _cmd_show(args: argparse.Namespace, session: SessionContext) -> None:
    """Show an entity card, optionally extended with all 23 fields."""
    import json as _json

    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = qs.get_entity_card(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    card = result.value
    e = card.entity

    if args.json:
        # JSON output — always full
        payload = {
            "id": e.id,
            "name": e.name,
            "aliases": list(e.aliases),
            "entity_type": e.entity_type.value,
            "brief_description": e.brief_description,
            "extended_description": e.extended_description,
            "canon_state": e.canon_state.value,
            "visibility_state": e.visibility_state.value,
            "certainty_level": e.certainty_level.value,
            "tags": list(e.tags),
            "domain": e.domain,
            "layers": list(e.layers),
            "custom_type_id": e.custom_type_id,
            "custom_fields": [
                {"field_id": cf.field_id, "value": cf.value}
                if hasattr(cf, "field_id") else cf
                for cf in e.custom_fields
            ],
            "narrative_importance": e.narrative_importance.value,
            "development_level": e.development_level.value,
            "private_notes": e.private_notes,
            "exportable_notes": e.exportable_notes,
            "created_at": e.created_at.isoformat(),
            "updated_at": e.updated_at.isoformat(),
            "relations": {
                "incoming": [
                    {
                        "id": r.id,
                        "type": r.relation_type.value,
                        "source_id": r.source_id,
                        "source_name": _resolve_name(es, r.source_id),
                        "intensity": r.intensity.value if hasattr(r, "intensity") else None,
                    }
                    for r in card.incoming_relations
                ],
                "outgoing": [
                    {
                        "id": r.id,
                        "type": r.relation_type.value,
                        "target_id": r.target_id,
                        "target_name": _resolve_name(es, r.target_id),
                        "intensity": r.intensity.value if hasattr(r, "intensity") else None,
                    }
                    for r in card.outgoing_relations
                ],
            },
            "sources": [
                {"id": s.id, "name": s.name, "type": s.source_type.value if hasattr(s, "source_type") else "?"}
                for s in card.sources
            ],
            "open_issues": [
                {"id": iss.id, "title": iss.title, "severity": iss.severity}
                for iss in card.open_issues
            ],
            "history": [
                {"timestamp": h.timestamp.isoformat() if hasattr(h, "timestamp") else "?",
                 "event_type": h.event_type.value if hasattr(h, "event_type") else "?"}
                for h in card.history
            ],
        }
        print(_json.dumps(payload, indent=2, ensure_ascii=False))
        return

    # ── Compact or extended text display ──
    from packages.domain.relation import IntensityLevel
    MAIN_INTENSITIES = {IntensityLevel.ALTA, IntensityLevel.MUY_ALTA}

    # Header
    print("═" * 60)
    print(f"  {e.name}")
    print("═" * 60)
    print(f"ID:           {e.id}")
    print(f"Type:         {e.entity_type.value}")
    print(f"Canon:        {e.canon_state.value}")
    print(f"Visibility:   {e.visibility_state.value}")

    # --- extended-only fields ---
    if args.extended:
        if e.aliases:
            print(f"Alias(es):    {', '.join(e.aliases)}")
        print(f"Certainty:    {e.certainty_level.value}")
        print(f"Importance:   {e.narrative_importance.value}")
        print(f"Development:  {e.development_level.value}")
        print(f"Created:      {e.created_at.isoformat()}")
        print(f"Updated:      {e.updated_at.isoformat()}")

    # --- shared fields ---
    if e.domain:
        print(f"Domain:       {e.domain}")
    if e.custom_type_id:
        print(f"Custom type:  {e.custom_type_id}")
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
    if e.custom_fields:
        print(f"Custom fields:")
        for cf in e.custom_fields:
            print(f"  {cf.field_id}: {cf.value}")

    # --- extended-only: notes ---
    if args.extended:
        if e.private_notes:
            print(f"Notes (private): [PRIVADO] {e.private_notes[:120]}")
        if e.exportable_notes:
            print(f"Notes (export):  {e.exportable_notes[:120]}")

    print()

    # Relations
    incoming = card.incoming_relations
    outgoing = card.outgoing_relations
    rel_count = len(incoming) + len(outgoing)
    print(f"Relations ({len(incoming)} incoming, {len(outgoing)} outgoing):")
    for r in incoming:
        rel_name = _resolve_name(es, r.source_id)
        intensity = getattr(r, "intensity", None)
        main_mark = " ★" if args.extended and intensity in MAIN_INTENSITIES else ""
        print(f"  ← {r.relation_type.value} from {r.source_id} ({rel_name}){main_mark}")
    for r in outgoing:
        rel_name = _resolve_name(es, r.target_id)
        intensity = getattr(r, "intensity", None)
        main_mark = " ★" if args.extended and intensity in MAIN_INTENSITIES else ""
        print(f"  → {r.relation_type.value} to {r.target_id} ({rel_name}){main_mark}")
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
            ts = h.timestamp.isoformat() if hasattr(h, "timestamp") else "?"
            et = h.event_type.value if hasattr(h, "event_type") else "?"
            print(f"  {ts}  {et}")
    else:
        print("  Historial: no disponible")
    print()

    # --- extended-only: placeholders & actions ---
    if args.extended:
        print("Incidencias:  (no disponible — Bloque 12)")
        print("Sugerencias IA: (no disponible — Bloque 14)")
        print()
        print("Acciones:")
        print(f"  edit <id>           → entity edit {e.id}")
        print(f"  relations <id>      → relation list --entity {e.id}")
        print(f"  archive <id>        → entity archive {e.id}")

    print("═" * 60)


def _resolve_name(es: Any, entity_id: str) -> str:
    """Resolve an entity name from its ID, or return placeholder."""
    r = es.get_by_id(entity_id)
    if isinstance(r, Error):
        return f"(entidad no encontrada: {entity_id})"
    return r.value.name


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