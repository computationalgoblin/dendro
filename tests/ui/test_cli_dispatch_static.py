"""Static guards for CLI parser/handler dispatch coverage.

The project has repeatedly hit a silent failure mode: a subcommand is registered in
argparse but no matching handler branch exists. These tests inspect the real parser
and the handler source to keep the common command modules covered.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

from packages.ui.cli import _build_parser

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "packages" / "ui"

ROOT_MODULE_BY_COMMAND = {
    "project": "cli_project.py",
    "entity": "cli_entity.py",
    "relation": "cli_relation.py",
    "history": "cli_history.py",
    "source": "cli_source.py",
    "custom-type": "cli_custom_type.py",
    "custom-field": "cli_custom_field.py",
    "gallery": "cli_gallery.py",
    "domain": "cli_domain.py",
    "layer": "cli_layer.py",
    "graph": "cli_graph.py",
    "issue": "cli_issue.py",
    "framework": "cli_framework.py",
    "candidate": "cli_candidate.py",
    "ai": "cli_ai.py",
    "export": "cli_export.py",
    "timeline": "cli_timeline.py",
    "writing": "cli_writing.py",
    "campaign": "cli_campaign.py",
    "secret": "cli_secrets.py",
    "clue": "cli_secrets.py",
    "session": "cli_session.py",
    "faction": "cli_faction.py",
    "front": "cli_faction.py",
    "maintenance": "cli_maintenance.py",
}

# Modules whose subcommands are direct string-dispatched and stable enough for a
# strict parser-vs-handler comparison. More dynamic/nested modules can be added
# after a dedicated audit.
STRICT_SUBCOMMAND_ROOTS = {
    "ai",
    "candidate",
    "domain",
    "entity",
    "export",
    "history",
    "issue",
    "layer",
    "maintenance",
    "relation",
    "source",
    "timeline",
    "writing",
}


def _subparser_actions(parser: argparse.ArgumentParser) -> list[argparse._SubParsersAction]:
    return [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]


def _parser_paths(parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    for action in _subparser_actions(parser):
        for name, subparser in action.choices.items():
            path = (*prefix, name)
            paths.append(path)
            paths.extend(_parser_paths(subparser, path))
    return paths


def _comparison_strings(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        sides = [node.left, *node.comparators]
        for side in sides:
            if isinstance(side, ast.Constant) and isinstance(side.value, str):
                values.add(side.value)
            elif isinstance(side, (ast.Tuple, ast.List, ast.Set)):
                for elt in side.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        values.add(elt.value)
    return values


def test_root_cli_commands_have_main_dispatch_branches() -> None:
    """Every top-level parser command must be routed from cli.main()."""
    parser = _build_parser()
    root_commands = {path[0] for path in _parser_paths(parser)}
    main_dispatch_strings = _comparison_strings(UI / "cli.py")

    missing = sorted(root_commands - main_dispatch_strings)

    assert not missing, "Top-level commands registered but not dispatched: " + ", ".join(missing)


def test_common_cli_subcommands_have_handler_branches() -> None:
    """Strict modules must compare each registered leaf subcommand in their handler."""
    parser = _build_parser()
    all_paths = _parser_paths(parser)
    missing: list[str] = []

    comparisons_by_module = {
        module: _comparison_strings(UI / module)
        for module in set(ROOT_MODULE_BY_COMMAND.values())
        if (UI / module).exists()
    }

    for path in all_paths:
        root = path[0]
        if root not in STRICT_SUBCOMMAND_ROOTS or len(path) != 2:
            continue
        subcommand = path[1]
        module = ROOT_MODULE_BY_COMMAND[root]
        if subcommand not in comparisons_by_module[module]:
            missing.append(f"{root}/{subcommand} ({module})")

    assert not missing, "Subcommands registered but not dispatched: " + ", ".join(missing)
