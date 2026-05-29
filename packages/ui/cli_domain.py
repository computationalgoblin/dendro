"""
CLI domain commands — ``domain list``, ``domain show`` (B10-T04).

Registered by :func:`register_domain_commands`.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)
from packages.ui.cli_entity import _entity_list_row


def register_domain_commands(subparsers: Any) -> None:
    """Register the ``domain`` subcommand under *subparsers*."""
    domain_parser = subparsers.add_parser("domain", help="Domain commands")
    domain_subs = domain_parser.add_subparsers(dest="domain_command", required=True)

    # domain list
    domain_subs.add_parser("list", help="List available narrative domains")

    # domain show <id>
    p_show = domain_subs.add_parser("show", help="Show domain details")
    p_show.add_argument("domain", help="Domain value (mundo, historia, campaña, compartido, sin_asignar)")


def handle_domain_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch to the correct domain subcommand handler."""
    cmd = args.domain_command
    if cmd == "list":
        _cmd_domain_list(args, session)
    elif cmd == "show":
        _cmd_domain_show(args, session)
    else:
        print(f"error: Unknown domain command '{cmd}'", file=sys.stderr)
        sys.exit(1)


def _cmd_domain_list(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    domains = ps.active_project.domains
    print(f"Domains ({len(domains)}):")
    for d in domains:
        count = len(es.get_by_domain(d).value if isinstance(es.get_by_domain(d), __import__('packages.domain.result', fromlist=['Ok']).Ok) else [])
        # Simpler: count entities with this domain
        all_entities = es.list_all()
        if isinstance(all_entities, Error):
            count = 0
        else:
            count = sum(1 for e in all_entities.value if d in e.domain_ids)
        print(f"  {d:20s}  ({count} entities)")


def _cmd_domain_show(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)

    domain = args.domain
    if domain not in ps.active_project.domains:
        print(f"error: Invalid domain '{domain}'. Valid: {', '.join(ps.active_project.domains)}", file=sys.stderr)
        sys.exit(1)

    result = es.get_by_domain(domain)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    entities = result.value
    print(f"Domain: {domain}")
    print(f"Entities ({len(entities)}):")
    if not entities:
        print("  (none)")
    for i, e in enumerate(entities, 1):
        print(_entity_list_row(e, index=i))
