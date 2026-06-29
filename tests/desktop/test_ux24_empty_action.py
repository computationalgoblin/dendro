"""Estado vacío del canvas con acción (BETA1-UX24)."""
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


def test_empty_state_tiene_accion_crear() -> None:
    canvas = GraphCanvasWidget(AppContext())
    assert canvas.empty.action_button is not None
    assert "Crear" in canvas.empty.action_button.text()


def test_accion_emite_crear_entidad() -> None:
    canvas = GraphCanvasWidget(AppContext())
    emitted = []
    canvas.contextCreateEntityRequested.connect(lambda: emitted.append(True))
    QTest.mouseClick(canvas.empty.action_button, Qt.MouseButton.LeftButton)
    assert emitted == [True]
