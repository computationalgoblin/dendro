"""BETA2-CLEANUP-PANELES: RingPanel unificado + creación redirigida al Foco.

Cubre:
- ``RingPanel`` crea y edita anillos (un solo panel minimalista).
- Aserciones estáticas de que el cajón de detalle (Nodo/Rama) se retiró y la
  edición vive en el Modo Foco, y de que el acceso al panel de anillo desde el
  Foco (banner + rail) quedó cableado.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _layer_controller():
    from hosts.DesktopHostPySide.controllers.layer_controller import LayerController
    from packages.application.project_service import ProjectService

    ps = ProjectService()
    ps.create("RingPanel test")
    return LayerController(ps), ps


# ── RingPanel: un solo panel para crear y editar ──────────────────────────


def test_ring_panel_create_persists_layer(qapp):
    from hosts.DesktopHostPySide.views.workspaces import RingPanel

    controller, ps = _layer_controller()
    saved: list[bool] = []
    panel = RingPanel(controller, lambda: saved.append(True))
    panel.name.setText("Corte Nazarí")
    panel.order.setValue(3)
    panel.description.setPlainText("La corte del sultán")
    panel._save()

    assert saved == [True]
    names = [wl.name for wl in ps.active_project.world_layers]
    assert "Corte Nazarí" in names


def test_ring_panel_edit_prefills_and_updates_causal_rank(qapp):
    from hosts.DesktopHostPySide.views.workspaces import RingPanel
    from packages.application.world_layer_service import WorldLayerService

    controller, ps = _layer_controller()
    layer = WorldLayerService(ps).create_layer("Estrato", "desc", 2).value

    panel = RingPanel(controller, lambda: None, ring_id=layer.id)
    assert panel.name.text() == "Estrato"
    assert panel.order.value() == 2

    panel.name.setText("Estrato Nuevo")
    panel.order.setValue(5)
    panel._save()

    updated = next(wl for wl in ps.active_project.world_layers if wl.id == layer.id)
    assert updated.name == "Estrato Nuevo"
    assert updated.order == 5
    # Editar escribe causal_rank (la concéntrica ordena por rango causal).
    assert updated.metadata.get("causal_rank") == "5"


def test_ring_panel_empty_name_does_not_create(qapp):
    from hosts.DesktopHostPySide.views.workspaces import RingPanel

    controller, ps = _layer_controller()
    before = len(ps.active_project.world_layers)
    panel = RingPanel(controller, lambda: None)
    panel.name.setText("   ")
    panel._save()
    assert len(ps.active_project.world_layers) == before


# ── Estático: el cajón se retiró; edición y anillos accesibles en el Foco ──


def test_workspaces_redirects_creation_to_foco_and_drops_drawer():
    src = _read("hosts/DesktopHostPySide/views/workspaces.py")
    assert "def _focus_new_entity" in src
    assert "class RingPanel" in src
    # Los editores del cajón «Nodo»/«Rama» se retiraron por completo.
    assert "def _open_node_panel" not in src
    assert "def _open_tree_panel" not in src
    assert "class LayerQuickCreatePanel" not in src
    assert "class RingEditPanel" not in src


def test_graph_edit_action_opens_foco():
    src = _read("hosts/DesktopHostPySide/widgets/graph_canvas.py")
    # "Editar" del menú contextual entra en el Foco (ya no abre el cajón).
    assert "self.entityFocusRequested.emit(entity_id)" in src


def test_foco_banner_is_clickable():
    src = _read("hosts/DesktopHostPySide/widgets/foco/foco_canvas.py")
    assert "ringBannerClicked = Signal()" in src
    assert "def mousePressEvent" in src


def test_foco_view_exposes_ring_signals():
    src = _read("hosts/DesktopHostPySide/widgets/foco/foco_view.py")
    assert "ringEditRequested = Signal(str)" in src
    assert "ringCreateRequested = Signal()" in src
    assert "def _on_ring_banner_clicked" in src


def test_foco_tool_rail_has_create_ring():
    src = _read("hosts/DesktopHostPySide/widgets/foco/foco_tool_rail.py")
    assert '"create_ring"' in src
