"""Empty states ricos con acción sugerida (BETA1-UX19)."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.widgets.design_system import EmptyState


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_sin_accion_es_retrocompatible() -> None:
    es = EmptyState("Sin entidades", "Aún no hay nada aquí.")
    assert es.action_button is None


def test_con_accion_crea_boton_y_dispara_callback() -> None:
    clicks = []
    es = EmptyState(
        "Sin entidades",
        "Empieza tu mundo.",
        action_text="Crea tu primera entidad",
        on_action=lambda: clicks.append(True),
    )
    assert es.action_button is not None
    assert es.action_button.text() == "Crea tu primera entidad"
    QTest.mouseClick(es.action_button, Qt.MouseButton.LeftButton)
    assert clicks == [True]


def test_action_text_sin_callback_no_crea_boton() -> None:
    # Un botón sin acción sería un botón muerto: no se crea.
    es = EmptyState("Vacío", "x", action_text="Acción")
    assert es.action_button is None
