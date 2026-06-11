"""BETA1-B05: default Creation layout is concentric without auto-template."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import hosts.DesktopHostPySide.app_context as app_context
from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.project_controller import ProjectController
from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget
from packages.application.project_service import ProjectService
from packages.domain.result import Ok
from packages.domain.world_layer import WorldLayer
from packages.persistence.store import ProjectStore

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False


@pytest.fixture()
def qapp():
    if not HAS_QT:
        pytest.skip("PySide6 no disponible")
    return QApplication.instance() or QApplication([])


def test_app_context_defaults_creation_to_concentric_without_preferences(tmp_path, monkeypatch):
    monkeypatch.setattr(app_context, "PREFERENCES_PATH", tmp_path / "missing-settings.json")

    ctx = AppContext()

    assert ctx.creation_layout_mode == "concentric_rings"


def test_app_context_ignores_legacy_free_layout_preference(tmp_path, monkeypatch):
    prefs = tmp_path / "settings.json"
    prefs.write_text('{"creation_layout_mode": "free"}', encoding="utf-8")
    monkeypatch.setattr(app_context, "PREFERENCES_PATH", prefs)

    ctx = AppContext()

    assert ctx.creation_layout_mode == "concentric_rings"


def test_empty_project_does_not_auto_apply_default_world_layers(qapp):
    project = SimpleNamespace(world_layers=[], entities=[], relations=[])
    ctx = SimpleNamespace(
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
        advanced_mode=False,
        creation_layout_mode="concentric_rings",
        creation_focused_ring_id="",
        selected_entity_id="",
        save_preferences=lambda: None,
        log=lambda *args, **kwargs: None,
    )
    widget = GraphCanvasWidget(ctx)

    widget.refresh()

    assert widget.canvas._layout_mode_active == "concentric_rings"
    assert widget.canvas._ring_items == {}
    assert project.world_layers == []


def test_project_service_new_project_starts_without_world_layers():
    service = ProjectService()

    created = service.create("Beta desde cero")
    assert isinstance(created, Ok)

    assert service.active_project is not None
    assert service.active_project.world_layers == []


def test_single_user_ring_does_not_pull_default_template(qapp):
    ring = WorldLayer(id="layer_user_alpha", name="Anillo propio", order=1, is_default=False)
    project = SimpleNamespace(world_layers=[ring], entities=[], relations=[])
    ctx = SimpleNamespace(
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
        advanced_mode=False,
        creation_layout_mode="concentric_rings",
        creation_focused_ring_id="",
        selected_entity_id="",
        save_preferences=lambda: None,
        log=lambda *args, **kwargs: None,
    )
    widget = GraphCanvasWidget(ctx)

    widget.refresh()

    assert widget.canvas._layout_mode_active == "concentric_rings"
    assert set(widget.canvas._ring_items) == {"layer_user_alpha"}
    assert [layer.id for layer in project.world_layers] == ["layer_user_alpha"]


def test_desktop_new_project_starts_without_world_layers(tmp_path):
    path = tmp_path / "beta1_new_project.json"
    controller = ProjectController(store=ProjectStore())

    created = controller.create("Beta sin plantilla", str(path))
    assert isinstance(created, Ok)

    project = controller.ps.active_project
    assert project is not None
    assert project.world_layers == []

    saved = controller.save()
    assert isinstance(saved, Ok)

    reopened = ProjectController(store=ProjectStore())
    reopened.open(str(path))
    assert reopened.ps.active_project is not None
    assert reopened.ps.active_project.world_layers == []
