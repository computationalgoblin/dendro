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

from packages.application.graph_models import GraphFilters
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
    _add_filter_flags(p_e)

    # --- B11-T03: entity <id> + B11-T06: entity create ---
    p_ent = gs.add_parser("entity", help="Entity neighborhood or create")
    p_ent.add_argument("id_or_create", nargs="?", default=None,
                       help="Entity ID, or 'create' for interactive create")
    p_ent.add_argument("--depth", type=int, default=1)
    _add_filter_flags(p_ent)
    # entity create extra args (filters already added by _add_filter_flags)
    p_ent.add_argument("--name", default=None, help="Entity name (for create)")
    p_ent.add_argument("--etype", default=None, dest="create_type",
                       help="Entity type (for create)")
    p_ent.add_argument("--brief", default="")
    p_ent.add_argument("--extended", default="")
    p_ent.add_argument("--domain", default=None)

    # --- B11-T03: path ---
    p_path = gs.add_parser("path", help="Find path between entities")
    p_path.add_argument("source_id", help="Source entity ID")
    p_path.add_argument("target_id", help="Target entity ID")
    p_path.add_argument("--max-depth", type=int, default=5)
    _add_filter_flags(p_path)

    # --- B11-T06: node show ---
    p_node = gs.add_parser("node", help="Node commands")
    node_subs = p_node.add_subparsers(dest="node_command", required=True)
    p_ns = node_subs.add_parser("show", help="Show entity ficha from graph")
    p_ns.add_argument("id", help="Entity ID")

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
    _add_filter_flags(p_vs)
    p_vshow = view_subs.add_parser("show", help="Show preset")
    p_vshow.add_argument("name", help="Preset name")
    view_subs.add_parser("list", help="List presets")
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
    )


def _load_preset(name: str, args: argparse.Namespace) -> GraphFilters:
    project_path = require_project_path(args, SessionContext())
    ps, *_ = _bootstrap_services(project_path)
    proj = ps.active_project
    if proj is None:
        print("error: No active project", file=sys.stderr)
        sys.exit(1)
    views = proj.metadata.get("graph_views", {})
    preset = views.get(name)
    if not preset:
        print(f"error: View preset '{name}' not found", file=sys.stderr)
        sys.exit(1)
    return GraphFilters(
        entity_type=preset.get("entity_type"),
        custom_type_id=preset.get("custom_type_id"),
        canon_state=preset.get("canon_state"),
        visibility_state=preset.get("visibility_state"),
        domain_id=preset.get("domain_id"),
        layer_id=preset.get("layer_id"),
        relation_type=preset.get("relation_type"),
        custom_relation_type_id=preset.get("custom_relation_type_id"),
        include_archived=preset.get("include_archived", False),
        include_broken=preset.get("include_broken", True),
        max_nodes=preset.get("max_nodes", 200),
        max_edges=preset.get("max_edges", 500),
    )


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
    result = gs.build_graph(filters)
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


def _cmd_entity(args, project_path, session):
    # B11-T06: entity create
    if args.id_or_create == "create":
        _create_entity(args, project_path)
        return
    # B11-T03: entity <id> (legacy)
    entity_id = args.id_or_create
    if not entity_id:
        print("error: graph entity requires <id> or 'create' "
              "(with --name and --etype)", file=sys.stderr)
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
    if args.domain:
        data["domain"] = args.domain
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
    """graph node show <id> — shortcut to entity show --extended."""
    if args.node_command == "show":
        r = sp.run([sys.executable, "-m", "narrative_architect",
                     "entity", "show", args.id, "--extended"],
                    capture_output=True, text=True, cwd=project_path.parent)
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr, end="")
            sys.exit(r.returncode)
        print(r.stdout)


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
    views = proj.metadata.setdefault("graph_views", {})
    if cmd == "save":
        if args.name in views and not getattr(args, "force", False):
            print(
                f"error: View '{args.name}' already exists. "
                "Use --force to overwrite.",
                file=sys.stderr,
            )
            sys.exit(1)
        preset = {
            "entity_type": args.type,
            "custom_type_id": getattr(args, "custom_type_id", None),
            "canon_state": args.canon,
            "visibility_state": getattr(args, "visibility", None),
            "domain_id": getattr(args, "domain_id", None),
            "layer_id": getattr(args, "layer_id", None),
            "relation_type": getattr(args, "relation_type", None),
            "custom_relation_type_id": None,
            "include_archived": getattr(args, "include_archived", False),
            "include_broken": True,
            "max_nodes": getattr(args, "max_nodes", 200),
            "max_edges": 500,
        }
        views[args.name] = preset
        save_result = ps.save(Path(project_path))
        if isinstance(save_result, Error):
            print(f"error: {save_result.error}", file=sys.stderr)
            sys.exit(1)
        print(f"View '{args.name}' saved")
    elif cmd == "show":
        preset = views.get(args.name)
        if not preset:
            print(f"error: View '{args.name}' not found", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(preset, indent=2, ensure_ascii=False))
    elif cmd == "list":
        if not views:
            print("No saved views")
            return
        for name in sorted(views):
            p = views[name]
            print(f"  {name}: type={p.get('entity_type','*')}, "
                  f"canon={p.get('canon_state','*')}, "
                  f"archived={p.get('include_archived',False)}")
    elif cmd == "delete":
        if args.name not in views:
            print(f"error: View '{args.name}' not found", file=sys.stderr)
            sys.exit(1)
        del views[args.name]
        save_result = ps.save(Path(project_path))
        if isinstance(save_result, Error):
            print(f"error: {save_result.error}", file=sys.stderr)
            sys.exit(1)
        print(f"View '{args.name}' deleted")
