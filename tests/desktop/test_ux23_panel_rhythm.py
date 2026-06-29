"""Ritmo exterior tokenizado en paneles de detalle (BETA1-UX23)."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
from hosts.DesktopHostPySide.widgets import design_system as ds
from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel
from packages.application.project_service import ProjectService
from packages.domain.result import Ok


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _ctx_with_project():
    ps = ProjectService()
    assert isinstance(ps.create("UX23"), Ok)
    ctx = AppContext()
    ctx.set_advanced_mode(False)
    ctx.project_controller = SimpleNamespace(ps=ps)
    return ctx, ps, EntityController(ps), RelationController(ps)


def _create_entity(ec, name, **extra):
    result = ec.create(
        {
            "name": name,
            "entity_type": "personaje",
            "brief_description": "",
            "canon_state": "borrador",
            **extra,
        }
    )
    assert isinstance(result, Ok)
    return result.value


def _assert_root_rhythm(panel) -> None:
    m = panel.layout().contentsMargins()
    assert (m.left(), m.top(), m.right(), m.bottom()) == (
        ds.SPACE_LG, ds.SPACE_LG, ds.SPACE_LG, ds.SPACE_LG
    )
    assert panel.layout().spacing() == ds.SPACE_MD


def test_node_panel_root_usa_tokens(_app):
    ctx, ps, ec, _rc = _ctx_with_project()
    entity = _create_entity(ec, "Eldrin")
    panel = NodeDetailPanel(ctx, ec, entity.id, on_saved=lambda: None)
    _assert_root_rhythm(panel)


def test_relation_panel_root_usa_tokens(_app):
    ctx, ps, ec, rc = _ctx_with_project()
    a = _create_entity(ec, "A")
    b = _create_entity(ec, "B")
    rel = rc.create(a.id, b.id, "es_aliado_de")
    rel_id = rel.value.id if isinstance(rel, Ok) else rel.id
    panel = RelationDetailPanel(ctx, rc, rel_id, on_saved=lambda: None)
    _assert_root_rhythm(panel)
