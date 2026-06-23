"""Movimiento de cámara del canvas (BETA1-UX06).

Las transiciones explícitas (encajar, centrar, enfocar) se deslizan en vez de
saltar. Verifica que: (a) en modo instantáneo la cámara llega al encuadre que
produciría fitInView, y (b) en modo animado se crea una animación que interpola
hasta ese mismo objetivo.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF, QVariantAnimation
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.widgets import graph_canvas as gc


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _view_con_contenido() -> gc.GraphCanvasView:
    view = gc.GraphCanvasView()
    view.resize(800, 600)
    view.scene_obj.addRect(QRectF(400, 300, 320, 240))
    return view


def test_modo_instantaneo_llega_al_encuadre_objetivo(monkeypatch) -> None:
    view = _view_con_contenido()
    monkeypatch.setattr(gc, "MOTION_ENABLED", False)
    rect = QRectF(400, 300, 320, 240)
    target_scale, _ = view._camera_fit_target(rect)
    view._animate_camera_fit(rect)
    assert abs(view.transform().m11() - target_scale) < 1e-3


def test_modo_animado_interpola_hasta_el_objetivo(monkeypatch) -> None:
    view = _view_con_contenido()
    view.show()  # offscreen: la hace "visible" para tomar la ruta animada
    QApplication.processEvents()
    monkeypatch.setattr(gc, "MOTION_ENABLED", True)

    rect = QRectF(1200, 1000, 360, 300)
    target_scale, _ = view._camera_fit_target(rect)
    start_scale = view.transform().m11()
    view._animate_camera_fit(rect)

    anim = getattr(view, "_camera_anim", None)
    if anim is None:
        pytest.skip("entorno sin viewport con tamaño: ruta instantánea")
    assert isinstance(anim, QVariantAnimation)
    # A mitad de la animación la escala ya cambió respecto al inicio…
    anim.setCurrentTime(gc._CAM_MS // 2)
    mid_scale = view.transform().m11()
    assert abs(mid_scale - start_scale) > 1e-4
    # …y al final aterriza en el objetivo.
    anim.setCurrentTime(gc._CAM_MS)
    assert abs(view.transform().m11() - target_scale) < 1e-2
