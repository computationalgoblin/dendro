"""
Tests for graph layout (B11-T04) — circular, by_type.
"""

from __future__ import annotations

import json

from packages.application.graph_layout import (
    GraphLayout,
    layout_by_type,
    layout_circular,
)
from packages.application.graph_models import GraphNode, GraphView


def _make_view(n: int) -> GraphView:
    nodes = [
        GraphNode(id=f"n{i}", label=f"Node{i}",
                  entity_type="personaje" if i % 2 == 0 else "localizacion")
        for i in range(n)
    ]
    return GraphView(nodes=nodes)


class TestLayoutCircular:
    def test_empty(self) -> None:
        view = GraphView()
        layout = layout_circular(view)
        assert layout.nodes == []
        assert layout.edges == []

    def test_one_node(self) -> None:
        view = _make_view(1)
        layout = layout_circular(view)
        assert len(layout.nodes) == 1

    def test_deterministic(self) -> None:
        view = _make_view(4)
        l1 = layout_circular(view)
        l2 = layout_circular(view)
        for a, b in zip(l1.nodes, l2.nodes):
            assert a.x == b.x
            assert a.y == b.y

    def test_to_dict_json(self) -> None:
        view = _make_view(3)
        layout = layout_circular(view)
        d = layout.to_dict()
        assert len(d["nodes"]) == 3
        json.dumps(d)  # must be JSON-serializable


class TestLayoutByType:
    def test_groups_by_type(self) -> None:
        view = _make_view(4)
        layout = layout_by_type(view)
        # Should have 2 groups: personaje and localizacion
        groups = {n.group for n in layout.nodes}
        assert len(groups) == 2

    def test_to_dict_json(self) -> None:
        view = _make_view(3)
        layout = layout_by_type(view)
        d = layout.to_dict()
        json.dumps(d)

    def test_group_by_domain(self) -> None:
        nodes = [
            GraphNode(id="a", label="A", entity_type="personaje",
                      domain_ids=["mundo"]),
            GraphNode(id="b", label="B", entity_type="personaje",
                      domain_ids=["historia"]),
        ]
        view = GraphView(nodes=nodes)
        layout = layout_by_type(view, group_by="domain_id")
        groups = {n.group for n in layout.nodes}
        assert "mundo" in groups
        assert "historia" in groups
