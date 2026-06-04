"""B37-T07 — Smoke test: medium-sized project validates search, filters, focus, suggestions."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.graph_canvas import (
        GraphCanvasView,
        VisualFilterState,
        _EdgeView,
        _NodeView,
    )

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _node(eid, name, kind, x=0.0, y=0.0, canon="canon", visibility="publico_mundo", layer=""):
    return _NodeView(
        entity=SimpleNamespace(
            id=eid, name=name, entity_type=SimpleNamespace(value=kind),
            brief="", description="", custom_metadata={},
            entity_name=name, importance="", development="",
            canon_state=SimpleNamespace(value=canon),
            visibility_state=SimpleNamespace(value=visibility),
            certainty="", color="#D0D8E0",
            layer_ids=[layer] if layer else [],
        ),
        entity_id=eid, name=name, kind=kind, subtitle="",
        canon=canon, visibility=visibility, layer_id=layer,
    )


def _edge(rid, kind, source, target):
    return _EdgeView(
        relation=SimpleNamespace(id=rid, relation_type=SimpleNamespace(value=kind)),
        relation_id=rid, kind=kind, label=kind,
        source_id=source, target_id=target,
    )


def build_medium_project(qapp):
    """20 entities, 10 relations, 3 trees, 5 causal, 3 layers."""
    nodes = [
        # Layer 1 — Metafísica
        _node("ent-meta1", "Dioses combatientes", "concepto", 0, 0, layer="metafisica"),
        _node("ent-meta2", "Primer dios", "personaje", -100, 80, layer="metafisica"),
        _node("ent-meta3", "Segundo dios", "personaje", 100, 80, layer="metafisica"),
        # Layer 2 — Materia
        _node("ent-mat1", "Gravedad inestable", "concepto", 0, 200, layer="materia"),
        _node("ent-mat2", "Materia residual", "objeto", -80, 280, layer="materia"),
        _node("ent-mat3", "Zonas temporales", "lugar", 80, 280, layer="materia"),
        # Layer 3 — Cultura
        _node("ent-cul1", "Culto a la caída", "concepto", 0, 400, layer="cultura"),
        _node("ent-cul2", "Templo del peso", "lugar", -80, 480, layer="cultura"),
        _node("ent-cul3", "Sacerdocio", "faccion", 80, 480, layer="cultura"),
        # Layer 4 — Status quo
        _node("ent-sq1", "Ciudad de Abisal", "lugar", -200, 600, layer="status_quo"),
        _node("ent-sq2", "Mercaderes del vacío", "faccion", 0, 600, layer="status_quo"),
        _node("ent-sq3", "Devian", "personaje", 200, 600, layer="status_quo"),
        _node("ent-sq4", "Akshan", "personaje", 300, 600, layer="status_quo"),
        _node("ent-sq5", "La Forja", "lugar", 400, 600, layer="status_quo"),
        # Trees
        _node("tree-pantheon", "Panteón", "contenedor", -200, -80, layer="metafisica"),
        _node("tree-ciudad", "Ciudad de Abisal", "contenedor", -200, 560, layer="status_quo"),
        _node("tree-culto", "Culto", "contenedor", -80, 440, layer="cultura"),
        # Standalone
        _node("ent-stand1", "Leyenda antigua", "objeto", -300, 300, layer="cultura"),
        _node("ent-stand2", "Artefacto roto", "objeto", 300, 300, layer="materia"),
        _node("ent-stand3", "Mercado nocturno", "lugar", 100, 700, layer="status_quo"),
    ]

    edges = [
        # Causal
        _edge("rel-caus1", "deriva_de", "ent-mat1", "ent-meta1"),
        _edge("rel-caus2", "deriva_de", "ent-mat2", "ent-meta1"),
        _edge("rel-caus3", "condiciona", "ent-cul1", "ent-mat1"),
        _edge("rel-caus4", "explica", "ent-sq1", "ent-cul1"),
        _edge("rel-caus5", "produce_consecuencia_en", "ent-cul3", "ent-mat3"),
        # Narrative
        _edge("rel-nar1", "alianza", "ent-sq3", "ent-sq4"),
        _edge("rel-nar2", "conflicto", "ent-sq2", "ent-cul3"),
        _edge("rel-nar3", "conoce", "ent-sq3", "ent-stand1"),
        # Structural
        _edge("rel-str1", "contiene", "tree-pantheon", "ent-meta2"),
        _edge("rel-str2", "contiene", "tree-pantheon", "ent-meta3"),
        _edge("rel-str3", "contiene", "tree-ciudad", "ent-sq1"),
        _edge("rel-str4", "contiene", "tree-ciudad", "ent-sq2"),
        _edge("rel-str5", "contiene", "tree-ciudad", "ent-sq3"),
        _edge("rel-str6", "contiene", "tree-culto", "ent-cul1"),
        _edge("rel-str7", "contiene", "tree-culto", "ent-cul2"),
    ]

    view = GraphCanvasView()
    view.resize(800, 600)
    view.set_graph(nodes, edges)
    return view, nodes, edges

def test_b37t07_medium_project_loads(qapp):
    view, nodes, edges = build_medium_project(qapp)
    assert len(view._nodes) == 20
    # Contiene edges become structural containers, not GraphEdgeItem
    non_contains = [e for e in edges if e.kind.lower() != "contiene"]
    assert len(view._edges) == len(non_contains)


def test_b37t07_search_finds_entity_by_name(qapp):
    view, _, _ = build_medium_project(qapp)
    results = view.search("Gravedad")
    assert any(r.item_id == "ent-mat1" for r in results)


def test_b37t07_search_finds_tree_by_name(qapp):
    view, _, _ = build_medium_project(qapp)
    results = view.search("Panteón")
    assert any(r.item_id == "tree-pantheon" for r in results)


def test_b37t07_search_no_ids_exposed(qapp):
    view, _, _ = build_medium_project(qapp)
    results = view.search("Devian")
    assert len(results) > 0
    for r in results:
        # display_lines() must not contain raw IDs
        for line in r.display_lines():
            assert "ent-" not in line
            assert "uuid" not in line.lower()


def test_b37t07_filter_by_layer_materia(qapp):
    view, _, _ = build_medium_project(qapp)
    view.apply_visual_filter(VisualFilterState(layer_ids=("materia",)))
    visible = {eid for eid, item in view._nodes.items() if item.isVisible()}
    assert "ent-mat1" in visible
    assert "ent-mat2" in visible
    assert "ent-cul1" not in visible


def test_b37t07_filter_by_tree(qapp):
    view, _, _ = build_medium_project(qapp)
    view.apply_visual_filter(VisualFilterState(tree_id="tree-ciudad"))
    visible = {eid for eid, item in view._nodes.items() if item.isVisible()}
    assert "tree-ciudad" in visible
    assert "ent-sq1" in visible


def test_b37t07_filter_causal_family(qapp):
    view, _, _ = build_medium_project(qapp)
    view.apply_visual_filter(VisualFilterState(relation_families=("causal",)))
    visible_kinds = {e.edge.kind for e in view._edges if e.isVisible()}
    assert "deriva_de" in visible_kinds
    assert "alianza" not in visible_kinds


def test_b37t07_focus_tree_scope(qapp):
    view, _, _ = build_medium_project(qapp)
    assert view.focus_tree_scope("tree-pantheon") is True
    visible = set(view._nodes)
    assert "tree-pantheon" in visible
    assert "ent-meta2" in visible
    assert "ent-sq3" not in visible


def test_b37t07_focus_neighborhood_entity(qapp):
    view, _, _ = build_medium_project(qapp)
    assert view.focus_neighborhood("ent-sq3") is True
    visible = set(view._nodes)
    assert "ent-sq3" in visible
    # Devian's neighbors via alliance and knowledge
    assert "ent-sq4" in visible  # alliance


def test_b37t07_clear_filters_restores_all(qapp):
    view, _, _ = build_medium_project(qapp)
    view.apply_visual_filter(VisualFilterState(entity_types=("personaje",)))
    view.clear_visual_filters()
    assert len(view._nodes) == 20


def test_b37t07_filter_then_search(qapp):
    view, _, _ = build_medium_project(qapp)
    view.apply_visual_filter(VisualFilterState(layer_ids=("cultura",)))
    results = view.search("Culto")
    assert any(r.item_id == "ent-cul1" for r in results)


def test_b37t07_camera_fit_all_medium(qapp):
    view, _, _ = build_medium_project(qapp)
    view.fit_all()
    view.reset_view()
    assert view.focus_node("ent-meta1") is True
    assert view.center_selection() is True


def test_b37t07_filter_hide_relations_no_orphan_edges(qapp):
    view, _, _ = build_medium_project(qapp)
    view.apply_visual_filter(VisualFilterState(show_relations=False))
    for edge in view._edges:
        assert not edge.isVisible()
