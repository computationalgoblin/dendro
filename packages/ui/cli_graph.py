"""
CLI graph commands — graph summary, export, entity, path (B11-T03).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from packages.application.graph_models import GraphFilters
from packages.application.graph_service import GraphService
from packages.domain.result import Error
from packages.ui.cli import (
    SessionContext,
    _bootstrap_services,
    require_project_path,
)


def register_graph_commands(subparsers: Any) -> None:
    """Register ``graph`` subcommand under *subparsers*."""
    gp = subparsers.add_parser("graph", help="Graph commands")
    gs = gp.add_subparsers(dest="graph_command", required=True)

    # graph summary
    p_s = gs.add_parser("summary", help="Show graph stats")
    _add_filter_flags(p_s)

    # graph export [--json]
    p_e = gs.add_parser("export", help="Export graph view")
    p_e.add_argument("--json", action="store_true", help="Output as JSON")
    _add_filter_flags(p_e)

    # graph entity <id> --depth <n>
    p_ent = gs.add_parser("entity", help="Show entity neighborhood")
    p_ent.add_argument("id", help="Entity ID")
    p_ent.add_argument("--depth", type=int, default=1, help="Neighborhood depth (>=1)")
    _add_filter_flags(p_ent)

    # graph path <source> <target> --max-depth <n>
    p_path = gs.add_parser("path", help="Find path between entities")
    p_path.add_argument("source_id", help="Source entity ID")
    p_path.add_argument("target_id", help="Target entity ID")
    p_path.add_argument("--max-depth", type=int, default=5, help="Max depth (>=1)")
    _add_filter_flags(p_path)


def _add_filter_flags(parser: argparse.ArgumentParser) -> None:
    """Add shared filter flags to a parser."""
    parser.add_argument("--type", default=None, help="Filter by entity type")
    parser.add_argument("--custom-type-id", default=None, help="Filter by custom entity type")
    parser.add_argument("--canon", default=None, help="Filter by canon state")
    parser.add_argument("--visibility", default=None, help="Filter by visibility")
    parser.add_argument("--domain-id", default=None, help="Filter by domain ID")
    parser.add_argument("--layer-id", default=None, help="Filter by layer ID")
    parser.add_argument("--relation-type", default=None, help="Filter by relation type")
    parser.add_argument("--include-archived", action="store_true", help="Include archived")
    parser.add_argument("--max-nodes", type=int, default=200, help="Max visible nodes")


def _build_filters(args: argparse.Namespace) -> GraphFilters:
    """Build GraphFilters from CLI args."""
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


def _build_graph_service(project_path):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    gs = GraphService(query_service=qs, relation_service=rs, entity_service=es)
    return ps, gs


def handle_graph_command(args: argparse.Namespace, session: SessionContext) -> None:
    """Dispatch graph commands."""
    project_path = require_project_path(args, session)
    ps, graph_svc = _build_graph_service(project_path)
    cmd = args.graph_command

    if cmd == "summary":
        filters = _build_filters(args)
        result = graph_svc.get_graph_stats(filters)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        s = result.value
        print(f"Graph: {s.visible_nodes} nodes ({s.hidden_nodes} hidden), "
              f"{s.visible_edges} edges ({s.hidden_edges} hidden)")
        print(f"  Active:   {s.active_nodes} nodes, {s.active_edges} edges")
        print(f"  Archived: {s.archived_nodes} nodes, {s.archived_edges} edges")
        print(f"  Broken:   {s.broken_edges} edges")

    elif cmd == "export":
        filters = _build_filters(args)
        result = graph_svc.build_graph(filters)
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

    elif cmd == "entity":
        filters = _build_filters(args)
        result = graph_svc.build_entity_neighborhood(
            args.id, depth=args.depth, filters=filters,
        )
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        view = result.value
        print(f"Entity: {view.nodes[0].label if view.nodes else args.id} "
              f"({view.nodes[0].entity_type if view.nodes else '?'})")
        print(f"  Neighbors (depth {args.depth}): "
              f"{len(view.nodes) - 1} nodes, {len(view.edges)} edges")
        for e in view.edges:
            direction = "→" if e.source_id == args.id else "←"
            other_id = e.target_id if e.source_id == args.id else e.source_id
            other_node = next((n for n in view.nodes if n.id == other_id), None)
            other_label = other_node.label if other_node else other_id[:8]
            print(f"    {direction} {e.relation_type}: {other_label} "
                  f"({other_node.entity_type if other_node else '?'})")

    elif cmd == "path":
        filters = _build_filters(args)
        result = graph_svc.build_path_between(
            args.source_id, args.target_id,
            max_depth=args.max_depth, filters=filters,
        )
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        path = result.value
        if path.found:
            node_names = [n.label for n in path.nodes]
            edges_btwn = [e.relation_type for e in path.edges]
            parts = [node_names[0]]
            for i, et in enumerate(edges_btwn):
                parts.append(f"→ {et} → {node_names[i+1]}")
            print(f"Path found (length {path.length}):")
            print("  " + " ".join(parts))
        else:
            print(f"No path found between {args.source_id[:8]} "
                  f"and {args.target_id[:8]} (max depth {args.max_depth})")
