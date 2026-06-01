"""
CLI root — argument parser, SessionContext, bootstrap, and main entry point.

Provides:

* :class:`SessionContext` — persists the active project path across CLI commands
  via `.narrative-session.json`.
* :func:`resolve_project_path` — resolves the project path from ``--project`` flag
  or session state.
* :func:`bootstrap` — initializes all application services for a given project path.
* :func:`main` — top-level ``argparse`` dispatcher.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.application.entity_service import EntityService
from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.query_service import QueryService
from packages.application.relation_service import RelationService
from packages.application.source_service import SourceService
from packages.application.text_search_service import TextSearchService
from packages.domain.result import Error
from packages.persistence.store import ProjectStore

# ---------------------------------------------------------------------------
# SessionContext
# ---------------------------------------------------------------------------


@dataclass
class SessionContext:
    """Persists the active project path between CLI invocations.

    Reads/writes a small JSON file (``.narrative-session.json``) in the
    current working directory.
    """

    session_file: Path = Path(".narrative-session.json")

    def get_project_path(self) -> Path | None:
        """Return the persisted project path, or None."""
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
            raw = data.get("project_path")
            return Path(raw) if raw else None
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None

    def set_project_path(self, path: Path) -> None:
        """Persist the given project path."""
        self.session_file.write_text(
            json.dumps({"project_path": str(path)}, indent=2), encoding="utf-8"
        )

    def clear(self) -> None:
        """Remove the session file if it exists."""
        try:
            self.session_file.unlink()
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def convert_config_value(raw: str) -> Any:
    """Convert a CLI string value to the best typed equivalent.

    Rules (from B07-T01 §5):
    * ``"true"`` / ``"false"`` → ``bool``
    * integer → ``int``
    * float (contains ``.``) → ``float``
    * JSON (starts with ``{`` or ``[``) → ``dict`` / ``list``
      Raises :class:`ValueError` if the JSON is invalid.
    * otherwise → ``str``
    """
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"

    if raw.startswith("{") or raw.startswith("["):
        return json.loads(raw)

    try:
        return int(raw)
    except ValueError:
        pass

    try:
        return float(raw)
    except ValueError:
        pass

    return raw


def resolve_project_path(
    args: argparse.Namespace, session: SessionContext
) -> Path | None:
    """Resolve the project path from ``--project`` or session state.

    Returns:
        The resolved :class:`Path`, or ``None`` when no project is configured.
    """
    if getattr(args, "project", None):
        return Path(args.project)
    return session.get_project_path()


def require_project_path(
    args: argparse.Namespace, session: SessionContext
) -> Path:
    """Resolve the project path; exit with an error message if none is found."""
    path = resolve_project_path(args, session)
    if path is None:
        print(
            "error: No active project. Use --project <path> or open a project first.",
            file=sys.stderr,
        )
        sys.exit(1)
    return path


def _bootstrap_services(
    project_path: Path | None = None,
) -> tuple[ProjectService, EntityService, RelationService, SourceService,
           HistoryService, QueryService, TextSearchService]:
    """Initialise all application services.

    When *project_path* is provided the project is opened automatically.
    """
    store = ProjectStore()
    ps = ProjectService(store=store)

    if project_path is not None:
        result = ps.open(project_path)
        if isinstance(result, Error):
            print(f"error: Failed to open project: {result.error}", file=sys.stderr)
            sys.exit(1)

    hs = HistoryService(project_service=ps)
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    ss = SourceService(project_service=ps, store=store)
    qs = QueryService(
        entity_service=es,
        relation_service=rs,
        source_service=ss,
        history_service=hs,
    )
    ts = TextSearchService(entity_service=es, relation_service=rs)

    return ps, es, rs, ss, hs, qs, ts


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the root argument parser with ``--project`` and subcommands."""
    parser = argparse.ArgumentParser(
        prog="narrative-architect",
        description="CLI for narrative-architect — worldbuilding and RPG campaign management",
    )
    parser.add_argument(
        "--project",
        metavar="PATH",
        help="Path to the project file (overrides session)",
    )

    sub = parser.add_subparsers(dest="command", title="commands")

    # ── project ──────────────────────────────────────────────────────────
    from packages.ui.cli_project import register_project_commands

    register_project_commands(sub)

    # ── entity ────────────────────────────────────────────────────────────
    from packages.ui.cli_entity import register_entity_commands

    register_entity_commands(sub)

    # ── relation ───────────────────────────────────────────────────────────
    from packages.ui.cli_relation import register_relation_commands

    register_relation_commands(sub)

    # ── history ────────────────────────────────────────────────────────────
    from packages.ui.cli_history import register_history_commands

    register_history_commands(sub)

    # ── source ─────────────────────────────────────────────────────────────
    from packages.ui.cli_source import register_source_commands

    register_source_commands(sub)

    # ── custom-type ─────────────────────────────────────────────────
    from packages.ui.cli_custom_type import register_custom_type_commands

    register_custom_type_commands(sub)

    # ── custom-field ────────────────────────────────────────────────
    from packages.ui.cli_custom_field import register_custom_field_commands

    register_custom_field_commands(sub)

    # ── gallery ──────────────────────────────────────────────────────
    from packages.ui.cli_gallery import register_gallery_commands

    register_gallery_commands(sub)

    # ── domain ──────────────────────────────────────────────────────
    from packages.ui.cli_domain import register_domain_commands

    register_domain_commands(sub)

    # ── layer ───────────────────────────────────────────────────────
    from packages.ui.cli_layer import register_layer_commands

    register_layer_commands(sub)

    # ── graph ─────────────────────────────────────────────────────────
    from packages.ui.cli_graph import register_graph_commands

    register_graph_commands(sub)

    # ── issue ──────────────────────────────────────────────────────────
    from packages.ui.cli_issue import register_issue_commands

    register_issue_commands(sub)

    # framework
    from packages.ui.cli_framework import register_framework_commands
    register_framework_commands(sub)

    # candidate
    from packages.ui.cli_candidate import register_candidate_commands
    register_candidate_commands(sub)

    # ai
    from packages.ui.cli_ai import register_ai_commands
    register_ai_commands(sub)

    # import
    from packages.ui.cli_import import register_import_commands
    register_import_commands(sub)

    # timeline
    from packages.ui.cli_timeline import register_timeline_commands
    register_timeline_commands(sub)

    from packages.ui.cli_writing import register_writing_commands
    register_writing_commands(sub)

    from packages.ui.cli_campaign import register_campaign_commands
    register_campaign_commands(sub)

    from packages.ui.cli_secrets import register_secrets_commands
    from packages.ui.cli_faction import register_faction_commands
    register_faction_commands(sub)

    register_secrets_commands(sub)
    from packages.ui.cli_faction import register_faction_commands
    register_faction_commands(sub)


    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments, resolve the project, bootstrap, and dispatch."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    session = SessionContext()

    # ── Commands that don't need a pre-loaded project ────────────────────
    if args.command == "project":
        from packages.ui.cli_project import handle_project_command

        handle_project_command(args, session)
        return

    # ── Entity commands ───────────────────────────────────────────────────
    if args.command == "entity":
        from packages.ui.cli_entity import handle_entity_command

        handle_entity_command(args, session)
        return

    # ── Relation commands ─────────────────────────────────────────────────
    if args.command == "relation":
        from packages.ui.cli_relation import handle_relation_command

        handle_relation_command(args, session)
        return

    # ── History commands ──────────────────────────────────────────────────
    if args.command == "history":
        from packages.ui.cli_history import handle_history_command

        handle_history_command(args, session)
        return

    # ── Source commands ───────────────────────────────────────────────────
    if args.command == "source":
        from packages.ui.cli_source import handle_source_command

        handle_source_command(args, session)
        return

    # ── Custom type commands ────────────────────────────────────────────
    if args.command == "custom-type":
        from packages.ui.cli_custom_type import handle_custom_type_command

        handle_custom_type_command(args, session)
        return

    # ── Custom field commands ───────────────────────────────────────────
    if args.command == "custom-field":
        from packages.ui.cli_custom_field import handle_custom_field_command

        handle_custom_field_command(args, session)
        return

    # ── Gallery commands ──────────────────────────────────────────────
    if args.command == "gallery":
        from packages.ui.cli_gallery import handle_gallery_command

        handle_gallery_command(args, session)
        return

    # ── Domain commands ─────────────────────────────────────────────
    if args.command == "domain":
        from packages.ui.cli_domain import handle_domain_command

        handle_domain_command(args, session)
        return

    # ── Layer commands ──────────────────────────────────────────────
    if args.command == "layer":
        from packages.ui.cli_layer import handle_layer_command

        handle_layer_command(args, session)
        return

    # ── Graph commands ──────────────────────────────────────────────
    if args.command == "graph":
        from packages.ui.cli_graph import handle_graph_command

        handle_graph_command(args, session)
        return

    # ── Issue commands ──────────────────────────────────────────────
    if args.command == "issue":
        from packages.ui.cli_issue import handle_issue_command

        handle_issue_command(args, session)
        return

    if args.command == "framework":
        from packages.ui.cli_framework import handle_framework_command
        handle_framework_command(args, session)
        return

    if args.command == "candidate":
        from packages.ui.cli_candidate import handle_candidate_command
        handle_candidate_command(args, session)
        return

    if args.command == "ai":
        from packages.ui.cli_ai import handle_ai_command
        handle_ai_command(args, session)
        return

    if args.command == "import":
        from packages.ui.cli_import import handle_import_command
        print(handle_import_command(args, session))
        return

    if args.command == "writing":
        from packages.ui.cli_writing import handle_writing_command
        handle_writing_command(args, session)
        return

    if args.command == "secret":
        from packages.ui.cli_secrets import handle_secret
        handle_secret(args, session)
        return

    if args.command == "clue":
        from packages.ui.cli_secrets import handle_clue
        handle_clue(args, session)
    if args.command == "faction":
        from packages.ui.cli_faction import handle_faction
        handle_faction(args, session)
        return

    if args.command == "front":
        from packages.ui.cli_faction import handle_front
        handle_front(args, session)
        return

        return

    if args.command == "campaign":
        from packages.ui.cli_campaign import handle_campaign
        handle_campaign(args, session)
        return

    print(f"error: Unknown command '{args.command}'", file=sys.stderr)
    sys.exit(1)
