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

    # entity list [--type <t>] [--canon <c>] [--visibility <v>] [--tag <t>] [--domain ...] [--limit <n>]
    p_list = entity_subs.add_parser("list", help="List/filter entities")
    p_list.add_argument("--type", default=None, metavar="TYPE", help="Filter by entity type")
    p_list.add_argument("--canon", default=None, metavar="STATE", help="Filter by canon state")
    p_list.add_argument(
        "--visibility", default=None, metavar="STATE",
        help="Filter by visibility state",
    )
    p_list.add_argument("--tag", default=None, help="Filter by tag")
    p_list.add_argument("--domain", default=None, help="Filter by domain")
    p_list.add_argument("--layer", default=None, help="Filter by layer")
    p_list.add_argument("--custom-type-id", default=None, help="Filter by custom entity type")
    p_list.add_argument("--source-id", default=None, help="Filter by source")
    p_list.add_argument("--domain-id", default=None, help="Filter by narrative domain (mundo/historia/campaña/compartido/sin_asignar)")
    p_list.add_argument("--layer-id", default=None, help="Filter by world layer ID")
    p_list.add_argument(
        "--sort", default="name",
        choices=["name", "updated_at", "created_at", "type", "canon", "certainty", "importance"],
        help="Sort field (default: name)",
    )
    p_list.add_argument("--sort-desc", action="store_true", help="Sort descending")
    p_list.add_argument("--offset", type=int, default=0, help="Pagination offset")
    p_list.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")
    p_list.add_argument(
        "--group-by", default=None,
        choices=["type", "tag", "canon", "visibility", "source"],
        help="Group results by field",
    )

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

    # entity quick-edit <id> [--name ...] [--brief ...] [--domain ...]
    p_qe = entity_subs.add_parser("quick-edit", help="Quick edit an entity")
    p_qe.add_argument("id", help="Entity ID")
    p_qe.add_argument("--name", default=None, help="New name")
    p_qe.add_argument("--brief", default=None, help="New brief description")
    p_qe.add_argument("--domain", default=None, help="New domain")

    # entity relations <id>
    p_er = entity_subs.add_parser("relations", help="Show relations of an entity")
    p_er.add_argument("id", help="Entity ID")

    # entity history <id>
    p_eh = entity_subs.add_parser("history", help="Show history of an entity")
    p_eh.add_argument("id", help="Entity ID")

    # entity sources <id>
    p_es = entity_subs.add_parser("sources", help="Show sources of an entity")
    p_es.add_argument("id", help="Entity ID")

    # entity assign-domain <id> <domain>
    p_ad = entity_subs.add_parser("assign-domain", help="Assign a narrative domain")
    p_ad.add_argument("id", help="Entity ID")
    p_ad.add_argument("domain", help="Domain (mundo, historia, campaña, compartido, sin_asignar)")

    # entity remove-domain <id> <domain>
    p_rd = entity_subs.add_parser("remove-domain", help="Remove a narrative domain")
    p_rd.add_argument("id", help="Entity ID")
    p_rd.add_argument("domain", help="Domain to remove")

    # entity assign-layer <id> <layer-id>
    p_al = entity_subs.add_parser("assign-layer", help="Assign a world layer")
    p_al.add_argument("id", help="Entity ID")
    p_al.add_argument("layer_id", help="World layer ID (e.g. layer_geografia)")

    # entity remove-layer <id> <layer-id>
    p_rl = entity_subs.add_parser("remove-layer", help="Remove a world layer")
    p_rl.add_argument("id", help="Entity ID")
    p_rl.add_argument("layer_id", help="World layer ID")


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
    elif cmd == "quick-edit":
        _cmd_quick_edit(args, session)
    elif cmd == "relations":
        _cmd_relations(args, session)
    elif cmd == "history":
        _cmd_history(args, session)
    elif cmd == "sources":
        _cmd_sources(args, session)
    elif cmd == "assign-domain":
        _cmd_assign_domain(args, session)
    elif cmd == "remove-domain":
        _cmd_remove_domain(args, session)
    elif cmd == "assign-layer":
        _cmd_assign_layer(args, session)
    elif cmd == "remove-layer":
        _cmd_remove_layer(args, session)
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

    # Map --sort choices to query sort_by
    sort_map = {"type": "entity_type", "canon": "canon_state"}

    result = qs.query(
        entity_type=entity_type,
        canon_state=canon_state,
        visibility_state=visibility,
        tag=args.tag,
        domain=args.domain,
        layer=args.layer,
        custom_type_id=args.custom_type_id,
        source_id=args.source_id,
        domain_id=getattr(args, "domain_id", None),
        layer_id=getattr(args, "layer_id", None),
        sort_by=sort_map.get(args.sort, args.sort),
        sort_desc=args.sort_desc,
        limit=args.limit,
        offset=args.offset,
    )
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    entities = result.value
    if not entities:
        print("No entities found.")
        return

    # ── group-by ──
    if args.group_by:
        _print_grouped(entities, args.group_by, es, ss)
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

    # --- extended-only: domain_ids and layer_ids (Bloque 10) ---
    if args.extended:
        if e.domain_ids:
            print(f"Domain (narr): {', '.join(e.domain_ids)}")
        if e.layer_ids:
            from packages.application.world_layer_service import WorldLayerService
            from packages.domain.result import Ok as ROk
            wls = WorldLayerService(ps)
            resolved = []
            for lid in e.layer_ids:
                lr = wls.get_layer(lid)
                if isinstance(lr, ROk):
                    resolved.append(lr.value.name)
                else:
                    resolved.append(lid)
            print(f"Layers (mundo): {', '.join(resolved)}")

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


# ---------------------------------------------------------------------------
# Group-by helper
# ---------------------------------------------------------------------------


def _print_grouped(entities: list[Any], field: str, es: Any, ss: Any) -> None:
    """Group entities by *field* and print with headers."""
    groups: dict[str, list[Any]] = {}
    for e in entities:
        if field == "type":
            key = e.entity_type.value
        elif field == "tag":
            keys = e.tags if e.tags else ["(sin etiqueta)"]
        elif field == "canon":
            key = e.canon_state.value
        elif field == "visibility":
            key = e.visibility_state.value
        elif field == "source":
            try:
                srcs = ss.get_sources_for_entity(e.id)
                keys = [s.name for s in srcs.value] if not isinstance(srcs, Error) else ["(sin fuente)"]
            except Exception:
                keys = ["(sin fuente)"]
            if not keys:
                keys = ["(sin fuente)"]
        else:
            continue

        if field in ("tag", "source"):
            for k in keys:
                groups.setdefault(k, []).append(e)
        else:
            groups.setdefault(key, []).append(e)

    for key in sorted(groups):
        g = groups[key]
        print(f"=== {key} ({len(g)}) ===")
        for i, e in enumerate(g, 1):
            print(_entity_list_row(e, index=i))


# ---------------------------------------------------------------------------
# Quick-edit
# ---------------------------------------------------------------------------


def _cmd_quick_edit(args: argparse.Namespace, session: SessionContext) -> None:
    """Edit a single field on an entity and auto-save."""
    edit_count = sum(1 for v in (args.name, args.brief, args.domain) if v is not None)
    if edit_count == 0:
        print("error: Especifica un campo: --name, --brief, o --domain", file=sys.stderr)
        sys.exit(1)
    if edit_count > 1:
        print("error: Solo se permite un campo por quick-edit", file=sys.stderr)
        sys.exit(1)

    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    data: dict[str, Any] = {}
    if args.name is not None:
        data["name"] = args.name
    elif args.brief is not None:
        data["brief_description"] = args.brief
    elif args.domain is not None:
        data["domain"] = args.domain

    result = es.update_entity(args.id, data, history_service=hs)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Quick-edit applied but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    updated = result.value
    print(f"Entity '{updated.name}' quick-edited: {list(data.keys())[0]} updated")


# ---------------------------------------------------------------------------
# Navigation shorthands
# ---------------------------------------------------------------------------


def _cmd_relations(args: argparse.Namespace, session: SessionContext) -> None:
    """Show relations for an entity (delegates to relation list --entity <id>)."""
    from packages.ui.cli_relation import _cmd_list as rel_list

    class _RelArgs:
        pass
    rel_args = _RelArgs()
    rel_args.entity = args.id
    rel_args.type = None
    rel_args.relation_command = "list"

    rel_list(rel_args, session)


def _cmd_history(args: argparse.Namespace, session: SessionContext) -> None:
    """Show history for an entity."""
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = hs.get_for_entity(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    entries = result.value
    if not entries:
        print(f"No history entries for entity '{args.id}'.")
        return

    print(f"History for entity '{args.id}' ({len(entries)} entries):")
    for h in entries:
        ts = h.timestamp.isoformat() if hasattr(h, "timestamp") else "?"
        et = h.event_type.value if hasattr(h, "event_type") else "?"
        desc = getattr(h, "description", "")
        detail = f" — {desc}" if desc else ""
        print(f"  {ts}  {et}{detail}")


def _cmd_sources(args: argparse.Namespace, session: SessionContext) -> None:
    """Show sources linked to an entity."""
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = ss.get_sources_for_entity(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    sources = result.value
    if not sources:
        print(f"No sources linked to entity '{args.id}'.")
        return

    print(f"Sources for entity '{args.id}' ({len(sources)}):")
    for s in sources:
        st = s.source_type.value if hasattr(s, "source_type") else "?"
        print(f"  {s.id}  {s.name} ({st})")


def _cmd_assign_domain(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = es.assign_domain(args.id, args.domain)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Domain assigned but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Domain '{args.domain}' assigned to entity '{args.id}'")


def _cmd_remove_domain(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = es.remove_domain(args.id, args.domain)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Domain removed but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Domain '{args.domain}' removed from entity '{args.id}'")


def _cmd_assign_layer(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = es.assign_layer(args.id, args.layer_id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Layer assigned but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Layer '{args.layer_id}' assigned to entity '{args.id}'")


def _cmd_remove_layer(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    result = es.remove_layer(args.id, args.layer_id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Layer removed but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Layer '{args.layer_id}' removed from entity '{args.id}'")