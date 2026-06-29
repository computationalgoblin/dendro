"""Indicador de carga reutilizable (BETA1-UX11).

Verifica el componente ``BusyIndicator``: arranca/para, refleja su estado, se
oculta al parar, no usa QGraphicsEffect (regla canvas-safe, lección G08) y pinta
sin romperse mientras gira.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.widgets.design_system import BusyIndicator


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_estado_inicial_parado_y_oculto() -> None:
    ind = BusyIndicator()
    assert ind.is_running() is False
    assert ind.isHidden() is True


def test_start_arranca_y_muestra() -> None:
    ind = BusyIndicator()
    ind.start()
    assert ind.is_running() is True
    assert ind.isHidden() is False


def test_stop_para_y_oculta() -> None:
    ind = BusyIndicator()
    ind.start()
    ind.stop()
    assert ind.is_running() is False
    assert ind.isHidden() is True


def test_stop_idempotente() -> None:
    ind = BusyIndicator()
    ind.stop()
    ind.stop()  # no debe lanzar
    assert ind.is_running() is False


def test_no_usa_graphics_effect() -> None:
    # Canvas-safe: jamás QGraphicsDropShadow/Opacity effect en widget dinámico.
    ind = BusyIndicator()
    ind.start()
    assert ind.graphicsEffect() is None


def test_set_period_ms_clampa_minimo() -> None:
    ind = BusyIndicator()
    ind.set_period_ms(0)
    # No explota y sigue siendo dibujable: un tick avanza el ángulo sin dividir por 0.
    ind.start()
    ind._tick()  # avance manual de un fotograma
    assert ind.is_running() is True


def test_pinta_sin_romperse_mientras_gira() -> None:
    ind = BusyIndicator(diameter=24)
    ind.start()
    ind._tick()
    img = ind.grab().toImage()  # fuerza paintEvent
    assert not img.isNull()
    assert img.width() > 0 and img.height() > 0
