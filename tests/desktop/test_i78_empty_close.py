"""I78 (desktop) — Cerrar el aviso de proyecto vacío ('Tu lienzo está por sembrar')."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_empty_state_has_close_button() -> None:
    canvas = GraphCanvasWidget(AppContext())
    assert canvas.empty.close_button is not None
    assert "Cerrar" in canvas.empty.close_button.text()


def test_close_button_has_no_mouse_transparent_ancestor() -> None:
    """Regresión BETA1-I78-FIX: el clic REAL debe llegar al botón. En Qt6 el hit-test
    omite el subárbol completo de cualquier ancestro WA_TransparentForMouseEvents, así
    que la tarjeta (y sus botones) no pueden colgar de un host mouse-transparente. El
    test previo con QTest.mouseClick no lo veía porque entrega el evento directo al
    botón, saltándose el hit-test."""
    canvas = GraphCanvasWidget(AppContext())
    widget = canvas.empty.close_button
    while widget is not None and widget is not canvas:
        assert not widget.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents), (
            f"{widget!r} es mouse-transparente; los clics no llegarían a 'Cerrar'"
        )
        widget = widget.parentWidget()


def test_close_hides_and_dismissal_persists() -> None:
    canvas = GraphCanvasWidget(AppContext())
    canvas._set_empty_visible(True)
    assert not canvas.empty.isHidden()

    QTest.mouseClick(canvas.empty.close_button, Qt.MouseButton.LeftButton)
    assert canvas.empty.isHidden()          # cerrado
    assert canvas._empty_dismissed is True

    canvas._set_empty_visible(True)          # intento de re-mostrar
    assert canvas.empty.isHidden()           # sigue oculto (respetado)
