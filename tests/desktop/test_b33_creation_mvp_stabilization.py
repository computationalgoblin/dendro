from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")

if HAS_QT:
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.app_context import AppContext
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
    from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel
    from packages.application.project_service import ProjectService
    from packages.domain.result import Error, Ok


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _ctx_with_project(name="B33-T03"):
    ps = ProjectService()
    assert isinstance(ps.create(name), Ok)
    ctx = AppContext()
    ctx.set_advanced_mode(False)
    ctx.project_controller = SimpleNamespace(ps=ps)
    return ctx, ps, EntityController(ps), RelationController(ps)


def _create_entity(ec, name):
    result = ec.create({
        "name": name,
        "entity_type": "personaje",
        "brief_description": "",
        "canon_state": "borrador",
        "custom_metadata": {"_node_color": "#7EC8A5"},
    })
    assert isinstance(result, Ok)
    return result.value


def _create_relation(rc, source_id, target_id):
    result = rc.create(source_id, target_id, "esta_relacionado_con", {
        "description": "",
        "custom_metadata": {"_visual_draft": True, "_edge_color": "#A4AEC0"},
    })
    assert isinstance(result, Ok)
    return result.value


def test_draft_entity_cancel_removes_node(qapp):
    ctx, ps, ec, _rc = _ctx_with_project()
    draft = ec.create({
        "name": "A",
        "entity_type": "nota",
        "canon_state": "borrador",
        "custom_metadata": {"_visual_draft": True},
    })
    assert isinstance(draft, Ok)
    assert len(ps.active_project.entities) == 1

    panel = NodeDetailPanel(ctx, ec, draft.value.id, on_saved=lambda: None, is_new=True)
    panel._cancel()

    assert ps.active_project.entities == []
    assert ps.active_project.relations == []


def test_draft_entity_save_leaves_single_persisted_node(qapp, tmp_path):
    ctx, ps, ec, _rc = _ctx_with_project()
    draft = ec.create({
        "name": "A",
        "entity_type": "nota",
        "canon_state": "borrador",
        "custom_metadata": {"_visual_draft": True, "_node_color": "#7EC8A5"},
    })
    assert isinstance(draft, Ok)

    panel = NodeDetailPanel(ctx, ec, draft.value.id, on_saved=lambda: None, is_new=True)
    panel.name_edit.setText("A")
    panel.brief_edit.setPlainText("Entidad guardada")
    panel.save()

    assert len(ps.active_project.entities) == 1
    entity = ps.active_project.entities[0]
    assert entity.name == "A"
    assert entity.custom_metadata.get("_node_color") == "#7EC8A5"
    assert "_visual_draft" not in entity.custom_metadata

    path = tmp_path / "entity-save.dendro.json"
    assert isinstance(ps.save(path), Ok)
    ps.close()
    reopened = ps.open(path)
    assert isinstance(reopened, Ok)
    assert len(reopened.value.entities) == 1
    assert reopened.value.entities[0].name == "A"
    assert reopened.value.entities[0].custom_metadata.get("_node_color") == "#7EC8A5"


def test_draft_relation_cancel_and_save_lifecycle(qapp):
    ctx, ps, ec, rc = _ctx_with_project()
    a = _create_entity(ec, "A")
    b = _create_entity(ec, "B")

    draft = _create_relation(rc, a.id, b.id)
    assert len(ps.active_project.relations) == 1
    cancel_panel = RelationDetailPanel(ctx, rc, draft.id, on_saved=lambda: None, is_new=True)
    cancel_panel._cancel()
    assert ps.active_project.relations == []

    draft = _create_relation(rc, a.id, b.id)
    save_panel = RelationDetailPanel(ctx, rc, draft.id, on_saved=lambda: None, is_new=True)
    save_panel.type_combo.setCurrentText("servidumbre")
    save_panel.description_edit.setPlainText("A sirve a B")
    save_panel.body_edit.setPlainText("Texto de relación")
    save_panel.notes_edit.setPlainText("Notas privadas")
    save_panel._update_color_swatch("#7EC8A5")
    save_panel.save()

    assert len(ps.active_project.relations) == 1
    relation = ps.active_project.relations[0]
    assert relation.description == "A sirve a B"
    assert relation.custom_metadata["_body"] == "Texto de relación"
    assert relation.custom_metadata["_notes"] == "Notas privadas"
    assert relation.custom_metadata["_edge_color"] == "#7EC8A5"
    assert "_visual_draft" not in relation.custom_metadata


def test_ai_discarded_not_persisted_and_accepted_persisted_after_save(qapp, tmp_path):
    ctx, ps, ec, rc = _ctx_with_project()
    a = _create_entity(ec, "A")
    b = _create_entity(ec, "B")
    relation = _create_relation(rc, a.id, b.id)
    panel = RelationDetailPanel(ctx, rc, relation.id, on_saved=lambda: None, is_new=True)

    panel.suggestion_text.setPlainText("Texto descartado")
    panel.suggestion_frame.setVisible(True)
    panel._discard_suggestion()
    panel.save()
    assert "Texto descartado" not in str(ps.active_project.to_dict())

    panel.suggestion_text.setPlainText("Texto aceptado")
    panel.suggestion_frame.setVisible(True)
    panel._accept_suggestion()
    assert "Texto aceptado" not in str(ps.active_project.to_dict())
    panel.save()

    path = tmp_path / "accepted-ai.dendro.json"
    assert isinstance(ps.save(path), Ok)
    ps.close()
    reopened = ps.open(path)
    assert isinstance(reopened, Ok)
    assert len(reopened.value.relations) == 1
    assert reopened.value.relations[0].custom_metadata.get("_body") == "Texto aceptado"
    assert "Texto descartado" not in str(reopened.value.to_dict())


def test_graph_rebuild_no_duplicate_edges_and_handle_selectable_after_reload(qapp, tmp_path):
    ctx, ps, ec, rc = _ctx_with_project()
    a = _create_entity(ec, "A")
    b = _create_entity(ec, "B")
    relation = _create_relation(rc, a.id, b.id)
    RelationDetailPanel(ctx, rc, relation.id, on_saved=lambda: None, is_new=True).save()

    path = tmp_path / "graph-reload.dendro.json"
    assert isinstance(ps.save(path), Ok)
    ps.close()
    reopened = ps.open(path)
    assert isinstance(reopened, Ok)

    graph = GraphCanvasWidget(ctx)
    captured = []
    graph.relationSelected.connect(captured.append)
    graph.refresh()
    graph.refresh()

    assert len(graph.canvas._nodes) == 2
    assert len(graph.canvas._edges) == 1
    edge = graph.canvas._edges[0]
    assert edge.handle_item.toolTip() == ""
    graph.canvas._set_single_edge_selection(edge)
    graph.canvas.relationSelected.emit(edge.edge.relation_id)
    assert graph.selected_relation_ids() == [edge.edge.relation_id]
    assert captured == [edge.edge.relation_id]
