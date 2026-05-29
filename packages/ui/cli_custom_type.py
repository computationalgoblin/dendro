"""
CLI custom type commands — ``custom-type entity`` and ``custom-type relation``
(B08-T04).

Registered by :func:`register_custom_type_commands`.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from packages.application.custom_type_service import CustomTypeService
from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)


def register_custom_type_commands(subparsers: Any) -> None:
    """Register ``custom-type`` subcommand under *subparsers*."""
    ct_parser = subparsers.add_parser("custom-type", help="Custom type commands")
    ct_subs = ct_parser.add_subparsers(dest="ct_command", required=True)

    # -- entity --
    e_parser = ct_subs.add_parser("entity", help="Custom entity type commands")
    e_subs = e_parser.add_subparsers(dest="entity_type_command", required=True)

    p_create = e_subs.add_parser("create", help="Create a custom entity type")
    p_create.add_argument("name", help="Type name")
    p_create.add_argument("--desc", default="", help="Description")
    p_create.add_argument("--base-category", default=None, help="Base EntityType")

    p_list = e_subs.add_parser("list", help="List custom entity types")
    p_list.add_argument("--inactive", action="store_true", help="Include inactive")

    p_show = e_subs.add_parser("show", help="Show custom entity type details")
    p_show.add_argument("id", help="Type ID")

    # -- relation --
    r_parser = ct_subs.add_parser("relation", help="Custom relation type commands")
    r_subs = r_parser.add_subparsers(dest="relation_type_command", required=True)

    p_rc = r_subs.add_parser("create", help="Create a custom relation type")
    p_rc.add_argument("name", help="Type name")
    p_rc.add_argument("--desc", default="", help="Description")
    p_rc.add_argument("--direction", default="unidireccional", help="Default direction")

    p_rl = r_subs.add_parser("list", help="List custom relation types")
    p_rl.add_argument("--inactive", action="store_true", help="Include inactive")

    p_rs = r_subs.add_parser("show", help="Show custom relation type details")
    p_rs.add_argument("id", help="Type ID")


def handle_custom_type_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch to entity or relation type handler."""
    if args.ct_command == "entity":
        _handle_entity_type(args, session)
    elif args.ct_command == "relation":
        _handle_relation_type(args, session)
    else:
        print(f"error: Unknown custom-type command '{args.ct_command}'", file=sys.stderr)
        sys.exit(1)


def _bootstrap_cts(project_path):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    cts = CustomTypeService(project_service=ps)
    return ps, es, rs, cts


def _handle_entity_type(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, cts = _bootstrap_cts(project_path)
    cmd = args.entity_type_command

    if cmd == "create":
        data: dict[str, Any] = {"name": args.name, "description": args.desc}
        if args.base_category:
            try:
                from packages.domain.entity import EntityType
                data["base_category"] = EntityType(args.base_category.lower())
            except ValueError:
                print(f"error: Invalid base category '{args.base_category}'", file=sys.stderr)
                sys.exit(1)
        result = cts.create_entity_type(data)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        ct = result.value
        save_result = ps.save(project_path)
        if isinstance(save_result, Error):
            print(f"error: Type created but save failed: {save_result.error}", file=sys.stderr)
            sys.exit(1)
        print(f"Custom entity type '{ct.name}' ({ct.id}) created")

    elif cmd == "list":
        result = cts.list_entity_types(include_inactive=args.inactive)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        types = result.value
        if not types:
            print("No custom entity types found.")
            return
        print(f"Custom entity types ({len(types)}):")
        for ct in types:
            active = "" if ct.is_active else " [INACTIVE]"
            print(f"  {ct.id}  {ct.name:<25}{active}")

    elif cmd == "show":
        result = cts.get_entity_type(args.id)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        ct = result.value
        print(f"Custom Entity Type: {ct.name}")
        print(f"  ID:             {ct.id}")
        print(f"  Description:    {ct.description or '(none)'}")
        print(f"  Base category:  {ct.base_category or '(none)'}")
        print(f"  Fields:         {len(ct.custom_fields)}")
        print(f"  Active:         {ct.is_active}")


def _handle_relation_type(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, cts = _bootstrap_cts(project_path)
    cmd = args.relation_type_command

    if cmd == "create":
        data: dict[str, Any] = {"name": args.name, "description": args.desc,
                                "default_direction": args.direction}
        result = cts.create_relation_type(data)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        crt = result.value
        save_result = ps.save(project_path)
        if isinstance(save_result, Error):
            print(f"error: Type created but save failed: {save_result.error}", file=sys.stderr)
            sys.exit(1)
        print(f"Custom relation type '{crt.name}' ({crt.id}) created")

    elif cmd == "list":
        result = cts.list_relation_types(include_inactive=args.inactive)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        types = result.value
        if not types:
            print("No custom relation types found.")
            return
        print(f"Custom relation types ({len(types)}):")
        for crt in types:
            active = "" if crt.is_active else " [INACTIVE]"
            print(f"  {crt.id}  {crt.name:<25}{active}")

    elif cmd == "show":
        result = cts.get_relation_type(args.id)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        crt = result.value
        print(f"Custom Relation Type: {crt.name}")
        print(f"  ID:         {crt.id}")
        print(f"  Direction:  {crt.default_direction}")
        print(f"  Active:     {crt.is_active}")
