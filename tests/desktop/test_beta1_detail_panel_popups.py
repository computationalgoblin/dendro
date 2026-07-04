from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


ROOT = Path(__file__).resolve().parents[2]
HAS_QT = importlib.util.find_spec("PySide6") is not None


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_detail_panels_do_not_keep_removed_causal_controls():
    node_panel = _read("hosts/DesktopHostPySide/widgets/node_detail_panel.py")
    tree_panel = _read("hosts/DesktopHostPySide/widgets/tree_detail_panel.py")
    relation_panel = _read("hosts/DesktopHostPySide/widgets/relation_detail_panel.py")

    for text in (node_panel, tree_panel, relation_panel):
        assert "Destino causal" not in text
        assert "Expandir hacia anillo inferior" not in text
        assert "Explicar desde causas superiores" not in text
        assert "_refresh_target_layer_combo" not in text

    assert "self.layer_combo" in node_panel
    assert "self.layer_combo" in tree_panel


def test_unmounted_technical_boxes_are_parented_and_never_shown():
    node_panel = _read("hosts/DesktopHostPySide/widgets/node_detail_panel.py")
    relation_panel = _read("hosts/DesktopHostPySide/widgets/relation_detail_panel.py")

    # BETA2-UX-03: las cajas «Datos técnicos» (sin montar, dato-no-UI) se
    # eliminaron por completo — ya no existe el widget.
    for text in (node_panel, relation_panel):
        assert "technical_box" not in text
        assert "technical_text" not in text


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_refreshing_detail_panels_does_not_spawn_top_level_popouts():
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

    from hosts.DesktopHostPySide.app_context import AppContext
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel
    from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel
    from hosts.DesktopHostPySide.widgets.tree_detail_panel import TreeDetailPanel
    from packages.application.project_service import ProjectService
    from packages.application.world_layer_service import WorldLayerService
    from packages.domain.result import Ok

    app = QApplication.instance() or QApplication([])
    project_service = ProjectService()
    assert isinstance(project_service.create("F00C popout regression"), Ok)
    project_service.active_project.worldbuilding_active = True
    layer = WorldLayerService(project_service).create_layer("Anillo visible").value

    ctx = AppContext()
    ctx.set_advanced_mode(False)
    ctx.project_controller = type("ProjectControllerStub", (), {"ps": project_service})()
    entity_controller = EntityController(project_service)
    relation_controller = RelationController(project_service)
    leaf = entity_controller.create({
        "name": "Hoja",
        "entity_type": "nota",
        "canon_state": "borrador",
        "layer_ids": [layer.id],
    }).value
    branch = entity_controller.create({
        "name": "Rama",
        "entity_type": "contenedor",
        "canon_state": "borrador",
        "layer_ids": [layer.id],
    }).value
    relation = relation_controller.create(
        leaf.id,
        branch.id,
        "esta_relacionado_con",
        {"description": ""},
    ).value

    cases = [
        ("leaf", lambda: NodeDetailPanel(ctx, entity_controller, leaf.id)),
        ("branch", lambda: TreeDetailPanel(ctx, entity_controller, relation_controller, branch.id)),
        ("relation", lambda: RelationDetailPanel(ctx, relation_controller, relation.id)),
    ]
    for label, factory in cases:
        baseline = set(app.topLevelWidgets())
        host = QWidget()
        host.setObjectName(f"host_{label}")
        layout = QVBoxLayout(host)
        panel = factory()
        layout.addWidget(panel)
        host.show()
        panel.refresh()
        app.processEvents()

        extra = [
            widget for widget in app.topLevelWidgets()
            if widget not in baseline and widget is not host and widget.isVisible()
        ]
        try:
            assert extra == []
        finally:
            host.close()
            panel.deleteLater()
            host.deleteLater()
            app.processEvents()


@pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")
def test_right_drawer_replaces_content_without_detached_visible_widget():
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    from hosts.DesktopHostPySide.widgets.right_drawer import RightDrawer

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.resize(1000, 720)
    layout = QVBoxLayout(host)
    drawer = RightDrawer(host)
    layout.addWidget(drawer)
    host.show()

    first = QLabel("Primer panel")
    second = QLabel("Segundo panel")
    drawer.set_content(first, title="Primero")
    drawer.open()
    app.processEvents()

    drawer.set_content(second, title="Segundo")

    try:
        assert first.isVisible() is False
        assert first.parent() is drawer
        assert second.graphicsEffect() is None
        assert second.isVisible() is True
        assert drawer._scroll.widget() is second
    finally:
        host.close()
        first.deleteLater()
        second.deleteLater()
        drawer.deleteLater()
        host.deleteLater()
        app.processEvents()
