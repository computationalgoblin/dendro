"""BETA1-B03: CRUD end-to-end de hojas, ramas, relaciones y anillos.

Parte 1 (sin Qt): operaciones vía controladores → servicios de aplicación,
incluida la persistencia (guardar/reabrir). Parte 2 (Qt): menú contextual
'Mover a anillo' emitiendo la señal B03.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from packages.application.project_service import ProjectService
from packages.application.world_layer_service import WorldLayerService
from packages.domain.result import Error, Ok
from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, _NodeView


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture()
def ps() -> ProjectService:
    service = ProjectService()
    result = service.create("CRUD Test BETA1")
    assert isinstance(result, Ok), f"create project failed: {result}"
    layer_service = WorldLayerService(service)
    for name in ("Anillo CRUD", "Anillo destino"):
        layer_result = layer_service.create_layer(name)
        assert isinstance(layer_result, Ok), f"create layer failed: {getattr(layer_result, 'error', '')}"
    return service


def world_layer_ids(ps: ProjectService) -> list[str]:
    return [str(layer.id) for layer in ps.active_project.world_layers]


def make_entity(ec: EntityController, name: str, *, kind: str = "nota", layer_ids=None) -> str:
    result = ec.create({
        "name": name,
        "entity_type": kind,
        "brief_description": "",
        "canon_state": "borrador",
        "layer_ids": list(layer_ids or []),
    })
    assert isinstance(result, Ok), f"create entity failed: {getattr(result, 'error', '')}"
    return str(result.value.id)


def _workspace_for(ps: ProjectService) -> CreationWorkspace:
    workspace = CreationWorkspace.__new__(CreationWorkspace)
    workspace.entity_controller = EntityController(ps)
    workspace.relation_controller = RelationController(ps)
    workspace.ctx = SimpleNamespace(
        project_controller=SimpleNamespace(ps=ps),
        log=lambda *args, **kwargs: None,
        drawer=None,
    )
    workspace.graph = SimpleNamespace(
        active_ring_id=lambda: "",
        focused_ring_id=lambda: "",
        canvas=SimpleNamespace(reveal_entity=lambda entity_id: None),
    )
    workspace.refresh = lambda: None
    workspace._open_node_panel = lambda *args, **kwargs: None
    workspace._open_tree_panel = lambda *args, **kwargs: None
    return workspace


# ── CRUD: crear ───────────────────────────────────────────────────────────

def test_create_leaf_lands_in_domain_with_ring(ps):
    ec = EntityController(ps)
    ring = world_layer_ids(ps)[0]
    eid = make_entity(ec, "Hoja CRUD", layer_ids=[ring])
    entity = next(e for e in ps.active_project.entities if e.id == eid)
    assert entity.name == "Hoja CRUD"
    assert ring in [str(v) for v in entity.layer_ids]


def test_create_branch_as_container(ps):
    ec = EntityController(ps)
    eid = make_entity(ec, "Rama CRUD", kind="contenedor")
    entity = next(e for e in ps.active_project.entities if e.id == eid)
    etype = str(getattr(entity.entity_type, "value", entity.entity_type))
    assert etype == "contenedor"


def test_convert_leaf_to_branch_preserves_fields(ps):
    ec = EntityController(ps)
    ring = world_layer_ids(ps)[0]
    eid = make_entity(ec, "Hoja convertible", layer_ids=[ring])
    result = ec.es.convert_to_branch(eid)
    assert isinstance(result, Ok), f"convert_to_branch failed: {getattr(result, 'error', '')}"
    entity = next(e for e in ps.active_project.entities if e.id == eid)
    etype = str(getattr(entity.entity_type, "value", entity.entity_type))
    assert etype == "contenedor"
    assert entity.name == "Hoja convertible"
    assert ring in [str(v) for v in entity.layer_ids]


def test_create_relation_between_leaves(ps):
    ec = EntityController(ps)
    rc = RelationController(ps)
    a = make_entity(ec, "Origen")
    b = make_entity(ec, "Destino")
    result = rc.create(a, b, "deriva_de", {})
    assert isinstance(result, Ok), f"create relation failed: {getattr(result, 'error', '')}"
    assert any(r.source_id == a and r.target_id == b for r in ps.active_project.relations)


# ── CRUD: actualizar ──────────────────────────────────────────────────────

def test_update_entity_name_visible_in_domain(ps):
    ec = EntityController(ps)
    eid = make_entity(ec, "Nombre viejo")
    result = ec.update(eid, {"name": "Nombre nuevo"})
    assert isinstance(result, Ok), f"update failed: {getattr(result, 'error', '')}"
    entity = next(e for e in ps.active_project.entities if e.id == eid)
    assert entity.name == "Nombre nuevo"


def test_move_entity_to_other_ring_via_update(ps):
    """The 'Mover a anillo' route: layer_ids swap via EntityController.update."""
    ec = EntityController(ps)
    rings = world_layer_ids(ps)
    assert len(rings) >= 2, "default world layers should provide several rings"
    eid = make_entity(ec, "Hoja móvil", layer_ids=[rings[0]])
    result = ec.update(eid, {"layer_ids": [rings[1]]})
    assert isinstance(result, Ok), f"update layer_ids failed: {getattr(result, 'error', '')}"
    entity = next(e for e in ps.active_project.entities if e.id == eid)
    ids = [str(v) for v in entity.layer_ids]
    assert rings[1] in ids and rings[0] not in ids


def test_create_leaf_inside_branch_inherits_branch_ring(ps):
    ec = EntityController(ps)
    rings = world_layer_ids(ps)
    branch = make_entity(ec, "Rama con anillo", kind="contenedor", layer_ids=[rings[0]])
    workspace = _workspace_for(ps)

    workspace._create_entity_in_tree(branch)

    created = next(e for e in ps.active_project.entities if e.name == "Nueva hoja")
    assert [str(v) for v in created.layer_ids][:1] == [rings[0]]
    assert any(
        workspace._rtype_value(rel) == "contiene"
        and getattr(rel, "source_id", "") == branch
        and getattr(rel, "target_id", "") == created.id
        for rel in ps.active_project.relations
    )


def test_move_branch_to_ring_moves_its_content(ps):
    ec = EntityController(ps)
    rc = RelationController(ps)
    rings = world_layer_ids(ps)
    branch = make_entity(ec, "Rama movible", kind="contenedor", layer_ids=[rings[0]])
    child = make_entity(ec, "Hoja dentro", layer_ids=[rings[0]])
    rc.create(branch, child, "contiene", {})
    workspace = _workspace_for(ps)

    workspace._assign_node_to_ring(branch, rings[1])

    branch_entity = next(e for e in ps.active_project.entities if e.id == branch)
    child_entity = next(e for e in ps.active_project.entities if e.id == child)
    assert [str(v) for v in branch_entity.layer_ids][:1] == [rings[1]]
    assert [str(v) for v in child_entity.layer_ids][:1] == [rings[1]]


# ── CRUD: eliminar ────────────────────────────────────────────────────────

def test_delete_relation_removes_line_data(ps):
    ec = EntityController(ps)
    rc = RelationController(ps)
    a = make_entity(ec, "A")
    b = make_entity(ec, "B")
    rel = rc.create(a, b, "deriva_de", {})
    rid = str(rel.value.id)
    result = rc.delete(rid)
    assert isinstance(result, Ok)
    assert not any(r.id == rid for r in ps.active_project.relations)


def test_delete_entity_cascades_relations(ps):
    ec = EntityController(ps)
    rc = RelationController(ps)
    a = make_entity(ec, "Cascada A")
    b = make_entity(ec, "Cascada B")
    rc.create(a, b, "deriva_de", {})
    result = ec.delete(a)
    assert isinstance(result, Ok)
    assert not any(e.id == a for e in ps.active_project.entities)
    assert not any(r.source_id == a or r.target_id == a for r in ps.active_project.relations)


def test_delete_missing_entity_returns_error(ps):
    ec = EntityController(ps)
    result = ec.delete("no-existe")
    assert isinstance(result, Error)


# ── Persistencia ──────────────────────────────────────────────────────────

def test_crud_roundtrip_persists(ps, tmp_path):
    ec = EntityController(ps)
    rc = RelationController(ps)
    ring = world_layer_ids(ps)[0]
    hoja = make_entity(ec, "Hoja persistente", layer_ids=[ring])
    rama = make_entity(ec, "Rama persistente", kind="contenedor")
    rc.create(rama, hoja, "contiene", {})

    path = tmp_path / "crud_beta1.json"
    save = ps.save(path)
    assert isinstance(save, Ok)
    ps.close()

    ps2 = ProjectService()
    reopened = ps2.open(path)
    assert isinstance(reopened, Ok)
    names = {e.name for e in ps2.active_project.entities}
    assert {"Hoja persistente", "Rama persistente"} <= names
    entity = next(e for e in ps2.active_project.entities if e.name == "Hoja persistente")
    assert ring in [str(v) for v in entity.layer_ids]
    assert any(r.kind if hasattr(r, "kind") else True for r in ps2.active_project.relations)
    assert len(ps2.active_project.relations) >= 1


# ── CRUD de anillos (capas-mundo) ─────────────────────────────────────────

def test_ring_create_update_hide_roundtrip(ps):
    from hosts.DesktopHostPySide.controllers.layer_controller import LayerController
    lc = LayerController(ps)
    created = lc.create({"name": "Anillo Nuevo", "description": "estrato de prueba"})
    assert isinstance(created, Ok), f"create layer failed: {getattr(created, 'error', '')}"
    ring_id = str(created.value.id)
    assert any(l.id == ring_id for l in lc.list_all())

    updated = lc.update(ring_id, {"name": "Anillo Editado", "order": 3, "metadata": {"causal_rank": "3"}})
    assert isinstance(updated, Ok), f"update layer failed: {getattr(updated, 'error', '')}"
    layer_obj = lc.get(ring_id).value
    assert layer_obj.name == "Anillo Editado"
    assert layer_obj.order == 3
    assert layer_obj.metadata.get("causal_rank") == "3"

    hidden = lc.hide(ring_id)
    assert isinstance(hidden, Ok)
    assert not any(l.id == ring_id for l in lc.list_all())  # soft-deleted
    # entities keep their layer ids; the layer object still exists hidden
    assert isinstance(lc.get(ring_id), Ok)


# ── Qt: menú 'Mover a anillo' ─────────────────────────────────────────────

pytest_qt_skip = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    if not HAS_QT:
        return None
    return QApplication.instance() or QApplication([])


def _layer(layer_id: str, name: str, rank: int):
    return SimpleNamespace(id=layer_id, name=name, metadata={"causal_rank": str(rank)}, is_visible=True, order=0)


def _node(entity_id: str, name: str, layer_id: str):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[layer_id]),
        entity_id=entity_id,
        name=name,
        kind="concepto",
        subtitle="",
        canon="canonico",
        visibility="publico",
        layer_id=layer_id,
    )


@pytest_qt_skip
def test_move_to_ring_menu_lists_other_rings_and_emits(qapp):
    view = GraphCanvasView()
    layers = [_layer("metafisica", "Metafísica", 1), _layer("politica", "Política", 5)]
    nodes = [_node("m1", "M1", "metafisica"), _node("p1", "P1", "politica")]
    view.set_graph(nodes, [], layout_mode="concentric_rings", layers=layers)

    received: list[tuple[str, str]] = []
    view.nodeAssignToRingRequested.connect(lambda eid, rid: received.append((eid, rid)))

    menu = view._node_context_menu(view._nodes["m1"])
    ring_menu = next(a for a in menu.actions() if a.text() == "Mover a anillo").menu()
    assert ring_menu is not None, "with rings present, 'Mover a anillo' must be a submenu"
    texts = [a.text() for a in ring_menu.actions()]
    assert texts == ["Política"]  # not its own ring, not unclassified
    ring_menu.actions()[0].trigger()
    assert received == [("m1", "politica")]
