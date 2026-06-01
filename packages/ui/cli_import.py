"""CLI import commands — import, basket, review, partial (B17-T04)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packages.application.import_service import ImportService
from packages.domain.import_models import ImportFormat
from packages.domain.result import Error, is_ok, unwrap
from packages.ui.cli import (
    _bootstrap_services,
    resolve_project_path,
)


def _import_service(project_path: Path) -> ImportService:
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    return ImportService(
        project_service=ps,
        candidate_service=None,
        source_service=ss,
    )


def _format_flag(args: argparse.Namespace) -> ImportFormat:
    mapping = {
        "txt": ImportFormat.TEXT_PLAIN,
        "pdf": ImportFormat.PDF,
    }
    return mapping.get(args.format, ImportFormat.TEXT_PLAIN)


# ── register ────────────────────────────────────────────────────────────


def register_import_commands(sub: argparse._SubParsersAction) -> None:
    imp = sub.add_parser("import", help="Import documents")
    imp_subs = imp.add_subparsers(dest="import_action")

    # import document
    doc = imp_subs.add_parser("document", help="Import a document file")
    doc.add_argument("file", help="Path to the document file")
    doc.add_argument("--format", choices=["txt", "pdf"], default="txt",
                     help="Document format (txt=text_plain, pdf=PDF)")

    # import basket
    basket = imp_subs.add_parser("basket", help="Manage import baskets")
    basket_subs = basket.add_subparsers(dest="basket_action")

    blist = basket_subs.add_parser("list", help="List import baskets")
    blist.add_argument("--json", action="store_true", help="JSON output")

    bshow = basket_subs.add_parser("show", help="Show basket details")
    bshow.add_argument("basket_id", help="Basket ID")
    bshow.add_argument("--json", action="store_true", help="JSON output")

    # import review
    review = imp_subs.add_parser("review", help="Review import candidates")
    review_subs = review.add_subparsers(dest="review_action")

    accept = review_subs.add_parser("accept", help="Accept import candidate")
    accept.add_argument("basket_id", help="Basket ID")
    accept.add_argument("cand_id", help="Import Candidate ID")

    reject = review_subs.add_parser("reject", help="Reject import candidate")
    reject.add_argument("basket_id", help="Basket ID")
    reject.add_argument("cand_id", help="Import Candidate ID")

    edit = review_subs.add_parser("edit", help="Edit import candidate")
    edit.add_argument("basket_id"); edit.add_argument("cand_id")
    edit.add_argument("--name"); edit.add_argument("--desc"); edit.add_argument("--type")

    merge = review_subs.add_parser("merge", help="Merge import candidates")
    merge.add_argument("basket_id"); merge.add_argument("cand_id1")
    merge.add_argument("--cand-id2", dest="cand_id2", required=True)
    merge.add_argument("--cand-ids", nargs="+", help="Additional candidate IDs")

    # import partial
    partial = imp_subs.add_parser("partial", help="Filtered view of basket")
    partial.add_argument("basket_id", help="Basket ID")
    partial.add_argument("--characters", action="store_true", help="Characters only")
    partial.add_argument("--locations", action="store_true", help="Locations only")
    partial.add_argument("--factions", action="store_true", help="Factions only")


# ── handle ──────────────────────────────────────────────────────────────


def handle_import_command(args: argparse.Namespace, session_ctx=None) -> str:
    project_path = resolve_project_path(args, session_ctx)
    if project_path is None:
        return "Error: no active project. Use: project open <path>"
    action = getattr(args, "import_action", None)

    if action == "document":
        return _cmd_import_document(args, session_ctx, project_path)
    elif action == "basket":
        return _cmd_basket(args, session_ctx, project_path)
    elif action == "review":
        return _cmd_review(args, session_ctx, project_path)
    elif action == "partial":
        return _cmd_partial(args, session_ctx, project_path)
    else:
        return "Error: unknown import subcommand. Use: import document|basket|review|partial"


def _cmd_import_document(args: argparse.Namespace, session_ctx, project_path: Path) -> str:
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    svc = ImportService(project_service=ps, candidate_service=None, source_service=ss)
    fmt = _format_flag(args)
    result = svc.import_document(args.file, fmt)
    if isinstance(result, Error):
        return f"Import failed: {result.error}"
    basket = result.value
    # Save after successful import
    save_result = ps.save(project_path)
    if isinstance(save_result, Error):
        return f"Import succeeded but save failed: {save_result.error}"
    return (
        f"Document imported successfully.\n"
        f"  Basket ID: {basket.id}\n"
        f"  Source ID: {basket.source_id}\n"
        f"  Segments: {len(basket.segments)}\n"
        f"  Candidates: {len(basket.import_candidates)}\n"
        f"\n"
        f"Next: import basket show {basket.id}"
    )


def _cmd_basket(args: argparse.Namespace, session_ctx, project_path: Path) -> str:
    svc = _import_service(project_path)
    b_action = getattr(args, "basket_action", None)

    if b_action == "list":
        result = svc.list_baskets()
        if isinstance(result, Error):
            return f"Error: {result.error}"
        baskets = result.value
        if getattr(args, "json", False):
            data = [
                {
                    "id": b.id,
                    "source_id": b.source_id,
                    "candidates_count": len(b.import_candidates),
                    "review_state": b.review_state,
                    "created_at": b.created_at,
                    "updated_at": b.updated_at,
                }
                for b in baskets
            ]
            return json.dumps(data, indent=2)
        if not baskets:
            return "No import baskets."
        lines = ["Import Baskets:"]
        for b in baskets:
            lines.append(
                f"  {b.id} | source={b.source_id[:8]} | "
                f"candidates={len(b.import_candidates)} | "
                f"state={b.review_state}"
            )
        return "\n".join(lines)

    elif b_action == "show":
        result = svc.get_basket(args.basket_id)
        if isinstance(result, Error):
            return f"Error: {result.error}"
        basket = result.value
        if getattr(args, "json", False):
            return json.dumps(basket.to_dict(), indent=2)
        lines = [
            f"Import Basket: {basket.id}",
            f"  Source: {basket.source_id}",
            f"  Segments: {len(basket.segments)}",
            f"  Candidates: {len(basket.import_candidates)}",
            f"  State: {basket.review_state}",
            "",
        ]
        for i, cand in enumerate(basket.import_candidates, 1):
            ct = cand.candidate_type.upper()
            name = cand.proposed_data.get("name", cand.proposed_data.get("source_name", "?"))
            conf = cand.confidence
            lines.append(
                f"  [{i}] {cand.id}  {ct}  \"{name}\" (conf={conf:.1f})"
                f" — segment {cand.segment_id[:8]}"
            )
        return "\n".join(lines)

    return "Error: unknown basket action. Use: import basket list|show"


def _cmd_review(args: argparse.Namespace, session_ctx, project_path: Path) -> str:
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    svc = ImportService(project_service=ps, candidate_service=None, source_service=ss)
    r_action = getattr(args, "review_action", None)

    if r_action == "accept":
        result = svc.accept_import_candidate(args.basket_id, args.cand_id)
        if isinstance(result, Error):
            return f"Accept failed: {result.error}"
        candidate = result.value
        # Save
        ps.save(project_path)
        return (
            "Import candidate accepted into candidate inbox:\n"
            f"  ImportCandidate: {args.cand_id}\n"
            f"  Candidate:       {candidate.id}\n"
            f"  State:           PENDIENTE\n"
            f"\n"
            f"Next: candidate show {candidate.id}\n"
            f"      candidate accept {candidate.id}   (to promote to canon)"
        )

    elif r_action == "reject":
        result = svc.reject_import_candidate(args.basket_id, args.cand_id)
        if isinstance(result, Error):
            return f"Reject failed: {result.error}"
        # Save
        ps.save(project_path)
        return f"Import candidate {args.cand_id[:8]} rejected."

    elif r_action == "edit":
        return _cmd_edit(args, session_ctx, project_path)

    elif r_action == "merge":
        return _cmd_merge(args, session_ctx, project_path)

    return "Error: unknown review action. Use: import review accept|reject|edit|merge"



def _cmd_edit(args, session_ctx, project_path):
    svc = _import_service(project_path)
    data = {}
    if getattr(args, "name", None): data["name"] = args.name
    if getattr(args, "desc", None): data["desc"] = args.desc
    if getattr(args, "type", None): data["type"] = args.type
    result = svc.edit_import_candidate(args.basket_id, args.cand_id, data)
    if isinstance(result, Error): return f"Error: {result.error}"
    from packages.application.project_service import ProjectService
    ps = ProjectService(store=svc._proj()._store if hasattr(svc._proj(), "_store") else None)
    try: ps.save(project_path)
    except: pass
    return f"Import candidate {args.cand_id[:8]} edited."

def _cmd_merge(args, session_ctx, project_path):
    svc = _import_service(project_path)
    cand_ids = [args.cand_id1, args.cand_id2]
    if hasattr(args, "cand_ids") and args.cand_ids:
        cand_ids = args.cand_ids
    result = svc.merge_import_candidates(args.basket_id, cand_ids)
    if isinstance(result, Error): return f"Error: {result.error}"
    b = result.value
    return f"Merged {len(cand_ids)} candidates into {b.import_candidates[-1].id} (state=FUSIONADO)."

def _cmd_partial(args: argparse.Namespace, session_ctx, project_path: Path) -> str:
    svc = _import_service(project_path)
    filters: dict = {}
    if getattr(args, "characters", False):
        filters["characters_only"] = True
    if getattr(args, "locations", False):
        filters["locations_only"] = True
    if getattr(args, "factions", False):
        filters["factions_only"] = True

    result = svc.partial_import(args.basket_id, filters)
    if isinstance(result, Error):
        return f"Error: {result.error}"
    basket = result.value
    lines = [
        f"Filtered view of basket {basket.id}:",
        f"  Candidates: {len(basket.import_candidates)} (filtered)",
    ]
    for i, cand in enumerate(basket.import_candidates, 1):
        ct = cand.candidate_type.upper()
        name = cand.proposed_data.get("name", "?")
        lines.append(f"  [{i}] {cand.id}  {ct}  \"{name}\"")
    return "\n".join(lines)
