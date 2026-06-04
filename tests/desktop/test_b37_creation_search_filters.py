from __future__ import annotations

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


def node(entity_id: str, name: str, kind: str = "personaje", *, subtitle="", layer_id="", canon="canonico", visibility="publico"):
    entity = SimpleNamespace(id=entity_id, name=name)
    return _NodeView(
        entity=entity,
        entity_id=entity_id,
        name=name,
        kind=kind,
        subtitle=subtitle or f"Descripción de {name}",
        canon=canon,
        visibility=visibility,
        layer_id=layer_id,
    )


def edge(relation_id: str, source_id: str, target_id: str, kind: str = "esta_relacionado_con"):
    relation = SimpleNamespace(id=relation_id)
    return _EdgeView(
        relation=relation,
        relation_id=relation_id,
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        label=kind.replace("_", " "),
    )


def build_view(qapp):
    view = GraphCanvasView()
    nodes = [
        node("tree-hermandad", "Hermandad del Acero", "contenedor"),
        node("ent-devian", "Devian", "personaje", subtitle="Espía de la Hermandad", layer_id="layer-cultura"),
        node("ent-forja", "Forja Negra", "lugar", layer_id="layer-materia", visibility="privado"),
    ]
    edges = [
        edge("rel-contiene", "tree-hermandad", "ent-devian", "contiene"),
        edge("rel-alianza", "ent-devian", "ent-forja", "es_aliado_de"),
        edge("rel-causal", "tree-hermandad", "ent-forja", "deriva_de"),
    ]
    layers = [
        SimpleNamespace(id="layer-cultura", name="Culturas y sociedades", is_visible=True, metadata={"causal_rank": 7}),
        SimpleNamespace(id="layer-materia", name="Materia y naturaleza", is_visible=True, metadata={"causal_rank": 3}),
    ]
    view.set_graph(nodes, edges, layer_mode=False, layers=layers)
    return view, nodes, edges


def test_b37_search_finds_entity_by_name(qapp):
    view, _, _ = build_view(qapp)
    results = view.search("Devian")
    assert any(r.title == "Devian" and r.item_kind == "entity" for r in results)


def test_b37_search_finds_tree_by_name(qapp):
    view, _, _ = build_view(qapp)
    results = view.search("Hermandad")
    assert any(r.title == "Hermandad del Acero" and r.item_kind == "tree" for r in results)


def test_b37_search_finds_relation_by_type(qapp):
    view, _, _ = build_view(qapp)
    results = view.search("aliado")
    assert any(r.item_kind == "relation" and r.category == "Relación" for r in results)


def test_b37_search_by_layer_when_worldbuilding_active(qapp):
    view, _, _ = build_view(qapp)
    results = view.search("culturas", worldbuilding_active=True)
    assert any(r.title == "Devian" for r in results)


def test_b37_search_display_lines_do_not_expose_ids(qapp):
    view, _, _ = build_view(qapp)
    result = next(r for r in view.search("Devian") if r.title == "Devian")
    display = "\n".join(result.display_lines())
    assert "ent-devian" not in display
    assert "tree-hermandad" not in display
    assert "{" not in display and "}" not in display


def test_b37_focus_node_uses_canvas_api(qapp):
    view, _, _ = build_view(qapp)
    assert view.focus_node("ent-devian") is True
    assert view.selected_entity_ids() == ["ent-devian"]


def test_b37_collapsed_tree_search_result_handles_focus_without_error(qapp):
    view, _, _ = build_view(qapp)
    tree = view._trees["tree-hermandad"]
    tree._collapse()
    result = next(r for r in view.search("Devian") if r.title == "Devian")
    assert result.is_inside_collapsed_tree is True
    assert result.parent_tree_name == "Hermandad del Acero"
    assert view.focus_node("ent-devian") is True
    assert getattr(tree, "_collapsed", False) is False


def test_b37_filter_by_entity_type(qapp):
    view, _, _ = build_view(qapp)
    view.apply_visual_filter(VisualFilterState(entity_types=("personaje",)))
    assert set(view._nodes) == {"ent-devian"}


def test_b37_filter_by_layer(qapp):
    view, _, _ = build_view(qapp)
    view.apply_visual_filter(VisualFilterState(layer_ids=("layer-materia",)))
    assert set(view._nodes) == {"ent-forja"}


def test_b37_filter_by_tree_includes_tree_and_descendants(qapp):
    view, _, _ = build_view(qapp)
    view.apply_visual_filter(VisualFilterState(tree_id="tree-hermandad"))
    assert "tree-hermandad" in view._nodes
    assert "ent-devian" in view._nodes
    assert "ent-forja" not in view._nodes


def test_b37_hide_relations(qapp):
    view, _, _ = build_view(qapp)
    view.apply_visual_filter(VisualFilterState(show_relations=False))
    assert all(not edge_item.isVisible() for edge_item in view._edges)


def test_b37_clear_filters_restores_view(qapp):
    view, _, _ = build_view(qapp)
    view.apply_visual_filter(VisualFilterState(entity_types=("personaje",)))
    assert set(view._nodes) == {"ent-devian"}
    view.clear_visual_filters()
    assert {"tree-hermandad", "ent-devian", "ent-forja"}.issubset(set(view._nodes))


def test_b37_edges_hidden_if_endpoint_hidden(qapp):
    view, _, _ = build_view(qapp)
    view.apply_visual_filter(VisualFilterState(entity_types=("personaje",)))
    assert all(item.edge.source_id in view._nodes and item.edge.target_id in view._nodes for item in view._edges)


def test_b37_filters_do_not_mutate_node_models(qapp):
    view, nodes, _ = build_view(qapp)
    before = [(n.entity_id, n.name, n.kind, n.canon, n.visibility, n.layer_id) for n in nodes]
    view.apply_visual_filter(VisualFilterState(entity_types=("personaje",), show_relations=False))
    view.clear_visual_filters()
    after = [(n.entity_id, n.name, n.kind, n.canon, n.visibility, n.layer_id) for n in nodes]
    assert after == before
