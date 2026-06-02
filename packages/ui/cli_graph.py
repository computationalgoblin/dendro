"""
CLI graph commands — summary, export, entity, path, node, edge,
entity-create, relation-create, relation-edit, view (B11-T03 + B11-T06).
"""

from __future__ import annotations

import argparse
import json
import subprocess as sp
import sys
from pathlib import Path
from typing import Any

from packages.application.graph_models import GraphFilters, SavedGraphView
from packages.application.graph_service import GraphService
from packages.domain.entity import EntityType
from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_graph_commands(subparsers: Any) -> None:
    gp = subparsers.add_parser("graph", help="Graph commands")
    gs = gp.add_subparsers(dest="graph_command", required=True)

    # --- B11-T03: summary ---
    p_s = gs.add_parser("summary", help="Show graph stats")
    _add_filter_flags(p_s)

    # --- B11-T03: export ---
    p_e = gs.add_parser("export", help="Export graph view")
    p_e.add_argument("--json", action="store_true", help="Output as JSON")
    p_e.add_argument("--overlay", action="append", default=[], help="Read-only overlay (repeatable)")
    _add_filter_flags(p_e)

    # --- B28-T04: compare derived views ---
    p_cmp = gs.add_parser("compare", help="Compare two derived graph views")
    p_cmp.add_argument("--view-a", required=True, help="Saved view A name")
    p_cmp.add_argument("--view-b", required=True, help="Saved view B name")
    p_cmp.add_argument("--json", action="store_true", help="Output as JSON")

    # --- B11-T03: entity <id> ---
    p_ent = gs.add_parser("entity", help="Entity neighborhood")
    p_ent.add_argument("id", nargs="?", default=None, help="Entity ID")
    p_ent.add_argument("--depth", type=int, default=1)
    _add_filter_flags(p_ent)

    # --- B11-T03: path ---
    p_path = gs.add_parser("path", help="Find path between entities")
    p_path.add_argument("source_id", help="Source entity ID")
    p_path.add_argument("target_id", help="Target entity ID")
    p_path.add_argument("--max-depth", type=int, default=5)
    _add_filter_flags(p_path)

    # --- B11-T06: node show/create ---
    p_node = gs.add_parser("node", help="Node commands")
    node_subs = p_node.add_subparsers(dest="node_command", required=True)
    p_ns = node_subs.add_parser("show", help="Show entity ficha from graph")
    p_ns.add_argument("id", help="Entity ID")
    p_nc = node_subs.add_parser("create", help="Create entity from graph")
    p_nc.add_argument("name", help="Entity name")
    p_nc.add_argument("--type", "--etype", required=True, dest="create_type",
                      help="Entity type (e.g., personaje, objeto)")
    p_nc.add_argument("--brief", default="", help="Brief description")
    p_nc.add_argument("--extended", default="", help="Extended description")
    p_nc.add_argument("--domain-id", default=None, help="Domain ID")
    p_nc.add_argument("--layer-id", default=None, help="Layer ID")

    # --- B11-T06: edge show ---
    p_edge = gs.add_parser("edge", help="Edge commands")
    edge_subs = p_edge.add_subparsers(dest="edge_command", required=True)
    p_es = edge_subs.add_parser("show", help="Show relation ficha from graph")
    p_es.add_argument("id", help="Relation ID")

    # --- B11-T06: relation create/edit ---
    p_rel = gs.add_parser("relation", help="Relation commands from graph")
    rel_subs = p_rel.add_subparsers(dest="relation_command", required=True)
    p_rc = rel_subs.add_parser("create", help="Create relation from graph")
    p_rc.add_argument("source_id", help="Source entity ID")
    p_rc.add_argument("target_id", help="Target entity ID")
    p_rc.add_argument("--type", required=True, help="Relation type")
    p_rc.add_argument("--desc", default="", help="Description")
    p_re = rel_subs.add_parser("edit", help="Edit relation from graph")
    p_re.add_argument("id", help="Relation ID")
    p_re.add_argument("--desc", default=None, help="New description")

    # --- B11-T06: view save/show/list/delete ---
    p_view = gs.add_parser("view", help="View presets")
    view_subs = p_view.add_subparsers(dest="view_command", required=True)
    p_vs = view_subs.add_parser("save", help="Save view preset")
    p_vs.add_argument("name", help="Preset name")
    p_vs.add_argument("--force", action="store_true", help="Overwrite existing")
    p_vs.add_argument("--description", default="", help="Human description")
    p_vs.add_argument("--overlay", action="append", default=[], help="Read-only overlay (repeatable)")
    _add_filter_flags(p_vs)
    p_vshow = view_subs.add_parser("show", help="Show preset")
    p_vshow.add_argument("name", help="Preset name")
    p_vlist = view_subs.add_parser("list", help="List presets")
    p_vlist.add_argument("--json", action="store_true", help="Output as JSON")
    p_vd = view_subs.add_parser("delete", help="Delete preset")
    p_vd.add_argument("name", help="Preset name")


def _add_filter_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--type", default=None, help="Filter by entity type")
    parser.add_argument("--custom-type-id", default=None)
    parser.add_argument("--canon", default=None, help="Filter by canon state")
    parser.add_argument("--visibility", default=None)
    parser.add_argument("--domain-id", default=None)
    parser.add_argument("--layer-id", default=None)
    parser.add_argument("--relation-type", default=None)
    parser.add_argument("--view-type", default="global", help="Specialized view type")
    parser.add_argument("--audience", default="author", choices=["author", "gm", "player", "public"])
    parser.add_argument("--campaign-id", default=None)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--include-archived", action="store_true")
    parser.add_argument("--max-nodes", type=int, default=200)
    parser.add_argument("--view", default=None, help="Load preset by name")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_filters(args: argparse.Namespace) -> GraphFilters:
    view_name = getattr(args, "view", None)
    if view_name:
        return _load_preset(view_name, args)
    depth = getattr(args, "depth", None)
    max_depth = getattr(args, "max_depth", None)
    max_nodes = getattr(args, "max_nodes", 200)
    if depth is not None and depth < 1:
        print("error: --depth must be >= 1", file=sys.stderr)
        sys.exit(1)
    if max_depth is not None and max_depth < 1:
        print("error: --max-depth must be >= 1", file=sys.stderr)
        sys.exit(1)
    if max_nodes < 1:
        print("error: --max-nodes must be >= 1", file=sys.stderr)
        sys.exit(1)
    return GraphFilters(
        entity_type=args.type,
        custom_type_id=getattr(args, "custom_type_id", None),
        canon_state=args.canon,
        visibility_state=getattr(args, "visibility", None),
        domain_id=getattr(args, "domain_id", None),
        layer_id=getattr(args, "layer_id", None),
        relation_type=getattr(args, "relation_type", None),
        include_archived=getattr(args, "include_archived", False),
        max_nodes=max_nodes,
        view_type=getattr(args, "view_type", "global"),
        overlays=list(getattr(args, "overlay", []) or []),
        audience=getattr(args, "audience", "author"),
        campaign_id=getattr(args, "campaign_id", None),
        session_id=getattr(args, "session_id", None),
    )


def _load_preset(name: str, args: argparse.Namespace) -> GraphFilters:
    project_path = require_project_path(args, SessionContext())
    ps, *_ = _bootstrap_services(project_path)
    proj = ps.active_project
    if proj is None:
        print("error: No active project", file=sys.stderr)
        sys.exit(1)
    preset = _find_saved_view(proj, name)
    if preset is None:
        print(f"error: View preset '{name}' not found", file=sys.stderr)
        sys.exit(1)
    return SavedGraphView.from_dict(preset).filters


def _find_saved_view(project: Any, name: str) -> dict[str, Any] | None:
    """Find a v19 saved graph view by name/id, with legacy metadata fallback."""
    for raw in getattr(project, "saved_graph_views", []):
        if not isinstance(raw, dict):
            continue
        if raw.get("name") == name or raw.get("id") == name:
            return raw
    legacy = getattr(project, "metadata", {}).get("graph_views", {})
    if isinstance(legacy, dict) and name in legacy:
        return {"name": name, "filters": legacy[name]}
    return None


def _saved_views(project: Any) -> list[dict[str, Any]]:
    """Return v19 saved graph views plus legacy presets for compatibility."""
    views = [v for v in getattr(project, "saved_graph_views", []) if isinstance(v, dict)]
    legacy = getattr(project, "metadata", {}).get("graph_views", {})
    if isinstance(legacy, dict):
        existing = {v.get("name") for v in views}
        for name, filters in legacy.items():
            if name not in existing:
                views.append({"name": name, "filters": filters})
    return views


def _build_graph_service(project_path):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    gs = GraphService(query_service=qs, relation_service=rs, entity_service=es)
    return ps, es, rs, gs


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def handle_graph_command(args: argparse.Namespace, session: SessionContext) -> None:
    project_path = require_project_path(args, session)
    cmd = args.graph_command
    if cmd == "summary":
        _cmd_summary(args, project_path)
    elif cmd == "export":
        _cmd_export(args, project_path)
    elif cmd == "compare":
        _cmd_compare(args, project_path)
    elif cmd == "entity":
        _cmd_entity(args, project_path, session)
    elif cmd == "path":
        _cmd_path(args, project_path)
    elif cmd == "node":
        _cmd_node(args, project_path)
    elif cmd == "edge":
        _cmd_edge(args, project_path)
    elif cmd == "relation":
        _cmd_relation(args, project_path)
    elif cmd == "view":
        _cmd_view(args, project_path)
    else:
        print(f"error: Unknown graph command '{cmd}'", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# B11-T03 handlers
# ---------------------------------------------------------------------------

def _cmd_summary(args, project_path):
    ps, es, rs, gs = _build_graph_service(project_path)
    filters = _build_filters(args)
    result = gs.get_graph_stats(filters)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    s = result.value
    print(f"Graph: {s.visible_nodes} nodes ({s.hidden_nodes} hidden), "
          f"{s.visible_edges} edges ({s.hidden_edges} hidden)")
    print(f"  Active:   {s.active_nodes} nodes, {s.active_edges} edges")
    print(f"  Archived: {s.archived_nodes} nodes, {s.archived_edges} edges")
    print(f"  Broken:   {s.broken_edges} edges")


def _cmd_export(args, project_path):
    ps, es, rs, gs = _build_graph_service(project_path)
    filters = _build_filters(args)
    result = gs.build_specialized_graph(filters)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    view = result.value
    if args.json:
        print(json.dumps(view.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Graph: {len(view.nodes)} nodes, {len(view.edges)} edges "
              f"({view.hidden_node_count} hidden nodes, "
              f"{view.hidden_edge_count} hidden edges)")
        for n in view.nodes[:20]:
            arch = " [ARCHIVED]" if n.is_archived else ""
            print(f"  [{n.entity_type}] {n.label} ({n.id[:8]}){arch}")
        if len(view.nodes) > 20:
            print(f"  ... and {len(view.nodes) - 20} more nodes")


def _cmd_compare(args, project_path):
    ps, es, rs, gs = _build_graph_service(project_path)
    proj = ps.active_project
    if proj is None:
        print("error: No active project", file=sys.stderr)
        sys.exit(1)
    raw_a = _find_saved_view(proj, args.view_a)
    raw_b = _find_saved_view(proj, args.view_b)
    if raw_a is None:
        print(f"error: View preset '{args.view_a}' not found", file=sys.stderr)
        sys.exit(1)
    if raw_b is None:
        print(f"error: View preset '{args.view_b}' not found", file=sys.stderr)
        sys.exit(1)
    saved_a = SavedGraphView.from_dict(raw_a)
    saved_b = SavedGraphView.from_dict(raw_b)
    view_a = gs.build_specialized_graph(saved_a.filters)
    view_b = gs.build_specialized_graph(saved_b.filters)
    if isinstance(view_a, Error):
        print(f"error: {view_a.error}", file=sys.stderr)
        sys.exit(1)
    if isinstance(view_b, Error):
        print(f"error: {view_b.error}", file=sys.stderr)
        sys.exit(1)
    result = gs.compare_graph_views(view_a.value, view_b.value, saved_a.name, saved_b.name)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    comparison = result.value
    if getattr(args, "json", False):
        print(json.dumps(comparison.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Graph comparison: {saved_a.name} -> {saved_b.name}")
    print(f"  Added nodes: {len(comparison.added_nodes)}")
    print(f"  Removed nodes: {len(comparison.removed_nodes)}")
    print(f"  Changed nodes: {len(comparison.changed_nodes)}")
    print(f"  Added edges: {len(comparison.added_edges)}")
    print(f"  Removed edges: {len(comparison.removed_edges)}")
    print(f"  Changed edges: {len(comparison.changed_edges)}")


def _cmd_entity(args, project_path, session):
    # B11-T03: entity <id>
    entity_id = args.id
    if not entity_id:
        print("error: graph entity requires <id>", file=sys.stderr)
        sys.exit(1)
    ps, es, rs, gs = _build_graph_service(project_path)
    filters = _build_filters(args)
    result = gs.build_entity_neighborhood(entity_id, depth=args.depth,
                                           filters=filters)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    view = result.value
    print(f"Entity: {view.nodes[0].label if view.nodes else entity_id} "
          f"({view.nodes[0].entity_type if view.nodes else '?'})")
    print(f"  Neighbors (depth {args.depth}): "
          f"{len(view.nodes) - 1} nodes, {len(view.edges)} edges")
    for e in view.edges:
        direction = "->" if e.source_id == entity_id else "<-"
        other_id = e.target_id if e.source_id == entity_id else e.source_id
        other_node = next((n for n in view.nodes if n.id == other_id), None)
        other_label = other_node.label if other_node else other_id[:8]
        print(f"    {direction} {e.relation_type}: {other_label} "
              f"({other_node.entity_type if other_node else '?'})")
    print()
    print(f"Use 'graph node show {entity_id}' for full entity ficha.")


def _create_entity(args, project_path) -> None:
    ps, es, rs, _ = _build_graph_service(project_path)
    proj = ps.active_project
    if proj is None:
        print("error: No active project", file=sys.stderr)
        sys.exit(1)
    # Validate domain/layer before creation
    domain_id = getattr(args, "domain_id", None)
    layer_id = getattr(args, "layer_id", None)
    if domain_id and domain_id not in proj.domains:
        print(f"error: Domain '{domain_id}' not found", file=sys.stderr)
        sys.exit(1)
    if layer_id:
        found = any(wl.id == layer_id for wl in proj.world_layers)
        if not found:
            print(f"error: Layer '{layer_id}' not found", file=sys.stderr)
            sys.exit(1)
    entity_name = args.name
    entity_type_raw = args.create_type
    if not entity_name or not entity_type_raw:
        print("error: --name and --etype are required for entity create",
              file=sys.stderr)
        sys.exit(1)
    try:
        etype = EntityType(entity_type_raw)
    except (ValueError, KeyError):
        print(f"error: Invalid entity type '{entity_type_raw}'", file=sys.stderr)
        sys.exit(1)
    data = {"name": entity_name, "entity_type": etype}
    if args.brief:
        data["brief_description"] = args.brief
    if args.extended:
        data["extended_description"] = args.extended
    if domain_id:
        data["domain_ids"] = [domain_id]
    if layer_id:
        data["layer_ids"] = [layer_id]
    result = es.create_entity(data)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    entity = result.value
    save_result = ps.save(Path(project_path))
    if isinstance(save_result, Error):
        print(f"error: Entity created but save failed: {save_result.error}",
              file=sys.stderr)
        sys.exit(1)
    print(f"Entity '{entity.name}' ({entity.id}) created")


def _cmd_path(args, project_path):
    ps, es, rs, gs = _build_graph_service(project_path)
    filters = _build_filters(args)
    result = gs.build_path_between(args.source_id, args.target_id,
                                    max_depth=args.max_depth, filters=filters)
    if isinstance(result, Error):
        print(f"error: {result.error}", file=sys.stderr)
        sys.exit(1)
    path = result.value
    if path.found:
        node_names = [n.label for n in path.nodes]
        edges_btwn = [e.relation_type for e in path.edges]
        parts = [node_names[0]]
        for i, et in enumerate(edges_btwn):
            parts.append(f"-> {et} -> {node_names[i+1]}")
        print(f"Path found (length {path.length}):")
        print("  " + " ".join(parts))
    else:
        print(f"No path found between {args.source_id[:8]} "
              f"and {args.target_id[:8]} (max depth {args.max_depth})")


# ---------------------------------------------------------------------------
# B11-T06 handlers
# ---------------------------------------------------------------------------

def _cmd_node(args, project_path):
    """graph node show <id> / graph node create <name> ..."""
    if args.node_command == "show":
        r = sp.run([sys.executable, "-m", "narrative_architect",
                     "entity", "show", args.id, "--extended"],
                    capture_output=True, text=True, cwd=project_path.parent)
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr, end="")
            sys.exit(r.returncode)
        print(r.stdout)
    elif args.node_command == "create":
        _create_entity(args, project_path)


def _cmd_edge(args, project_path):
    """graph edge show <id> — shortcut to relation show --extended."""
    if args.edge_command == "show":
        r = sp.run([sys.executable, "-m", "narrative_architect",
                     "relation", "show", args.id, "--extended"],
                    capture_output=True, text=True, cwd=project_path.parent)
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr, end="")
            sys.exit(r.returncode)
        print(r.stdout)


def _cmd_relation(args, project_path):
    ps, es, rs, _ = _build_graph_service(project_path)
    cmd = args.relation_command
    if cmd == "create":
        from packages.domain.relation import RelationType
        try:
            rtype = getattr(RelationType, args.type.upper())
        except (AttributeError, KeyError):
            print(f"error: Invalid relation type '{args.type}'", file=sys.stderr)
            sys.exit(1)
        result = rs.create_relation(
            source_id=args.source_id, target_id=args.target_id,
            relation_type=rtype,
            data={"description": args.desc} if args.desc else None,
        )
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        rel = result.value
        save_result = ps.save(Path(project_path))
        if isinstance(save_result, Error):
            print(f"error: Relation created but save failed: {save_result.error}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"Relation '{rel.id}' ({rel.relation_type.value}) created")
    elif cmd == "edit":
        if not args.desc:
            print("error: --desc is required for relation edit", file=sys.stderr)
            sys.exit(1)
        result = rs.update_relation(args.id, data={"description": args.desc})
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        save_result = ps.save(Path(project_path))
        if isinstance(save_result, Error):
            print(f"error: Relation edited but save failed: {save_result.error}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"Relation '{args.id}' updated")


def _cmd_view(args, project_path):
    ps, es, rs, _ = _build_graph_service(project_path)
    cmd = args.view_command
    proj = ps.active_project
    if proj is None:
        print("error: No active project", file=sys.stderr)
        sys.exit(1)
    if not isinstance(getattr(proj, "saved_graph_views", None), list):
        proj.saved_graph_views = []

    if cmd == "save":
        existing_index = next(
            (idx for idx, raw in enumerate(proj.saved_graph_views)
             if isinstance(raw, dict) and raw.get("name") == args.name),
            None,
        )
        if existing_index is not None and not getattr(args, "force", False):
            print(
                f"error: View '{args.name}' already exists. "
                "Use --force to overwrite.",
                file=sys.stderr,
            )
            sys.exit(1)
        filters = _build_filters(args)
        saved = SavedGraphView(
            name=args.name,
            description=getattr(args, "description", ""),
            filters=filters,
            scope=filters.normalized_scope(),
            overlays=list(getattr(args, "overlay", []) or []),
        ).to_dict()
        if existing_index is None:
            proj.saved_graph_views.append(saved)
        else:
            old = proj.saved_graph_views[existing_index]
            if isinstance(old, dict) and old.get("id"):
                saved["id"] = old["id"]
            proj.saved_graph_views[existing_index] = saved
        save_result = ps.save(Path(project_path))
        if isinstance(save_result, Error):
            print(f"error: {save_result.error}", file=sys.stderr)
            sys.exit(1)
        print(f"View '{args.name}' saved")
    elif cmd == "show":
        preset = _find_saved_view(proj, args.name)
        if preset is None:
            print(f"error: View '{args.name}' not found", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(SavedGraphView.from_dict(preset).to_dict(), indent=2, ensure_ascii=False))
    elif cmd == "list":
        views = _saved_views(proj)
        if getattr(args, "json", False):
            print(json.dumps({"views": [SavedGraphView.from_dict(v).to_dict() for v in views]}, indent=2, ensure_ascii=False))
            return
        if not views:
            print("No saved views")
            return
        for raw in sorted(views, key=lambda item: str(item.get("name", ""))):
            saved = SavedGraphView.from_dict(raw)
            filters = saved.filters
            print(f"  {saved.name}: view_type={filters.normalized_view_type().value}, "
                  f"audience={filters.audience}, "
                  f"archived={filters.include_archived}")
    elif cmd == "delete":
        index = next(
            (idx for idx, raw in enumerate(proj.saved_graph_views)
             if isinstance(raw, dict) and (raw.get("name") == args.name or raw.get("id") == args.name)),
            None,
        )
        if index is None:
            print(f"error: View '{args.name}' not found", file=sys.stderr)
            sys.exit(1)
        del proj.saved_graph_views[index]
        save_result = ps.save(Path(project_path))
        if isinstance(save_result, Error):
            print(f"error: {save_result.error}", file=sys.stderr)
            sys.exit(1)
        print(f"View '{args.name}' deleted")
