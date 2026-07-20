"""BETA2-CAL-06 — CalendarEditorDialog: diálogo ancho de edición del calendario.

Verifica que carga la vista del controller, que al guardar delega en
``configure_calendar`` con el payload del editor y avisa a ``on_saved``, y que no
escribe persistencia directa (todo pasa por el controller inyectado).
"""

from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.calendar_editor_dialog import CalendarEditorDialog
    from packages.domain.result import Ok


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeController:
    def __init__(self, view):
        self._view = view
        self.saved_payload = None

    def calendar_view(self):
        return Ok(self._view)

    def configure_calendar(self, payload):
        self.saved_payload = payload
        return Ok(None)


def test_dialog_loads_view_and_saves(qapp):
    view = {
        "calendar_name": "Cal",
        "description": "",
        "eras": [{"name": "A", "duration": 30}, {"name": "B", "duration": 100}],
        "present": {"era_index": 1, "year_within": 5, "month": "", "day": 1},
        "months": [],
        "weekdays": [],
        "week_anchor": 0,
    }
    controller = _FakeController(view)
    calls = []
    dialog = CalendarEditorDialog(controller, on_saved=lambda: calls.append(True))

    # Cargó la vista en el editor embebido.
    loaded = dialog.panel.editor.value()
    assert [e["name"] for e in loaded["eras"]] == ["A", "B"]
    assert loaded["present"]["era_index"] == 1

    # Guardar delega en el controller y avisa a on_saved (y cierra el diálogo).
    dialog.panel.save()
    assert controller.saved_payload is not None
    assert [e["duration"] for e in controller.saved_payload["eras"]] == [30, 100]
    assert calls == [True]
