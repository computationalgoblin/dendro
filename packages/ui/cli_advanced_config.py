"""
CLI advanced config commands — ``project config advanced get``, ``set``, ``show`` (B10-T04).
"""

from __future__ import annotations

import argparse
import json as _json
import sys
from typing import Any

from packages.application.advanced_config_service import AdvancedConfigService
from packages.domain.advanced_config import CONFIG_PATH_WHITELIST
from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    convert_config_value,
    require_project_path,
)


def register_advanced_config_commands(project_config_subs: Any) -> None:
    """Register ``advanced`` subcommand under the ``project config`` subparser."""
    adv_parser = project_config_subs.add_parser(
        "advanced", help="Advanced project configuration"
    )
    adv_subs = adv_parser.add_subparsers(dest="advanced_command")

    # project config advanced show
    adv_subs.add_parser("show", help="Show all advanced configuration")

    # project config advanced get <path>
    p_get = adv_subs.add_parser("get", help="Get a config value")
    p_get.add_argument("path", help=f"Config path. Valid: {', '.join(sorted(CONFIG_PATH_WHITELIST))}")

    # project config advanced set <path> <value>
    p_set = adv_subs.add_parser("set", help="Set a config value")
    p_set.add_argument("path", help=f"Config path. Valid: {', '.join(sorted(CONFIG_PATH_WHITELIST))}")
    p_set.add_argument("value", help="Value. Arrays as JSON: '[\"a\", \"b\"]'")


def handle_advanced_config_command(
    args: argparse.Namespace, session: SessionContext
) -> None:
    """Dispatch to the correct advanced config subcommand."""
    cmd = getattr(args, "advanced_command", None)
    if cmd is None:
        print("error: Missing advanced config command (show, get, set)", file=sys.stderr)
        sys.exit(1)

    if cmd == "show":
        _cmd_advanced_show(args, session)
    elif cmd == "get":
        _cmd_advanced_get(args, session)
    elif cmd == "set":
        _cmd_advanced_set(args, session)
    else:
        print(f"error: Unknown advanced config command '{cmd}'", file=sys.stderr)
        sys.exit(1)


def _cmd_advanced_show(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    svc = AdvancedConfigService(ps)

    result = svc.get_config()
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    cfg = result.value
    print("Advanced Configuration:")
    print(f"  Genre:")
    print(f"    primary:              {cfg.primary_genre or '(not set)'}")
    print(f"    subgenres:            {', '.join(cfg.subgenres) if cfg.subgenres else '(none)'}")
    print(f"  Tone:")
    print(f"    global:               {cfg.global_tone}")
    print(f"    secondary:            {', '.join(cfg.secondary_tones) if cfg.secondary_tones else '(none)'}")
    print(f"  Realism:")
    print(f"    level:                {cfg.realism_level}")
    print(f"    contradiction:        {cfg.contradiction_tolerance}")
    print(f"  Conventions:")
    print(f"    naming:               {cfg.naming_conventions or '(not set)'}")
    print(f"    languages:            {', '.join(cfg.internal_languages) if cfg.internal_languages else '(none)'}")
    print(f"    calendar:             {cfg.internal_calendar or '(not set)'}")
    print(f"    measurement:          {cfg.measurement_units or '(not set)'}")
    print(f"  Rules:")
    print(f"    visibility:           {cfg.visibility_rules or '(not set)'}")
    print(f"    creative restrictions: {', '.join(cfg.creative_restrictions) if cfg.creative_restrictions else '(none)'}")
    print(f"  Future AI:")
    print(f"    preferences:          {', '.join(cfg.future_ai_preferences) if cfg.future_ai_preferences else '(none)'}")


def _cmd_advanced_get(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    svc = AdvancedConfigService(ps)

    result = svc.get_value(args.path)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    value = result.value
    if isinstance(value, list):
        print(_json.dumps(value, ensure_ascii=False))
    else:
        print(str(value))


def _cmd_advanced_set(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    svc = AdvancedConfigService(ps)

    # Convert value: try JSON for arrays, else string
    value = convert_config_value(args.value)

    result = svc.set_value(args.path, value)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    # Auto-save
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        print(f"error: Config updated but save failed: {save_result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Config '{args.path}' set")
