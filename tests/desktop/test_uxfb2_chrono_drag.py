"""BETA1-UX2C: edición gráfica del lapso de vida en la cronología.

Cubre el inverso de YearScale (year_at) y el arrastre simulado de los mangos de
origen/fin, que debe emitir ``lifespanEdited`` con los años correctos (y death=None
al bajar el fin al presente). Sin sintetizar QMouseEvent: se llaman los hooks
``_begin/_update/_finish_handle_drag`` directamente.
"""
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

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView, YearScale


# zoom_step es puro (sin Qt) → se prueba aunque no haya PySide6 instalado.
from hosts.DesktopHostPySide.widgets.chrono_canvas import zoom_step as _zoom_step  # noqa: E402


def test_zoom_step_allows_zoom_in_when_fit_made_scale_tiny():
    # BETA1-UX2D regresión: la cronología es muy alta; fit_all deja m11≈0.10
    # (por debajo del antiguo mínimo 0.12) y el gate combinado bloqueaba TODO
    # acercamiento. Ahora acercar desde 0.10 SÍ devuelve un factor (>1).
    factor = _zoom_step(0.10, zoom_in=True)
    assert factor is not None and factor > 1.0


def test_zoom_step_caps_at_extremes():
    # En el tope superior no acerca más; en el inferior no aleja más.
    assert _zoom_step(8.0, zoom_in=True) is None
    assert _zoom_step(0.02, zoom_in=False) is None
    # Pero alejar desde un nivel medio sí devuelve factor (<1).
    out = _zoom_step(1.0, zoom_in=False)
    assert out is not None and out < 1.0


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_year_scale_inverse_roundtrip(qapp):
    scale = YearScale([0, 80, 320, 400])
    for year in (0, 40, 80, 200, 320, 400):
        assert abs(scale.year_at(scale.y(year)) - year) <= 1


def _project(present=400, birth=10):
    chronology = SimpleNamespace(present_year=present, eras=[], metadata={})
    entity = SimpleNamespace(
        id="e1", name="El Jinn", entity_type="personaje", layer_ids=[],
        birth_year=birth, death_year=None, custom_metadata={},
    )
    return SimpleNamespace(
        entities=[entity], relations=[], world_layers=[],
        causal_milestones=[], project_chronology=chronology,
    )


def _view(qapp):
    view = ChronoCanvasView()
    view.set_project(_project())
    return view


def test_drag_death_handle_sets_death_year(qapp):
    view = _view(qapp)
    captured = []
    view.lifespanEdited.connect(lambda e, b, d: captured.append((e, b, d)))
    scale = view._layout.scale
    view._begin_handle_drag("e1", "death")
    view._update_handle_drag(scale.y(200))
    result = view._finish_handle_drag()
    assert result == ("e1", 10, 200)
    assert captured and captured[-1] == ("e1", 10, 200)


def test_drag_death_below_present_marks_alive(qapp):
    view = _view(qapp)
    captured = []
    view.lifespanEdited.connect(lambda e, b, d: captured.append((e, b, d)))
    scale = view._layout.scale
    present = view._layout.present_year
    view._begin_handle_drag("e1", "death")
    view._update_handle_drag(scale.y(present) + 60)  # por debajo del presente
    result = view._finish_handle_drag()
    assert result[2] is None  # sigue viva
    assert captured[-1][2] is None


def test_drag_birth_handle_sets_origin(qapp):
    view = _view(qapp)
    captured = []
    view.lifespanEdited.connect(lambda e, b, d: captured.append((e, b, d)))
    scale = view._layout.scale
    view._begin_handle_drag("e1", "birth")
    view._update_handle_drag(scale.y(150))
    result = view._finish_handle_drag()
    assert result[0] == "e1" and result[1] == 150
    assert captured[-1][1] == 150


def test_birth_cannot_exceed_present_when_alive(qapp):
    view = _view(qapp)
    scale = view._layout.scale
    present = view._layout.present_year
    view._begin_handle_drag("e1", "birth")
    view._update_handle_drag(scale.y(present + 500))  # intento pasarse del presente
    _eid, birth, _death = view._finish_handle_drag()
    assert birth <= present


def _move_event(x, y):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    pos = QPointF(x, y)
    return QMouseEvent(
        QEvent.Type.MouseMove, pos, pos,
        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )


def test_tiny_jitter_on_click_does_not_start_drag(qapp):
    # BETA1-UX2D (regresión "desaparece al clicar"): un temblor < umbral al clicar
    # NO debe iniciar el arrastre (que relocalizaría el mango lejos).
    view = _view(qapp)
    captured = []
    view.lifespanEdited.connect(lambda e, b, d: captured.append((e, b, d)))
    view._press_handle = ("e1", "birth")
    view._press_pos = _move_event(200, 200).position()
    view._handle_moved = False
    view._handle_drag = None
    # El temblor normal de un clic (≈3-10px) NO debe arrancar el arrastre: si lo
    # hiciera, el nodo saltaría años (alejado) y "desaparecería" al clicar.
    view.mouseMoveEvent(_move_event(202, 202))  # 4 px
    view.mouseMoveEvent(_move_event(200, 206))  # 6 px
    view.mouseMoveEvent(_move_event(204, 206))  # 10 px
    assert view._handle_drag is None and not view._handle_moved
    assert not captured
    # Un movimiento amplio y deliberado SÍ arranca el arrastre.
    view.mouseMoveEvent(_move_event(200, 260))  # 60 px > umbral
    assert view._handle_drag is not None and view._handle_moved


def test_chrono_uses_full_viewport_update(qapp):
    # BETA1-UX2D (items que "desaparecen" al clicar): en raster, el modo Minimal
    # dejaba zonas sin repintar; FullViewport repinta todo el viewport.
    from PySide6.QtWidgets import QGraphicsView

    view = ChronoCanvasView()
    assert view.viewportUpdateMode() == QGraphicsView.ViewportUpdateMode.FullViewportUpdate


def test_chrono_scene_has_no_bsp_index(qapp):
    # BETA1-UX2D (items que desaparecen al clicar y no vuelven hasta el rebuild):
    # el índice BSP quedaba obsoleto y el render saltaba items. NoIndex lo evita.
    from PySide6.QtWidgets import QGraphicsScene

    view = ChronoCanvasView()
    assert view.scene().itemIndexMethod() == QGraphicsScene.ItemIndexMethod.NoIndex


def test_set_project_survives_bad_data(qapp):
    # BETA1-UX2D (crash): si construir el layout lanza (datos inesperados), la
    # vista NO debe propagar (eso aborta la app); deja escena vacía y _layout None.
    class _Bomba:
        project_chronology = SimpleNamespace(present_year=0, eras=[], metadata={})
        relations: list = []
        world_layers: list = []
        causal_milestones: list = []

        @property
        def entities(self):
            raise RuntimeError("datos corruptos a propósito")

    view = ChronoCanvasView()
    view.set_project(_Bomba())  # no debe lanzar
    assert view._layout is None
    assert view._lifeline_views == {}
