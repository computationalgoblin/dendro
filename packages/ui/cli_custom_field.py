"""
CLI custom field commands — ``custom-field create``, ``list``, ``show`` (B08-T04).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from packages.application.custom_type_service import CustomTypeService
from packages.domain.custom_types import FieldType
from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)


def register_custom_field_commands(subparsers: Any) -> None:
    """Register ``custom-field`` subcommand under *subparsers*."""
    cf_parser = subparsers.add_parser("custom-field", help="Custom field commands")
    cf_subs = cf_parser.add_subparsers(dest="cf_command", required=True)

    p_create = cf_subs.add_parser("create", help="Create a custom field definition")
    p_create.add_argument("name", help="Field name")
    p_create.add_argument("--type", required=True, metavar="TYPE", help="Field type")
    p_create.add_argument("--desc", default="", help="Description")
    p_create.add_argument("--options", default=None, help="Options for select fields (comma-separated)")
    p_create.add_argument("--required", action="store_true", help="Field is required")

    p_list = cf_subs.add_parser("list", help="List field definitions")
    p_list.add_argument("--entity-type-id", default=None, help="Filter by custom entity type ID")
    p_list.add_argument("--inactive", action="store_true", help="Include inactive")

    p_show = cf_subs.add_parser("show", help="Show field definition details")
    p_show.add_argument("id", help="Field ID")


def handle_custom_field_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch custom field commands."""
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    cts = CustomTypeService(project_service=ps)
    cmd = args.cf_command

    if cmd == "create":
        # Parse field type
        try:
            ft = FieldType(args.type.lower())
        except ValueError:
            valid = ", ".join(sorted(e.value for e in FieldType))
            print(f"error: Invalid field type '{args.type}'. Valid: {valid}", file=sys.stderr)
            sys.exit(1)

        # Parse options with space normalization
        options = []
        if args.options:
            options = [o.strip() for o in args.options.split(",") if o.strip()]

        data: dict[str, Any] = {
            "name": args.name,
            "field_type": ft,
            "description": args.desc,
            "required": args.required,
            "options": options,
        }
        result = cts.create_field_definition(data)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        fd = result.value
        save_result = ps.save(project_path)
        if isinstance(save_result, Error):
            print(f"error: Field created but save failed: {save_result.error}", file=sys.stderr)
            sys.exit(1)
        print(f"Custom field '{fd.name}' ({fd.id}) created [{fd.field_type.value}]")

    elif cmd == "list":
        result = cts.list_field_definitions(
            include_inactive=args.inactive,
            entity_type_id=args.entity_type_id,
        )
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        fds = result.value
        if not fds:
            print("No custom field definitions found.")
            return
        print(f"Custom field definitions ({len(fds)}):")
        for fd in fds:
            active = "" if fd.is_active else " [INACTIVE]"
            print(f"  {fd.id}  {fd.name:<25} {fd.field_type.value:<15}{active}")

    elif cmd == "show":
        result = cts.get_field_definition(args.id)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        fd = result.value
        print(f"Custom Field: {fd.name}")
        print(f"  ID:         {fd.id}")
        print(f"  Type:       {fd.field_type.value}")
        print(f"  Required:   {fd.required}")
        if fd.options:
            print(f"  Options:    {', '.join(fd.options)}")
        print(f"  Active:     {fd.is_active}")
