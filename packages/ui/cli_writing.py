"""CLI writing commands — create, show, list, edit, archive, tree, link, coverage (B19-T04)."""

from __future__ import annotations

import argparse, json, sys
from pathlib import Path
from typing import Any

from packages.application.writing_service import WritingService
from packages.domain.result import Error
from packages.domain.writing_models import WritingUnitType, RevisionState
from packages.ui.cli import _bootstrap_services, require_project_path


def _get_svc(project_path):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    ws = WritingService(ps, entity_service=es, source_service=ss)
    return ps, ws, es, ss, hs


def register_writing_commands(subparsers: Any) -> None:
    wp = subparsers.add_parser("writing", help="Writing commands")
    ws = wp.add_subparsers(dest="writing_command", required=True)

    p = ws.add_parser("create", help="Create writing unit")
    p.add_argument("name")
    p.add_argument("--type", dest="unit_type", required=True)
    p.add_argument("--content", default="")
    p.add_argument("--summary", default="")
    p.add_argument("--parent")
    p.add_argument("--order", type=int, default=0)

    p = ws.add_parser("show", help="Show writing unit detail")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")

    p = ws.add_parser("list", help="List writing units")
    p.add_argument("--type", dest="unit_type")
    p.add_argument("--parent")
    p.add_argument("--entity")
    p.add_argument("--revision")
    p.add_argument("--tag")
    p.add_argument("--domain-id")
    p.add_argument("--layer-id")
    p.add_argument("--framework-id")
    p.add_argument("--include-archived", action="store_true")
    p.add_argument("--json", action="store_true")

    p = ws.add_parser("edit", help="Edit writing unit")
    p.add_argument("id")
    p.add_argument("--name")
    p.add_argument("--content")
    p.add_argument("--summary")
    p.add_argument("--revision")

    p = ws.add_parser("archive", help="Archive (soft delete) writing unit")
    p.add_argument("id")

    p = ws.add_parser("tree", help="Show hierarchy tree")
    p.add_argument("--root")
    p.add_argument("--json", action="store_true")

    p = ws.add_parser("link", help="Link entity to writing unit")
    p.add_argument("unit_id")
    p.add_argument("entity_id")

    p = ws.add_parser("unlink", help="Unlink entity from writing unit")
    p.add_argument("unit_id")
    p.add_argument("entity_id")

    p = ws.add_parser("linked", help="Show units where an entity appears")
    p.add_argument("entity_id")
    p.add_argument("--json", action="store_true")

    p = ws.add_parser("coverage", help="Show entity coverage summary")
    p.add_argument("--json", action="store_true")

    p = ws.add_parser("reorder", help="Change order of writing unit")
    p.add_argument("id")
    p.add_argument("new_order", type=int)

    p = ws.add_parser("reparent", help="Move unit under another parent")
    p.add_argument("id")
    p.add_argument("new_parent_id", nargs="?", default=None)
    p.add_argument("--root", action="store_true")

    p = ws.add_parser("check", help="Detect writing issues")
    p.add_argument("--json", action="store_true")

    p = ws.add_parser("expand", help="Expand with AI")
    p.add_argument("id")
    p.add_argument("--hint", default="")
    p.add_argument("--audience", default="author")

    p = ws.add_parser("summarize", help="Summarize with AI (preview)")
    p.add_argument("id")
    p.add_argument("--audience", default="author")

    p = ws.add_parser("critique", help="Critique with AI -> Candidate")
    p.add_argument("id")
    p.add_argument("--audience", default="author")

    p = ws.add_parser("rewrite", help="Rewrite with AI -> Candidate")
    p.add_argument("id")
    p.add_argument("--hint", default="")
    p.add_argument("--audience", default="author")


def handle_writing_command(args, session):
    project_path = require_project_path(args, session)
    ps, ws, es, ss, hs = _get_svc(project_path)
    cmd = args.writing_command

    if cmd == "create":
        ut = args.unit_type
        try:
            ut_enum = WritingUnitType(ut)
        except ValueError:
            print(f"error: Invalid type '{ut}'", file=sys.stderr)
            sys.exit(1)
        data = {"name": args.name, "unit_type": ut_enum,
                "content": args.content, "summary": args.summary,
                "parent_id": args.parent, "order": args.order}
        r = ws.create_unit(data)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        print(f"WritingUnit '{r.value.name}' ({r.value.id}) created [{r.value.unit_type.value}]")

    elif cmd == "show":
        r = ws.get_unit(args.id)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        u = r.value
        if args.json:
            print(json.dumps(u.to_dict(), indent=2, ensure_ascii=False))
        else:
            ents = ws.get_linked_entities(args.id)
            ent_names = ", ".join(e.name for e in ents) if ents else "(none)"
            print(f"WritingUnit: {u.name} [{u.unit_type.value}]")
            print(f"  ID:        {u.id}")
            print(f"  Parent:    {u.parent_id or '(root)'}")
            print(f"  Order:     {u.order}")
            print(f"  Revision:  {u.revision_state.value}")
            print(f"  Entities:  {ent_names}")
            print(f"  Summary:   {u.summary or '(none)'}")
            print(f"  Content:   {u.content[:300] or '(empty)'}")

    elif cmd == "list":
        filters = {}
        if hasattr(args, "unit_type") and args.unit_type:
            try:
                filters["unit_type"] = WritingUnitType(args.unit_type)
            except ValueError:
                pass
        if hasattr(args, "parent") and args.parent:
            filters["parent_id"] = args.parent
        if hasattr(args, "entity") and args.entity:
            filters["entity_id"] = args.entity
        if hasattr(args, "revision") and args.revision:
            filters["revision_state"] = args.revision
        if hasattr(args, "tag") and args.tag:
            filters["tag"] = args.tag
        if hasattr(args, "domain_id") and args.domain_id:
            filters["domain_id"] = args.domain_id
        if hasattr(args, "layer_id") and args.layer_id:
            filters["layer_id"] = args.layer_id
        if hasattr(args, "framework_id") and args.framework_id:
            filters["framework_id"] = args.framework_id
        if hasattr(args, "include_archived") and args.include_archived:
            filters["include_archived"] = True
        units = ws.list_units(filters)
        if args.json:
            data = {"total": len(units), "units": [u.to_dict() for u in units]}
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            active = sum(1 for u in units if u.revision_state != RevisionState.ARCHIVADO)
            print(f"Writing units: {len(units)} total ({active} active, {len(units)-active} archived)")
            for i, u in enumerate(units, 1):
                parent = u.parent_id[:8] if u.parent_id else "root"
                print(f"  {i:>3}. {u.id}  {u.name:<30} [{u.unit_type.value}] parent={parent}")

    elif cmd == "edit":
        data = {}
        for k in ("name", "content", "summary", "revision"):
            v = getattr(args, k, None)
            if v is not None:
                if k == "revision":
                    data["revision_state"] = v
                else:
                    data[k] = v
        r = ws.update_unit(args.id, data)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        print(f"WritingUnit '{r.value.name}' updated")

    elif cmd == "archive":
        r = ws.archive_unit(args.id)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        print(f"WritingUnit '{r.value.name}' archived (soft delete)")

    elif cmd == "tree":
        root = getattr(args, "root", None)
        if not root:
            # Use first root-level unit
            units = [u for u in ws.list_units() if u.parent_id is None]
            if not units:
                print("No writing units found.")
                return
            root = units[0].id
        tree = ws.get_tree(root)
        if args.json:
            print(json.dumps(_tree_to_dict(tree), indent=2, ensure_ascii=False))
        else:
            _print_tree(tree)

    elif cmd == "link":
        r = ws.link_entity(args.unit_id, args.entity_id)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        print(f"Linked entity '{args.entity_id}' to unit '{args.unit_id}'")

    elif cmd == "unlink":
        r = ws.unlink_entity(args.unit_id, args.entity_id)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        print(f"Unlinked entity '{args.entity_id}' from unit '{args.unit_id}'")

    elif cmd == "linked":
        units = ws.get_entity_coverage(args.entity_id)
        if args.json:
            data = {"entity_id": args.entity_id, "units": [u.to_dict() for u in units]}
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"Entity '{args.entity_id}' appears in {len(units)} writing units:")
            for u in units:
                print(f"  {u.id}  {u.name} [{u.unit_type.value}]")

    elif cmd == "coverage":
        summary = ws.get_coverage_summary()
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            pct = (summary["covered"] / summary["total"] * 100) if summary["total"] else 0
            print(f"Writing coverage:")
            print(f"  Total entities: {summary['total']}")
            print(f"  Covered: {summary['covered']} ({pct:.1f}%)")
            print(f"  Uncovered: {summary['uncovered']}")
            for etype, count in summary["by_type"].items():
                print(f"    {etype}: {count}")

    elif cmd == "reorder":
        r = ws.reorder_unit(args.id, args.new_order)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        print(f"WritingUnit '{r.value.name}' reordered to {args.new_order}")

    elif cmd == "reparent":
        new_parent = None if args.root else args.new_parent_id
        r = ws.reparent_unit(args.id, new_parent)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        dest = "root" if new_parent is None else new_parent[:8]
        print(f"WritingUnit '{r.value.name}' reparented to {dest}")

    elif cmd == "check":
        # Check for existing open issues to avoid duplicates
        proj = ps._active_project()
        existing_keys = set()
        for iss in getattr(proj, "issues", []):
            meta = getattr(iss, "metadata", {})
            if meta.get("validator") == "writing" and "writing_unit_id" in meta:
                existing_keys.add((iss.description, meta.get("writing_unit_id")))

        issues = ws.detect_writing_issues()
        new_issues = []
        for iss in issues:
            key = (iss.description, iss.metadata.get("writing_unit_id"))
            if key not in existing_keys:
                new_issues.append(iss)
                if hasattr(proj, "issues"):
                    proj.issues.append(iss)

        ps.save(Path(project_path))
        if args.json:
            data = {"total": len(new_issues), "issues": [i.to_dict() for i in new_issues]}
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            skipped = len(issues) - len(new_issues)
            print(f"Writing check: {len(new_issues)} new issues, {skipped} skipped (duplicates)")
            for iss in new_issues:
                print(f"  - {iss.description}")

    elif cmd == "expand":
        r = ws.expand_unit(args.id, args.hint)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        cand = r.value
        print(f"Candidate '{cand.title}' ({cand.id}) created [PENDIENTE, sugerencia_ia]")
        if cand.metadata:
            print(f"  ai_mode: {cand.metadata.get('ai_mode')}")

    elif cmd == "summarize":
        r = ws.summarize_unit(args.id)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        print(r.value)

    elif cmd == "critique":
        r = ws.critique_unit(args.id)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        cand = r.value
        print(f"Candidate '{cand.title}' ({cand.id}) created [PENDIENTE, sugerencia_ia]")

    elif cmd == "rewrite":
        r = ws.rewrite_unit(args.id, args.hint)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr)
            sys.exit(1)
        ps.save(Path(project_path))
        cand = r.value
        print(f"Candidate '{cand.title}' ({cand.id}) created [PENDIENTE, sugerencia_ia]")


# ── Tree helpers ────────────────────────────────────────────────────


def _tree_to_dict(node: dict) -> dict:
    unit = node["unit"]
    return {
        "unit": unit.to_dict() if hasattr(unit, "to_dict") else unit,
        "children": [_tree_to_dict(c) for c in node.get("children", [])],
    }


def _print_tree(node: dict, indent: int = 0) -> None:
    unit = node["unit"]
    prefix = "  " * indent + ("├── " if indent > 0 else "")
    print(f"{prefix}{unit.name} ({unit.unit_type.value}) [{unit.id[:8]}]")
    children = node.get("children", [])
    for child in children:
        _print_tree(child, indent + 1)


__all__ = ["register_writing_commands", "handle_writing_command"]
