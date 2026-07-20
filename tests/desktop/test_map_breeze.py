"""Brisa del Mapa (BETA2-PULIDO-07): gates del canvas y jardín congelado."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _node_view(entity_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=entity_id,
        name=entity_id,
        kind="personaje",
        color=None,
        proposed=False,
        canon="borrador",
        visibility="publico",
        is_event=False,
        image_path="",
        image_crop=None,
    )


def _view_with_bodies(qapp, reports):
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView, GraphNodeItem

    view = GraphCanvasView()
    for entity_id in reports:
        view._nodes[entity_id] = GraphNodeItem(_node_view(entity_id), x=0.0, y=0.0)
    view.set_garden_status_provider(lambda ids: reports)
    view._rebuild_physics_world()
    return view


def _report(status: str) -> SimpleNamespace:
    return SimpleNamespace(status=status, latest=None, stale=False)


class TestMapBreeze:
    def test_breeze_moves_live_and_skips_frozen(self, qapp):
        view = _view_with_bodies(
            qapp, {"viva": _report("regada"), "seca": _report("falta_regar")}
        )
        view.show()  # la brisa exige vista visible
        view._blow_breeze()
        assert view._physics_engine.bodies["seca"].vx == 0.0
        live = view._physics_engine.bodies["viva"]
        assert (live.vx, live.vy) != (0.0, 0.0)
        assert view._breeze_timer.isActive()  # la siguiente ráfaga queda armada
        view.hide()

    def test_closed_gate_or_disabled_physics_blocks_the_breeze(self, qapp):
        view = _view_with_bodies(qapp, {"viva": _report("regada")})
        view.show()
        view.set_motion_gate(lambda: False)  # modo sin animación
        view._blow_breeze()
        live = view._physics_engine.bodies["viva"]
        assert (live.vx, live.vy) == (0.0, 0.0)
        assert view._breeze_timer.isActive()  # se re-arma igualmente

        view.set_motion_gate(None)
        view._physics_enabled = False
        view._blow_breeze()
        assert (live.vx, live.vy) == (0.0, 0.0)
        view.hide()

    def test_drag_in_progress_blocks_the_breeze(self, qapp):
        view = _view_with_bodies(qapp, {"viva": _report("regada")})
        view.show()
        view._physics_drag_freeze = True
        view._blow_breeze()
        live = view._physics_engine.bodies["viva"]
        assert (live.vx, live.vy) == (0.0, 0.0)
        view.hide()
