"""BETA-CIERRE WS-E: borrar la entidad en foco desde el Modo Foco.

Antes solo se podía borrar desde el Mapa; en la vista PRINCIPAL de Creación (Foco) no
había forma de eliminar una entidad mal creada. Ahora el rail tiene una herramienta de
borrado que enruta por EntityController (con confirmación), la misma vía que el Mapa.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from packages.domain.result import Error, Ok  # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_rail_delete_tool_enabled_only_with_center(app):
    from hosts.DesktopHostPySide.widgets.foco.foco_tool_rail import FocoToolRail

    rail = FocoToolRail()
    rail.set_selection_context({"has_project": True, "center_id": "e1"})
    assert rail.button("delete_focus") is not None
    assert rail.button("delete_focus").isEnabled()  # con entidad en foco

    rail.set_selection_context({"has_project": True})  # sin centro
    assert not rail.button("delete_focus").isEnabled()


def _make_ws(entity_controller):
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    ws = CreationWorkspace.__new__(CreationWorkspace)  # sin construir el QWidget completo
    ws.entity_controller = entity_controller
    ws.refreshed = 0

    class _Ctx:
        def log(self, *a, **k):
            pass

        def notify(self, *a, **k):
            pass

    class _Proj:
        def entity_by_id(self, eid):
            return type("E", (), {"name": "Ana"})()

    ws.ctx = _Ctx()
    ws._get_active_project = lambda: _Proj()
    ws.refresh = lambda: setattr(ws, "refreshed", ws.refreshed + 1)
    return ws


def test_delete_confirms_deletes_and_refreshes(app, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    deleted = []

    class _EC:
        def delete(self, eid):
            deleted.append(eid)
            return Ok(None)

    ws = _make_ws(_EC())
    ws._delete_entity_from_foco("e1")
    assert deleted == ["e1"]
    assert ws.refreshed == 1


def test_delete_cancelled_when_user_declines(app, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    )
    deleted = []

    class _EC:
        def delete(self, eid):
            deleted.append(eid)
            return Ok(None)

    ws = _make_ws(_EC())
    ws._delete_entity_from_foco("e1")
    assert deleted == []  # no se borra si el usuario cancela
    assert ws.refreshed == 0


def test_delete_error_notifies_and_does_not_refresh(app, monkeypatch):
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )

    class _EC:
        def delete(self, eid):
            return Error("boom")

    ws = _make_ws(_EC())
    ws._delete_entity_from_foco("e1")
    assert ws.refreshed == 0  # un fallo no refresca (ni finge éxito)
