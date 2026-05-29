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
from packages.ui.cli_entity import _parse_enum

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


def _add_query_flags(parser: argparse.ArgumentParser, *, exclude: set[str] | None = None) -> None:
    """Add shared query flags (filters, sort, pagination, json).

    *exclude* is a set of flag dest names to skip (e.g. ``{\"source_id\"}`` for
    subcommands that already have a positional ``source_id`` argument).
    """
    ex = exclude or set()
    # ── filters ──
    if "canon" not in ex:
        parser.add_argument(
            "--canon", default=None, metavar="STATE",
            help="Filter by canon state (canonico, borrador, hipotesis, archivado, etc.)",
        )
    if "visibility" not in ex:
        parser.add_argument(
            "--visibility", default=None, metavar="STATE",
            help="Filter by visibility state (visible_usuario, visible_dm, privado_dm, etc.)",
        )
    if "domain" not in ex:
        parser.add_argument("--domain", default=None, help="Filter by domain")
    if "tag" not in ex:
        parser.add_argument("--tag", default=None, help="Filter by tag")
    if "layer" not in ex:
        parser.add_argument("--layer", default=None, help="Filter by layer")
    if "custom_type_id" not in ex:
        parser.add_argument("--custom-type-id", default=None, help="Filter by custom entity type ID")
    if "source_id" not in ex:
        parser.add_argument("--source-id", default=None, help="Filter by source ID")
    if "domain_id" not in ex:
        parser.add_argument("--domain-id", default=None,
                            help="Filter by narrative domain (mundo/historia/campaña/compartido/sin_asignar)")
    if "layer_id" not in ex:
        parser.add_argument("--layer-id", default=None, help="Filter by world layer ID")
    # ── sort & pagination ──
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
    """Execute a gallery query and display results.

    Explicit keyword args (derived from subcommand selection) take precedence
    over CLI flags.  CLI flags (--canon, --visibility, --domain, --tag,
    --layer, --custom-type-id, --source-id) are used for compound filtering
    on type galleries and as fallbacks.
    """
    project_path = require_project_path(args, session)
    _, _, _, _, _, qs, _ = _bootstrap_services(project_path)

    # ── Resolve enum filters from args ──
    visibility: Any = None
    if getattr(args, "visibility", None):
        from packages.domain.entity import VisibilityState
        visibility = _parse_enum(args.visibility, VisibilityState, "visibility state")

    canon: Any = canon_state  # explicit takes precedence
    if canon is None and getattr(args, "canon", None):
        canon = _parse_enum(args.canon, CanonState, "canon state")

    # Layer / source / custom-type: explicit overrides args
    ly = layer if layer is not None else getattr(args, "layer", None)
    sid = source_id if source_id is not None else getattr(args, "source_id", None)
    cid = custom_type_id if custom_type_id is not None else getattr(args, "custom_type_id", None)

    domain = getattr(args, "domain", None)
    tag = getattr(args, "tag", None)

    result = qs.query(
        entity_type=entity_type,
        canon_state=canon,
        visibility_state=visibility,
        tag=tag,
        domain=domain,
        layer=ly,
        custom_type_id=cid,
        source_id=sid,
        domain_id=getattr(args, "domain_id", None),
        layer_id=getattr(args, "layer_id", None),
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
    _add_query_flags(p, exclude={"source_id"})

    # ── Layer ──
    p = gallery_subs.add_parser("por-capa", help="Browse entities by layer")
    p.add_argument("layer", help="Layer name")
    _add_query_flags(p, exclude={"layer"})

    # ── Canon state ──
    p = gallery_subs.add_parser("por-canon", help="Browse entities by canon state")
    p.add_argument("canon_state", help="Canon state (e.g. canonico, borrador)")
    _add_query_flags(p, exclude={"canon"})

    # ── Custom type ──
    p = gallery_subs.add_parser("custom", help="Browse entities by custom type")
    p.add_argument("custom_type_id", help="Custom entity type ID")
    _add_query_flags(p, exclude={"custom_type_id"})


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
