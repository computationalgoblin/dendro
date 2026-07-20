"""BETA2-STRUCT (fix smoke): aceptar un ajuste estructural refresca el Mapa AL
INSTANTE. ``GraphCanvasWidget.refresh(full=True)`` SALTA el atajo incremental —
que, para un ``ring_move`` de una hoja (mismos ids/estructura, solo cambia el
anillo), la actualizaría in situ SIN reubicarla a su nuevo anillo.

Ejecutar POR ARCHIVO (offscreen): el directorio desktop completo segfaultea.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget

from packages.application.world_layer_causal import set_causal_rank
from packages.domain.entity import NarrativeEntity
from packages.domain.project import Project
from packages.domain.world_layer import WorldLayer

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ctx(project) -> SimpleNamespace:
    return SimpleNamespace(
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
        advanced_mode=False,
        creation_layout_mode="concentric_rings",
        creation_focused_ring_id="",
        selected_entity_id="",
        save_preferences=lambda: None,
        log=lambda *a, **k: None,
    )


def _project_with_node() -> Project:
    p = Project(id="p", name="P")
    ring = WorldLayer(id="ring_a", name="A")
    set_causal_rank(ring, 1)
    p.world_layers.append(ring)
    p.entities.append(NarrativeEntity(id="e1", name="E1", layer_ids=["ring_a"]))
    return p


def test_refresh_full_bypasses_incremental_shortcut(qapp):
    widget = GraphCanvasWidget(_ctx(_project_with_node()))
    widget.set_layout_mode("concentric_rings")  # primer refresh real dibuja el nodo

    calls = {"incremental": 0, "set_graph": 0}

    def _spy_incremental(*_a, **_k):
        calls["incremental"] += 1
        return True  # simula que el atajo SÍ aplicaría (dejaría el nodo en su sitio)

    def _spy_set_graph(*_a, **_k):
        calls["set_graph"] += 1

    widget.canvas.try_incremental_refresh = _spy_incremental
    widget.canvas.set_graph = _spy_set_graph

    # full=True: NO se intenta el atajo → rebuild completo (reubica por anillo).
    widget.refresh(full=True)
    assert calls["incremental"] == 0
    assert calls["set_graph"] == 1

    # full=False (defecto): sí intenta el atajo; como devuelve True, no hay rebuild.
    widget.refresh()
    assert calls["incremental"] == 1
    assert calls["set_graph"] == 1
