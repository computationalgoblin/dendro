"""UI2-09: atmósfera de hojas en el Foco + ráfaga direccional y deslizamiento.

Las hojas de fondo (CanvasAtmosphere) llegan al lienzo del Foco; al recentrar,
una ráfaga empuja las hojas en la dirección de la transición y la tarjeta
entra deslizándose. Con el gate de animación cerrado (offscreen) todo queda
exactamente como antes: colocación instantánea, sin timers ni ráfagas.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


_CTX_STILL = SimpleNamespace(animation_duration=lambda default=220: 0)
_CTX_MOVING = SimpleNamespace(animation_duration=lambda default=220: default)


class TestGust:
    def _atmosphere(self, qapp, ctx):
        from hosts.DesktopHostPySide.widgets.canvas_atmosphere import CanvasAtmosphere
        from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoCanvas

        canvas = FocoCanvas()
        atmosphere = CanvasAtmosphere(canvas, ctx=ctx, count=5)
        return canvas, atmosphere

    def test_gust_is_noop_with_reduced_motion(self, qapp):
        canvas, atmosphere = self._atmosphere(qapp, _CTX_STILL)
        atmosphere._ensure()
        before = [(leaf["x"], leaf["y"], leaf["wx"]) for leaf in atmosphere._leaves]
        atmosphere.gust(1.0, 0.0)
        after = [(leaf["x"], leaf["y"], leaf["wx"]) for leaf in atmosphere._leaves]
        assert before == after
        assert not atmosphere._timer.isActive()
        canvas.deleteLater()

    def test_gust_pushes_leaves_and_decays(self, qapp):
        canvas, atmosphere = self._atmosphere(qapp, _CTX_MOVING)
        atmosphere._ensure()
        atmosphere.gust(1.0, 0.0)
        assert all(leaf["wx"] > 0 for leaf in atmosphere._leaves)
        xs = [leaf["x"] for leaf in atmosphere._leaves]
        wx = [leaf["wx"] for leaf in atmosphere._leaves]
        atmosphere._tick()
        assert all(leaf["x"] > x0 - 0.061 for leaf, x0 in zip(atmosphere._leaves, xs))
        assert all(leaf["wx"] < w0 for leaf, w0 in zip(atmosphere._leaves, wx))
        atmosphere.stop()
        canvas.deleteLater()

    def test_foco_canvas_owns_atmosphere(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_canvas import FocoCanvas

        canvas = FocoCanvas()
        assert canvas._atmosphere is not None
        canvas.set_atmosphere_context(_CTX_STILL)
        canvas.show()  # gate cerrado → el timer NO arranca
        assert not canvas._atmosphere._timer.isActive()
        canvas.hide()
        canvas.deleteLater()


def _setup_view(ctx_motion):
    project_service = ProjectService()
    project_service.create("Atmósfera")
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    ctx = SimpleNamespace(
        advanced_mode=False,
        log=lambda *args, **kwargs: None,
        animation_duration=ctx_motion.animation_duration,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        project_controller=SimpleNamespace(ps=project_service, current_path=None),
    )
    entity = NarrativeEntity(name="Eldrin")
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    view = FocoView(
        project_provider=lambda: project_service.active_project,
        ctx=ctx,
        entity_controller=EntityController(project_service),
    )
    view.resize(1000, 700)
    return view, entity


class TestTransition:
    def test_transition_direction_is_unit_vector(self, qapp):
        view, entity = _setup_view(_CTX_STILL)
        view.center_entity(entity.id)
        # Satélite fake muy a la izquierda del centro → dirección hacia la
        # derecha, siempre unitaria.
        view.canvas._items["fake"] = SimpleNamespace(pos=lambda: QPointF(-5000.0, 0.0))
        direction = view._transition_direction("fake")
        assert direction is not None
        assert math.hypot(*direction) == pytest.approx(1.0, abs=1e-6)
        assert direction[0] > 0
        assert view._transition_direction("no-existe") is None
        view.deleteLater()

    def test_closed_gate_places_card_instantly(self, qapp):
        view, entity = _setup_view(_CTX_STILL)
        view._pending_transition = (1.0, 0.0)
        view.center_entity(entity.id)
        assert view._center_anim is None  # sin animación pendiente
        assert view._pending_transition is None  # el hint se consume igualmente
        hole = view.canvas.center_hole_rect()
        assert view._center_card.x() == int(hole.x())
        view.deleteLater()

    def test_open_gate_starts_slide_and_gust(self, qapp):
        view, entity = _setup_view(_CTX_MOVING)
        view.canvas._atmosphere._ensure()
        view._pending_transition = (1.0, 0.0)
        view.center_entity(entity.id)
        assert view._center_anim is not None  # deslizamiento en curso
        hole = view.canvas.center_hole_rect()
        assert view._center_card.x() == int(hole.x()) - 28  # entra desde la izquierda
        assert all(leaf["wx"] > 0 for leaf in view.canvas._atmosphere._leaves)
        view._position_overlays()  # una recolocación explícita corta la animación
        assert view._center_anim is None
        assert view._center_card.x() == int(hole.x())
        view.canvas._atmosphere.stop()
        view.deleteLater()

    def test_navigation_paths_route_through_wind_wrapper(self, qapp):
        source = Path("hosts/DesktopHostPySide/widgets/foco/foco_view.py").read_text(
            encoding="utf-8"
        )
        assert "self.canvas.satelliteActivated.connect(self._on_satellite_activated)" in source
        assert "self._on_satellite_activated(target)" in source  # flechas
