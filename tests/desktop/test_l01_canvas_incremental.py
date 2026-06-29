"""BETA1-L01 — refresh incremental del canvas (update-in-place de hojas).

Una edición de atributos (mismos ids, misma estructura) debe actualizar los
items in situ y REUTILIZARLOS (sin rebuild O(N)). Cualquier cambio estructural
(alta, baja, contención, layout, filtros) cae al ``set_graph`` completo."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, _EdgeView, _NodeView

pytest_qt = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    if not HAS_QT:
        return None
    return QApplication.instance() or QApplication([])


def _node(entity_id, name, kind="concepto", layer_id=""):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id] if layer_id else []),
        entity_id=entity_id,
        name=name,
        kind=kind,
        subtitle="",
        canon="canonico",
        visibility="publico",
        layer_id=layer_id,
    )


def _edge(rid, a, b, kind="deriva_de"):
    return _EdgeView(
        relation=SimpleNamespace(id=rid), relation_id=rid,
        source_id=a, target_id=b, kind=kind, label=kind,
    )


@pytest_qt
def test_attribute_edit_updates_in_place_and_reuses_item(qapp):
    view = GraphCanvasView()
    view.set_graph([_node("a", "Alfa"), _node("b", "Beta")], [_edge("r", "a", "b")])
    item_a = view._nodes["a"]
    item_b = view._nodes["b"]

    # Editar SOLO el nombre de 'a'
    ok = view.try_incremental_refresh(
        [_node("a", "Alfa Renombrada"), _node("b", "Beta")], [_edge("r", "a", "b")]
    )
    assert ok is True
    assert view._nodes["a"] is item_a  # MISMO item: no hubo rebuild
    assert view._nodes["b"] is item_b
    assert "Renombrada" in item_a._title_item.text()
    assert item_a.node.name == "Alfa Renombrada"


@pytest_qt
def test_no_change_is_still_incremental(qapp):
    view = GraphCanvasView()
    view.set_graph([_node("a", "Alfa")], [])
    item_a = view._nodes["a"]
    ok = view.try_incremental_refresh([_node("a", "Alfa")], [])
    assert ok is True
    assert view._nodes["a"] is item_a


@pytest_qt
def test_addition_falls_back(qapp):
    view = GraphCanvasView()
    view.set_graph([_node("a", "Alfa")], [])
    # Añadir 'b' → no es seguro incremental
    assert view.try_incremental_refresh([_node("a", "Alfa"), _node("b", "Beta")], []) is False


@pytest_qt
def test_removal_falls_back(qapp):
    view = GraphCanvasView()
    view.set_graph([_node("a", "Alfa"), _node("b", "Beta")], [])
    assert view.try_incremental_refresh([_node("a", "Alfa")], []) is False


@pytest_qt
def test_containment_change_falls_back(qapp):
    view = GraphCanvasView()
    view.set_graph([_node("a", "Alfa"), _node("b", "Beta")], [])
    # Aparece una relación 'contiene' (anidamiento) → rebuild completo
    assert view.try_incremental_refresh(
        [_node("a", "Alfa"), _node("b", "Beta")], [_edge("c", "a", "b", kind="contiene")]
    ) is False


@pytest_qt
def test_container_kind_change_falls_back(qapp):
    view = GraphCanvasView()
    view.set_graph([_node("a", "Alfa"), _node("b", "Beta")], [])
    # 'a' pasa de hoja a contenedor → cambia el TIPO de item → rebuild
    assert view.try_incremental_refresh(
        [_node("a", "Alfa", kind="contenedor"), _node("b", "Beta")], []
    ) is False


@pytest_qt
def test_edge_attribute_change_falls_back(qapp):
    view = GraphCanvasView()
    view.set_graph(
        [_node("a", "Alfa"), _node("b", "Beta")], [_edge("r", "a", "b", kind="deriva_de")]
    )
    # La arista cambia de tipo → no reconstruimos aristas in situ → rebuild
    assert view.try_incremental_refresh(
        [_node("a", "Alfa"), _node("b", "Beta")], [_edge("r", "a", "b", kind="parte_de")]
    ) is False


@pytest_qt
def test_layout_change_falls_back(qapp):
    view = GraphCanvasView()
    view.set_graph([_node("a", "Alfa")], [])  # free
    assert view.try_incremental_refresh(
        [_node("a", "Alfa")], [], layout_mode="concentric_rings"
    ) is False
