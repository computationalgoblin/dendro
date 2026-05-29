"""
CLI layer commands — ``layer list``, ``show``, ``create``, ``edit``,
``hide``, ``unhide``, ``reorder`` (B10-T04).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from packages.application.world_layer_service import WorldLayerService
from packages.domain.result import Error, Ok
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)
from packages.ui.cli_entity import _entity_list_row


def register_layer_commands(subparsers: Any) -> None:
    """Register the ``layer`` subcommand under *subparsers*."""
    layer_parser = subparsers.add_parser("layer", help="World layer commands")
    layer_subs = layer_parser.add_subparsers(dest="layer_command", required=True)

    # layer list [--all]
    p_list = layer_subs.add_parser("list", help="List world layers")
    p_list.add_argument("--all", dest="show_all", action="store_true",
                         help="Include hidden layers")

    # layer show <id>
    p_show = layer_subs.add_parser("show", help="Show layer details")
    p_show.add_argument("id", help="Layer ID")

    # layer create <name> [--desc <desc>] [--order <n>]
    p_create = layer_subs.add_parser("create", help="Create a custom layer")
    p_create.add_argument("name", help="Layer name")
    p_create.add_argument("--desc", default="", help="Description")
    p_create.add_argument("--order", type=int, default=None, help="Display order")

    # layer edit <id> [--name <n>] [--desc <d>]
    p_edit = layer_subs.add_parser("edit", help="Edit a layer")
    p_edit.add_argument("id", help="Layer ID")
    p_edit.add_argument("--name", default=None, help="New name")
    p_edit.add_argument("--desc", default=None, help="New description")

    # layer hide <id>
    p_hide = layer_subs.add_parser("hide", help="Hide a layer")
    p_hide.add_argument("id", help="Layer ID")

    # layer unhide <id>
    p_unhide = layer_subs.add_parser("unhide", help="Unhide a layer")
    p_unhide.add_argument("id", help="Layer ID")

    # layer reorder <id> <order>
    p_reorder = layer_subs.add_parser("reorder", help="Change layer order")
    p_reorder.add_argument("id", help="Layer ID")
    p_reorder.add_argument("order", type=int, help="New order")


def handle_layer_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch to the correct layer subcommand handler."""
    cmd = args.layer_command
    if cmd == "list":
        _cmd_layer_list(args, session)
    elif cmd == "show":
        _cmd_layer_show(args, session)
    elif cmd == "create":
        _cmd_layer_create(args, session)
    elif cmd == "edit":
        _cmd_layer_edit(args, session)
    elif cmd == "hide":
        _cmd_layer_hide(args, session)
    elif cmd == "unhide":
        _cmd_layer_unhide(args, session)
    elif cmd == "reorder":
        _cmd_layer_reorder(args, session)
    else:
        print(f"error: Unknown layer command '{cmd}'", file=sys.stderr)
        sys.exit(1)


def _cmd_layer_list(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    wls = WorldLayerService(ps)

    layers = wls.list_layers(include_hidden=args.show_all)
    print(f"Layers ({len(layers)}):")
    for wl in layers:
        vis = "" if wl.is_visible else " [oculta]"
        default = " (default)" if wl.is_default else " (custom)"
        print(f"  {wl.order:3d}. {wl.id:25s} {wl.name[:40]:40s}{vis}{default}")


def _cmd_layer_show(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    wls = WorldLayerService(ps)

    result = wls.get_layer(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    wl = result.value
    print(f"Layer: {wl.name}")
    print(f"ID:          {wl.id}")
    print(f"Description: {wl.description or '(none)'}")
    print(f"Order:       {wl.order}")
    print(f"Visible:     {wl.is_visible}")
    print(f"Default:     {wl.is_default}")

    # Show entities in this layer
    layer_entities = es.get_by_layer(wl.id)
    if isinstance(layer_entities, Ok):
        ents = layer_entities.value
        print(f"Entities ({len(ents)}):")
        if ents:
            for e in ents:
                print(f"  {e.id[:8]} {e.name[:30]}")
        else:
            print("  (none)")


def _cmd_layer_create(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    wls = WorldLayerService(ps)

    result = wls.create_layer(args.name, description=args.desc, order=args.order)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Layer created but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Layer '{result.value.name}' ({result.value.id}) created")


def _cmd_layer_edit(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    wls = WorldLayerService(ps)

    kwargs: dict[str, Any] = {}
    if args.name is not None:
        kwargs["name"] = args.name
    if args.desc is not None:
        kwargs["description"] = args.desc

    if not kwargs:
        print("error: No fields to edit. Provide --name or --desc.", file=sys.stderr)
        sys.exit(1)

    result = wls.update_layer(args.id, **kwargs)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Layer updated but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Layer '{args.id}' updated")


def _cmd_layer_hide(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    wls = WorldLayerService(ps)

    result = wls.hide_layer(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Layer hidden but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Layer '{args.id}' hidden")


def _cmd_layer_unhide(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    wls = WorldLayerService(ps)

    result = wls.show_layer(args.id)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Layer unhidden but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Layer '{args.id}' unhidden")


def _cmd_layer_reorder(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    wls = WorldLayerService(ps)

    result = wls.reorder_layer(args.id, args.order)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Layer reordered but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Layer '{args.id}' order set to {args.order}")
