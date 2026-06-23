from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, GraphCanvasWidget, VisualFilterState, _EdgeView, _NodeView
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def layer(layer_id: str, name: str, rank: int | None, *, visible: bool = True):
    metadata = {} if rank is None else {"causal_rank": str(rank)}
    return SimpleNamespace(id=layer_id, name=name, metadata=metadata, is_visible=visible, order=0)


def node(entity_id: str, name: str, *, kind: str = "concepto", layer_id: str = ""):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id] if layer_id else []),
        entity_id=entity_id,
        name=name,
        kind=kind,
        subtitle=f"Descripción de {name}",
        canon="canonico",
        visibility="publico",
        layer_id=layer_id,
    )


def edge(relation_id: str, source_id: str, target_id: str, kind: str = "deriva_de"):
    return _EdgeView(
        relation=SimpleNamespace(id=relation_id),
        relation_id=relation_id,
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        label=kind.replace("_", " "),
    )


def ring_by_id(view: "GraphCanvasView", ring_id: str):
    return next(r for r in view._ring_visuals if r.ring_id == ring_id)


def test_b44_concentric_layout_orders_layers_by_causal_rank_center_to_outer(qapp):
    view = GraphCanvasView()
    layers = [
        layer("politica", "Política", 5),
        layer("metafisica", "Metafísica", 1),
        layer("naturaleza", "Naturaleza", 2),
    ]
    nodes = [
        node("n-politica", "Senado", layer_id="politica"),
        node("n-meta", "Dioses", layer_id="metafisica"),
        node("n-naturaleza", "Bosque", layer_id="naturaleza"),
    ]

    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)

    assert view._layout_mode_active == "concentric_rings"
    assert [r.ring_id for r in view._ring_visuals] == ["metafisica", "naturaleza", "politica"]
    radii = [r.inner_radius for r in view._ring_visuals]
    assert radii == sorted(radii)
    assert ring_by_id(view, "metafisica").outer_radius < ring_by_id(view, "politica").inner_radius


def test_b44_concentric_layout_keeps_user_unranked_rings_and_unassigned_bucket(qapp):
    view = GraphCanvasView()
    layers = [
        layer("metafisica", "Metafísica", 1),
        layer("meta", "Notas meta", None),
    ]
    nodes = [
        node("n-meta", "Dioses", layer_id="metafisica"),
        node("n-unranked", "Tono", layer_id="meta"),
        node("n-free", "Sin anillo"),
    ]

    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)

    assert [r.ring_id for r in view._ring_visuals] == ["metafisica", "meta", "__unclassified__"]
    assert view._node_ring_ids["n-unranked"] == "meta"
    unclassified = ring_by_id(view, "__unclassified__")
    assert unclassified.display_name == "Sin clasificar"
    assert set(unclassified.item_ids) == {"n-free"}
    assert unclassified.inner_radius > ring_by_id(view, "meta").outer_radius


def test_b44_concentric_layout_radius_grows_with_content_and_pushes_outer_rings(qapp):
    layers = [layer("metafisica", "Metafísica", 1), layer("politica", "Política", 5)]

    sparse = GraphCanvasView()
    sparse.set_graph(
        [node("m1", "M1", layer_id="metafisica"), node("p1", "P1", layer_id="politica")],
        [],
        layout_mode="concentric_rings",
        layers=layers,
    )

    dense = GraphCanvasView()
    dense_nodes = [node(f"m{i}", f"M{i}", layer_id="metafisica") for i in range(12)]
    dense_nodes.append(node("p1", "P1", layer_id="politica"))
    dense.set_graph(dense_nodes, [], layout_mode="concentric_rings", layers=layers)

    sparse_meta = ring_by_id(sparse, "metafisica")
    dense_meta = ring_by_id(dense, "metafisica")
    sparse_politica = ring_by_id(sparse, "politica")
    dense_politica = ring_by_id(dense, "politica")

    assert dense_meta.outer_radius - dense_meta.inner_radius > sparse_meta.outer_radius - sparse_meta.inner_radius
    assert dense_politica.inner_radius > sparse_politica.inner_radius


def test_b44_concentric_layout_places_items_inside_their_ring(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1), layer("politica", "Política", 5)]
    nodes = [
        node("m1", "M1", layer_id="metafisica"),
        node("m2", "M2", kind="contenedor", layer_id="metafisica"),
        node("p1", "P1", layer_id="politica"),
    ]

    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)

    for n in nodes:
        item = view._nodes[n.entity_id]
        center = item.sceneBoundingRect().center()
        distance = (center.x() ** 2 + center.y() ** 2) ** 0.5
        ring = ring_by_id(view, n.layer_id)
        assert ring.inner_radius <= distance <= ring.outer_radius


def test_b44_concentric_layout_mode_does_not_destroy_free_view_or_relations(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1), layer("politica", "Política", 5)]
    nodes = [node("m1", "M1", layer_id="metafisica"), node("p1", "P1", layer_id="politica")]
    edges = [edge("r1", "m1", "p1")]

    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)
    assert set(view._nodes) == {"m1", "p1"}
    assert [e.edge.relation_id for e in view._edges] == ["r1"]

    view.set_graph(nodes, edges, layout_mode="free", layers=layers)

    assert view._layout_mode_active == "free"
    assert view._ring_visuals == []
    assert set(view._nodes) == {"m1", "p1"}
    assert [e.edge.relation_id for e in view._edges] == ["r1"]


def test_b44_ring_focus_filters_to_ring_and_hides_floating_edges(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1), layer("politica", "Política", 5)]
    nodes = [
        node("m1", "M1", layer_id="metafisica"),
        node("m2", "M2", layer_id="metafisica"),
        node("p1", "P1", layer_id="politica"),
    ]
    edges = [edge("inside", "m1", "m2"), edge("cross", "m1", "p1")]
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)

    assert view.focus_ring_scope("metafisica") is True

    assert view._focused_ring_id == "metafisica"
    assert [ring.ring_id for ring in view._ring_visuals] == ["metafisica"]
    assert len(view._ring_items) == 1
    assert set(view._nodes) == {"m1", "m2"}
    assert [e.edge.relation_id for e in view._edges] == ["inside"]
    assert ring_by_id(view, "metafisica").state == "focused"


def test_b44_ring_items_exist_for_empty_area_selection_and_double_click_entry(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1)]
    view.set_graph([node("m1", "M1", layer_id="metafisica")], [], layout_mode="concentric_rings", layers=layers)

    assert "metafisica" in view._ring_items
    assert view.select_ring("metafisica") is True
    assert view._selected_ring_id == "metafisica"


def test_b44_clear_focus_restores_global_concentric_layout(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1), layer("politica", "Política", 5)]
    nodes = [node("m1", "M1", layer_id="metafisica"), node("p1", "P1", layer_id="politica")]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)
    assert view.focus_ring_scope("metafisica") is True
    assert set(view._nodes) == {"m1"}

    view.clear_focus_scope()

    assert view._focused_ring_id == ""
    assert view._layout_mode_active == "concentric_rings"
    assert [ring.ring_id for ring in view._ring_visuals] == ["metafisica", "politica"]
    assert set(view._nodes) == {"m1", "p1"}


def test_b44_ring_focus_does_not_leave_layer_visual_filter_after_reassignment(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1), layer("politica", "Política", 5)]
    nodes = [node("m1", "M1", layer_id="metafisica"), node("p1", "P1", layer_id="politica")]
    view.apply_visual_filter(VisualFilterState(layer_ids=("metafisica",)))
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)

    assert view.focus_ring_scope("metafisica") is True

    assert view.get_filter_state().layer_ids == ()
    assert [ring.ring_id for ring in view._ring_visuals] == ["metafisica"]


def test_b44_marks_inter_ring_edges_without_changing_relation_canon(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1), layer("naturaleza", "Naturaleza", 2)]
    nodes = [node("m1", "M1", layer_id="metafisica"), node("n1", "N1", layer_id="naturaleza")]
    edges = [edge("cross", "m1", "n1", kind="deriva_de")]
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)

    edge_item = view._edges[0]

    assert edge_item.edge.inter_ring is True
    assert edge_item.edge.causal is True
    assert getattr(edges[0].relation, "custom_metadata", {}) == {}


def test_b44_intra_ring_edges_remain_plain(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1)]
    nodes = [node("m1", "M1", layer_id="metafisica"), node("m2", "M2", layer_id="metafisica")]
    edges = [edge("inside", "m1", "m2", kind="deriva_de")]
    view.set_graph(nodes, edges, layout_mode="concentric_rings", layers=layers)

    assert view._edges[0].edge.inter_ring is False
    assert view._edges[0].edge.causal is True


def test_b44_concentric_widget_does_not_auto_apply_default_rings(qapp):
    ctx = SimpleNamespace(
        advanced_mode=False,
        creation_layout_mode="free",
        creation_focused_ring_id="",
        selected_entity_id="",
        save_preferences=lambda: None,
        log=lambda *args, **kwargs: None,
    )
    widget = GraphCanvasWidget(ctx)
    project = SimpleNamespace(world_layers=[])

    layers = widget._effective_world_layers(project)
    view = GraphCanvasView()
    nodes = [node("n-meta", "Dioses", layer_id="layer_metafisica")]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)

    assert layers == []
    assert not any(ring.ring_id == "layer_metafisica" for ring in view._ring_visuals)
    assert ring_by_id(view, "__unclassified__").item_ids == ("n-meta",)
    assert len(view._ring_items) == 1


def test_b44_selecting_ring_sets_active_ring_for_contextual_creation(qapp):
    view = GraphCanvasView()
    layers = [layer("metafisica", "Metafísica", 1)]
    view.set_graph([node("n-meta", "Dioses", layer_id="metafisica")], [], layout_mode="concentric_rings", layers=layers)

    assert view.select_ring("metafisica") is True
    assert view.active_ring_id() == "metafisica"


def test_b44_creation_payload_uses_active_ring_and_ignores_unclassified(qapp):
    workspace = CreationWorkspace.__new__(CreationWorkspace)
    workspace.graph = SimpleNamespace(active_ring_id=lambda: "layer_metafisica")

    payload = workspace._with_active_ring_payload({"name": "Nueva hoja", "layer_ids": []})

    assert payload["layer_ids"] == ["layer_metafisica"]

    workspace.graph = SimpleNamespace(active_ring_id=lambda: "__unclassified__")
    payload = workspace._with_active_ring_payload({"name": "Nueva hoja"})

    assert "layer_ids" not in payload


def _scope_workspace(monkeypatch, *, focused: str, active: str, layers):
    """CreationWorkspace mínima para ejercitar `_current_context_scope` sin Qt real."""
    import packages.application.creative_context as cc
    monkeypatch.setattr(cc, "project_creative_brief", lambda project: {})
    monkeypatch.setattr(cc, "selected_entity_creative_context", lambda project, ids=None: [])
    monkeypatch.setattr(cc, "selected_branch_creative_context", lambda project, ids=None: [])

    ws = CreationWorkspace.__new__(CreationWorkspace)
    project = SimpleNamespace(
        id="proj",
        worldbuilding_active=True,
        world_layers=[SimpleNamespace(id=lid, name=lid, metadata={}) for lid in layers],
    )
    ws._get_active_project = lambda: project
    ws._chrono_context_hito_ids = []
    canvas = SimpleNamespace(
        _visual_filter=VisualFilterState(),
        _ring_display_name=lambda rid: rid,
    )
    ws.graph = SimpleNamespace(
        canvas=canvas,
        focused_ring_id=lambda: focused,
        active_ring_id=lambda: active,
        selected_entity_ids=lambda: [],
        selected_relation_ids=lambda: [],
        active_filter_count=lambda: 0,
    )
    return ws


def test_ux5c_context_scope_uses_selected_ring_not_only_focused(qapp, monkeypatch):
    """Regresión UX5c-fix: un anillo SELECCIONADO (clic simple, sin enfocar) debe
    viajar en el scope como `active_ring_id`. Antes el scope solo miraba el anillo
    ENFOCADO, así que una entidad creada sobre una mera selección nacía «sin anillo»
    y sin el contexto temático del anillo (incoherente con su trama)."""
    ws = _scope_workspace(
        monkeypatch, focused="", active="designio_oculto", layers=["designio_oculto"]
    )

    scope = ws._current_context_scope()

    assert scope["active_ring_id"] == "designio_oculto"  # ← el arreglo: alimenta layer_ids + brief
    assert scope["focused_ring_id"] == ""  # el breadcrumb de zoom sigue vacío sin enfocar
    assert scope["focus_label"] == ""


def test_ux5c_context_scope_drops_stale_active_ring(qapp, monkeypatch):
    """Un anillo activo que ya no existe en el proyecto no debe filtrarse al scope."""
    ws = _scope_workspace(monkeypatch, focused="", active="anillo_borrado", layers=["otro"])

    scope = ws._current_context_scope()

    assert scope["active_ring_id"] == ""


def test_b44_concentric_widget_opens_with_empty_project(qapp):
    project = SimpleNamespace(world_layers=[], entities=[], relations=[])
    ctx = SimpleNamespace(
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
        advanced_mode=False,
        creation_layout_mode="free",
        creation_focused_ring_id="",
        selected_entity_id="",
        save_preferences=lambda: None,
        log=lambda *args, **kwargs: None,
    )
    widget = GraphCanvasWidget(ctx)

    widget.set_layout_mode("concentric_rings")

    assert widget.canvas.isHidden() is False
    assert widget.empty.isHidden() is True
    assert widget.canvas._layout_mode_active == "concentric_rings"
    assert len(widget.canvas._ring_items) == 0
    assert widget.canvas.select_ring("layer_metafisica") is False
    assert widget.canvas.active_ring_id() == ""


def test_b44_concentric_refresh_does_not_auto_reapply_saved_ring_focus(qapp):
    project = SimpleNamespace(world_layers=[], entities=[], relations=[])
    ctx = SimpleNamespace(
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
        advanced_mode=False,
        creation_layout_mode="concentric_rings",
        creation_focused_ring_id="layer_campaña",
        save_preferences=lambda: None,
        log=lambda *args, **kwargs: None,
    )
    widget = GraphCanvasWidget(ctx)
    widget.set_layout_mode("concentric_rings")
    widget.refresh()

    assert widget.canvas._layout_mode_active == "concentric_rings"
    assert widget.canvas.focused_ring_id() == ""
    assert len(widget.canvas._ring_items) == 0
