"""
CLI project commands — ``project create``, ``open``, ``save``, ``close``,
``info``, and ``config get/set``.

Registered by :func:`register_project_commands` and dispatched via
:func:`handle_project_command`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from packages.application.project_service import ProjectService
from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    convert_config_value,
    require_project_path,
    resolve_project_path,
)


def register_project_commands(subparsers: Any) -> None:
    """Register the ``project`` subcommand and its sub-subcommands."""
    project_parser = subparsers.add_parser("project", help="Project lifecycle commands")
    project_subs = project_parser.add_subparsers(dest="project_command", required=True)

    # project create <name> [--path <file>]
    p_create = project_subs.add_parser("create", help="Create a new project")
    p_create.add_argument("name", help="Project name")
    p_create.add_argument("--path", metavar="FILE", help="Save to this file")

    # project open <path>
    p_open = project_subs.add_parser("open", help="Open an existing project")
    p_open.add_argument("path", help="Path to the project file")

    # project save [path]
    p_save = project_subs.add_parser("save", help="Save the active project")
    p_save.add_argument("path", nargs="?", default=None, help="Save to this file (optional)")

    # project close
    project_subs.add_parser("close", help="Close the active project")

    # project info
    project_subs.add_parser("info", help="Show project information")

    # project config get <path>
    p_cfg_get = project_subs.add_parser("config", help="Read or modify configuration")
    cfg_subs = p_cfg_get.add_subparsers(dest="config_command", required=True)
    p_get = cfg_subs.add_parser("get", help="Read a configuration value")
    p_get.add_argument("path", help="Dotted configuration path (e.g. general.theme)")

    # project config set <path> <value>
    p_set = cfg_subs.add_parser("set", help="Set a configuration value")
    p_set.add_argument("path", help="Dotted configuration path")
    p_set.add_argument("value", help="New value (string, JSON for dicts/lists)")

    # project config advanced (get|set|show)
    from packages.ui.cli_advanced_config import register_advanced_config_commands
    register_advanced_config_commands(cfg_subs)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_project_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch to the correct project subcommand handler."""
    cmd = args.project_command
    if cmd == "create":
        _cmd_create(args, session)
    elif cmd == "open":
        _cmd_open(args, session)
    elif cmd == "save":
        _cmd_save(args, session)
    elif cmd == "close":
        _cmd_close(args, session)
    elif cmd == "info":
        _cmd_info(args, session)
    elif cmd == "config":
        _cmd_config(args, session)
    else:
        print(f"error: Unknown project command '{cmd}'", file=sys.stderr)
        sys.exit(1)


# ── create ──────────────────────────────────────────────────────────────────


def _cmd_create(args: argparse.Namespace, session: SessionContext) -> None:
    ps = ProjectService()
    result = ps.create(name=args.name)

    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    project = result.value

    save_path = Path(args.path) if args.path else None
    if save_path:
        save_result = ps.save(save_path)
        if isinstance(save_result, Error):
            print(
                f"error: Project created but save failed: {save_result.error}",
                file=sys.stderr,
            )
            sys.exit(1)
        session.set_project_path(save_path.resolve())
        print(f"Project '{project.name}' ({project.id}) created and saved to {save_path.resolve()}")
    else:
        session.set_project_path(Path(f"{project.id}.json"))
        print(f"Project '{project.name}' ({project.id}) created (not persisted — use project save)")
    sys.exit(0)


# ── open ────────────────────────────────────────────────────────────────────


def _cmd_open(args: argparse.Namespace, session: SessionContext) -> None:
    ps = ProjectService()
    open_path = Path(args.path).resolve()

    if not open_path.exists():
        print(f"error: File not found: {open_path}", file=sys.stderr)
        sys.exit(1)

    result = ps.open(open_path)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    session.set_project_path(open_path)
    project = result.value
    print(f"Project '{project.name}' ({project.id}) opened from {open_path}")
    sys.exit(0)


# ── save ────────────────────────────────────────────────────────────────────


def _cmd_save(args: argparse.Namespace, session: SessionContext) -> None:
    # Determine the save path
    if args.path:
        save_path = Path(args.path)
    else:
        resolved = session.get_project_path()
        if resolved is None:
            print(
                "error: No project path. Use 'project save <path>' or open a project first.",
                file=sys.stderr,
            )
            sys.exit(1)
        save_path = resolved

    project_path = require_project_path(args, session)
    ps, *_ = _bootstrap_services(project_path)
    result = ps.save(save_path)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    print(f"Project saved to {save_path}")
    sys.exit(0)


# ── close ───────────────────────────────────────────────────────────────────


def _cmd_close(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = resolve_project_path(args, session)
    if project_path is None:
        print("No active project to close.", file=sys.stderr)
        sys.exit(1)

    ps, *_ = _bootstrap_services(project_path)
    ps.close()
    session.clear()
    # ps.active_project should now be None after close
    print("Project closed. Session cleared.")
    sys.exit(0)


# ── info ────────────────────────────────────────────────────────────────────


def _cmd_info(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    p = ps.active_project
    if p is None:
        print("error: No active project", file=sys.stderr)
        sys.exit(1)

    print(f"Project: {p.name}")
    print(f"  ID:            {p.id}")
    print(f"  Language:      {p.primary_language}")
    print(f"  Theme:         {p.general.theme or '(none)'}")
    print(f"  Entities:      {len(p.entities)}")
    print(f"  Relations:     {len(p.relations)}")
    print(f"  Sources:       {len(p.sources)}")
    print(f"  History:       {len(p.history)}")
    print(f"  Issues:        {len(p.issues)}")
    print(f"  Candidates:    {len(p.candidates)}")
    print(f"  Created:       {p.created_at.isoformat() if p.created_at else 'N/A'}")
    print(f"  Updated:       {p.updated_at.isoformat() if p.updated_at else 'N/A'}")
    sys.exit(0)


# ── config get / set ────────────────────────────────────────────────────────


def _cmd_config(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, *_ = _bootstrap_services(project_path)

    if args.config_command == "get":
        result = ps.get_config(args.path)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        value = result.value
        if isinstance(value, (dict, list)):
            print(json.dumps(value, indent=2, ensure_ascii=False))
        else:
            print(value)
    elif args.config_command == "set":
        try:
            typed = convert_config_value(args.value)
        except json.JSONDecodeError as e:
            print(f"error: Invalid JSON value: {e}", file=sys.stderr)
            sys.exit(1)

        update_result = ps.update_config(args.path, typed)
        if isinstance(update_result, Error):
            print(f"error: {update_result.error}", file=sys.stderr)
            sys.exit(1)

        # Auto-save after Ok
        save_result = ps.save(project_path)
        if isinstance(save_result, Error):
            print(
                f"error: Config updated in memory but save failed: {save_result.error}",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Set {args.path} = {args.value}")
    elif args.config_command == "advanced":
        from packages.ui.cli_advanced_config import handle_advanced_config_command
        handle_advanced_config_command(args, session)
        return
    sys.exit(0)
