"""
CLI gallery commands — ``gallery personajes``, ``localizaciones``, ..., ``por-canon``.

Organises the narrative corpus by entity type, state, source, layer, and custom type
(contrato_fases §9.2). Consumes ``QueryService.query()`` — no filter logic in CLI.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any

from packages.domain.entity import CanonState, EntityType
from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)

# ═══════════════════════════════════════════════════════════════════════
# Map: gallery subcommand name → EntityType (§9.2)
# ═══════════════════════════════════════════════════════════════════════

GALLERY_ENTITY_TYPE_MAP: dict[str, EntityType] = {
    "personajes": EntityType.PERSONAJE,
    "localizaciones": EntityType.LOCALIZACION,
    "facciones": EntityType.FACCION,
    "culturas": EntityType.CULTURA,
    "objetos": EntityType.OBJETO,
    "eventos": EntityType.EVENTO,
    "escenas": EntityType.ESCENA,
    "sesiones": EntityType.SESION,
    "secretos": EntityType.SECRETO,
    "pistas": EntityType.PISTA,
    "conflictos": EntityType.CONFLICTO,
    "reglas": EntityType.REGLA_DEL_MUNDO,
    "tecnologias": EntityType.TECNOLOGIA,
    "sistemas-magicos": EntityType.SISTEMA_MAGICO,
    "religiones": EntityType.RELIGION,
    "idiomas": EntityType.IDIOMA,
    "instituciones": EntityType.INSTITUCION,
    "criaturas": EntityType.CRIATURA,
    "tramas": EntityType.TRAMA,
    "notas": EntityType.NOTA,
}


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _add_query_flags(parser: argparse.ArgumentParser) -> None:
    """Add shared query flags (--sort, --sort-desc, --limit, --offset, --json)."""
    parser.add_argument(
        "--sort", default="name",
        choices=["name", "updated_at", "created_at", "type", "canon", "certainty", "importance"],
        help="Sort field (default: name)",
    )
    parser.add_argument(
        "--sort-desc", action="store_true", help="Sort descending",
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Max results (default: 50)",
    )
    parser.add_argument(
        "--offset", type=int, default=0, help="Pagination offset",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON instead of table",
    )


def _sort_key_for(field: str) -> str:
    """Translate CLI sort field names to QueryService sort_by values."""
    return {
        "type": "entity_type",
        "canon": "canon_state",
    }.get(field, field)


def _format_table(entities: list[Any]) -> str:
    """Format entities as a text table."""
    if not entities:
        return "(no entities)"
    lines = []
    for i, e in enumerate(entities, 1):
        name = e.name[:30]
        etype = e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type)
        canon = e.canon_state.value if hasattr(e.canon_state, "value") else str(e.canon_state)
        lines.append(f"  {i:3d}.  {e.id[:8]:8s}  {name:30s}  {etype:20s}  {canon}")
    return "\n".join(lines)


def _format_json(entities: list[Any]) -> str:
    """Format entities as JSON."""
    return json.dumps(
        [e if isinstance(e, dict) else e.to_dict() for e in entities],
        indent=2,
        ensure_ascii=False,
    )


def _run_gallery(
    args: argparse.Namespace,
    session: SessionContext,
    *,
    entity_type: EntityType | None = None,
    canon_state: CanonState | list[CanonState] | None = None,
    layer: str | None = None,
    source_id: str | None = None,
    custom_type_id: str | None = None,
    label: str = "",
) -> None:
    """Execute a gallery query and display results."""
    project_path = require_project_path(args, session)
    _, _, _, _, _, qs, _ = _bootstrap_services(project_path)

    result = qs.query(
        entity_type=entity_type,
        canon_state=canon_state,
        layer=layer,
        source_id=source_id,
        custom_type_id=custom_type_id,
        sort_by=_sort_key_for(args.sort),
        sort_desc=args.sort_desc,
        limit=args.limit,
        offset=args.offset,
    )

    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)

    entities = result.value

    if args.json:
        print(_format_json(entities))
    else:
        header = f"=== {label} ({len(entities)}) ==="
        print(header)
        print(_format_table(entities))


# ═══════════════════════════════════════════════════════════════════════
# Registration
# ═══════════════════════════════════════════════════════════════════════


def register_gallery_commands(subparsers: Any) -> None:
    """Register the ``gallery`` command and its sub-subcommands."""
    gallery_parser = subparsers.add_parser("gallery", help="Gallery / browse views")
    gallery_subs = gallery_parser.add_subparsers(dest="gallery_command", required=True)

    # ── Type galleries (20 subcommands) ──
    for subcmd, etype in GALLERY_ENTITY_TYPE_MAP.items():
        p = gallery_subs.add_parser(subcmd, help=f"Browse {etype.value} entities")
        _add_query_flags(p)

    # ── State galleries ──
    p = gallery_subs.add_parser("archivados", help="Browse archived entities")
    _add_query_flags(p)

    p = gallery_subs.add_parser("pendientes", help="Browse draft/hypothesis entities")
    _add_query_flags(p)

    # ── Source ──
    p = gallery_subs.add_parser("por-fuente", help="Browse entities by source")
    p.add_argument("source_id", help="Source ID")
    _add_query_flags(p)

    # ── Layer ──
    p = gallery_subs.add_parser("por-capa", help="Browse entities by layer")
    p.add_argument("layer", help="Layer name")
    _add_query_flags(p)

    # ── Canon state ──
    p = gallery_subs.add_parser("por-canon", help="Browse entities by canon state")
    p.add_argument("canon_state", help="Canon state (e.g. canonico, borrador)")
    _add_query_flags(p)

    # ── Custom type ──
    p = gallery_subs.add_parser("custom", help="Browse entities by custom type")
    p.add_argument("custom_type_id", help="Custom entity type ID")
    _add_query_flags(p)


# ═══════════════════════════════════════════════════════════════════════
# Handler
# ═══════════════════════════════════════════════════════════════════════


def handle_gallery_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch to the correct gallery subcommand."""
    cmd = args.gallery_command

    # Type galleries
    if cmd in GALLERY_ENTITY_TYPE_MAP:
        etype = GALLERY_ENTITY_TYPE_MAP[cmd]
        _run_gallery(args, session, entity_type=etype, label=str(etype.value))
        return

    # State galleries
    if cmd == "archivados":
        _run_gallery(args, session, canon_state=CanonState.ARCHIVADO, label="archivados")
        return

    if cmd == "pendientes":
        _run_gallery(
            args, session,
            canon_state=[CanonState.BORRADOR, CanonState.HIPOTESIS],
            label="pendientes",
        )
        return

    # Special filters
    if cmd == "por-fuente":
        _run_gallery(args, session, source_id=args.source_id, label=f"source={args.source_id}")
        return

    if cmd == "por-capa":
        _run_gallery(args, session, layer=args.layer, label=f"layer={args.layer}")
        return

    if cmd == "por-canon":
        try:
            cs = CanonState(args.canon_state)
        except ValueError:
            print(f"error: Invalid canon state '{args.canon_state}'", file=sys.stderr)
            sys.exit(1)
        _run_gallery(args, session, canon_state=cs, label=str(cs.value))
        return

    if cmd == "custom":
        _run_gallery(args, session, custom_type_id=args.custom_type_id,
                      label=f"custom={args.custom_type_id}")
        return

    print(f"error: Unknown gallery command '{cmd}'", file=sys.stderr)
    sys.exit(1)
