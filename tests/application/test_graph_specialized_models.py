from __future__ import annotations

import json

from packages.application.graph_models import (
    GraphComparison,
    GraphComparisonChange,
    GraphFilters,
    GraphOverlay,
    GraphScope,
    GraphView,
    GraphViewType,
    SavedGraphView,
)


def test_b28_contract_exposes_15_specialized_graph_view_types() -> None:
    values = {item.value for item in GraphViewType}

    assert values == {
        "global",
        "personaje",
        "localizacion",
        "faccion",
        "conflicto",
        "secretos",
        "pistas",
        "cronologia",
        "causal",
        "campana",
        "sesion",
        "conocimiento",
        "estructura_narrativa",
        "inconsistencias",
        "capas",
    }


def test_graph_filters_scope_overlay_and_audience_are_json_serializable() -> None:
    filters = GraphFilters(
        view_type=GraphViewType.SECRETOS,
        scope=GraphScope(scope_type="campaign", ids=["camp_1"]),
        overlays=[GraphOverlay.ISSUES, GraphOverlay.CANDIDATES],
        audience="player",
        campaign_id="camp_1",
        session_id="ses_1",
    )

    data = filters.to_dict()

    assert data["view_type"] == "secretos"
    assert data["scope"] == {"scope_type": "campaign", "ids": ["camp_1"]}
    assert data["overlays"] == ["issues", "candidates"]
    assert data["audience"] == "player"
    json.dumps(data)


def test_saved_graph_view_persists_configuration_not_nodes_or_edges() -> None:
    saved = SavedGraphView(
        name="Player secrets",
        filters=GraphFilters(view_type="secretos", audience="player"),
        overlays=[GraphOverlay.SECRETS],
        layout_preferences={"algorithm": "circular", "positions": {"n1": [1, 2]}},
    )

    data = saved.to_dict()

    assert data["name"] == "Player secrets"
    assert data["filters"]["view_type"] == "secretos"
    assert data["layout_preferences"]["positions"] == {"n1": [1, 2]}
    assert "nodes" not in data
    assert "edges" not in data
    assert SavedGraphView.from_dict(data).layout_preferences["positions"]["n1"] == [1, 2]


def test_graph_view_contains_type_scope_clusters_and_overlays() -> None:
    view = GraphView(
        view_type=GraphViewType.FACCION,
        scope=GraphScope(scope_type="domain", ids=["mundo"]),
        overlays={"issues": [{"id": "iss_1"}]},
        clusters={"faction:f1": ["ent_1"]},
    )

    data = view.to_dict()

    assert data["view_type"] == "faccion"
    assert data["scope"] == {"scope_type": "domain", "ids": ["mundo"]}
    assert data["overlays"]["issues"] == [{"id": "iss_1"}]
    assert data["clusters"] == {"faction:f1": ["ent_1"]}
    json.dumps(data)


def test_graph_comparison_reports_added_removed_changed_without_snapshots() -> None:
    cmp = GraphComparison(
        view_a_id="old",
        view_b_id="new",
        added_nodes=[GraphComparisonChange(id="n2", kind="node")],
        removed_edges=[GraphComparisonChange(id="e1", kind="edge")],
        changed_nodes=[GraphComparisonChange(id="n1", kind="node", changes={"label": ["A", "A2"]})],
    )

    data = cmp.to_dict()

    assert data["added_nodes"][0]["id"] == "n2"
    assert data["removed_edges"][0]["id"] == "e1"
    assert data["changed_nodes"][0]["changes"] == {"label": ["A", "A2"]}
    assert "snapshot" not in json.dumps(data).lower()
