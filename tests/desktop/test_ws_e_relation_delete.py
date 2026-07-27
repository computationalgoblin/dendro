"""BETA-CIERRE WS-E: eliminar una relación desde el Foco.

La pestaña Relaciones del Foco listaba las relaciones (clic → dual) pero no había
forma de borrar una relación mal creada sin ir al Mapa. Ahora cada fila lleva un
«×» que delega en el workspace (confirmación + controller; el panel no escribe
persistencia).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QToolButton  # noqa: E402

from packages.domain.result import Error, Ok  # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _ctx_with_relation():
    ent_a = SimpleNamespace(id="a", name="Ana")
    ent_b = SimpleNamespace(id="b", name="Beto")
    rel = SimpleNamespace(
        id="r1", source_id="a", target_id="b", relation_type="aliado",
        direction="unidireccional", canon_state="canonico",
    )
    proj = SimpleNamespace(entities=[ent_a, ent_b], relations=[rel])
    return SimpleNamespace(
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=proj))
    )


def _delete_buttons(panel):
    return [b for b in panel.findChildren(QToolButton) if b.text() == "×"]


def test_panel_has_no_delete_without_callback(app):
    from hosts.DesktopHostPySide.widgets.foco.relations_panel import FocoRelationsPanel

    panel = FocoRelationsPanel(_ctx_with_relation(), "a")
    assert _delete_buttons(panel) == []  # sin callback → sin ×


def test_panel_delete_button_invokes_callback(app):
    from hosts.DesktopHostPySide.widgets.foco.relations_panel import FocoRelationsPanel

    got = []
    panel = FocoRelationsPanel(
        _ctx_with_relation(), "a", on_delete_relation=lambda rid: got.append(rid)
    )
    btns = _delete_buttons(panel)
    assert len(btns) == 1  # una relación → un ×
    btns[0].click()
    assert got == ["r1"]


def _workspace(relation_controller, monkeypatch, *, answer):
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: answer))
    ws = CreationWorkspace.__new__(CreationWorkspace)
    ws.relation_controller = relation_controller
    ws.refreshed = 0

    class _Ctx:
        def log(self, *a, **k):
            pass

        def notify(self, *a, **k):
            pass

    ws.ctx = _Ctx()
    ws.refresh = lambda: setattr(ws, "refreshed", ws.refreshed + 1)
    return ws


def test_workspace_delete_confirms_deletes_and_refreshes(app, monkeypatch):
    deleted = []

    class _RC:
        def delete(self, rid):
            deleted.append(rid)
            return Ok(None)

    ws = _workspace(_RC(), monkeypatch, answer=QMessageBox.StandardButton.Yes)
    ws._delete_relation_from_foco("r1")
    assert deleted == ["r1"]
    assert ws.refreshed == 1


def test_workspace_delete_cancelled(app, monkeypatch):
    deleted = []

    class _RC:
        def delete(self, rid):
            deleted.append(rid)
            return Ok(None)

    ws = _workspace(_RC(), monkeypatch, answer=QMessageBox.StandardButton.No)
    ws._delete_relation_from_foco("r1")
    assert deleted == []  # cancelado → no borra
    assert ws.refreshed == 0


def test_workspace_delete_error_does_not_refresh(app, monkeypatch):
    class _RC:
        def delete(self, rid):
            return Error("boom")

    ws = _workspace(_RC(), monkeypatch, answer=QMessageBox.StandardButton.Yes)
    ws._delete_relation_from_foco("r1")
    assert ws.refreshed == 0  # un fallo no refresca (ni finge éxito)
