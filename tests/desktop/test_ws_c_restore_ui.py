"""BETA-CIERRE WS-C (rest): fallo de apertura visible + restaurar copia `.bak` en UI.

Antes, un fallo al abrir iba solo a la barra de estado (parecía olvido de datos) y las
copias `.bak` no tenían forma de restaurarse desde la app. Ahora el fallo ofrece
restaurar la copia más reciente (vía ProjectMaintenanceService).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402
from packages.domain.project import Project  # noqa: E402
from packages.persistence.store import ProjectStore  # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")


def _auto_click_restore(monkeypatch):
    """Hace que el diálogo modal 'auto-pulse' el botón de rol Accept (Restaurar)."""
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    orig_add = QMessageBox.addButton

    def _add(self, *a, **k):
        btn = orig_add(self, *a, **k)
        if a and a[-1] == QMessageBox.ButtonRole.AcceptRole:
            self._accept_btn = btn
        return btn

    monkeypatch.setattr(QMessageBox, "addButton", _add)
    monkeypatch.setattr(
        QMessageBox, "clickedButton", lambda self: getattr(self, "_accept_btn", None)
    )


def test_open_failure_offers_backup_restore(app, tmp_path, monkeypatch):
    from hosts.DesktopHostPySide.main_window import MainWindow

    path = tmp_path / "mundo.json"
    store = ProjectStore()
    store.save(Project(name="Bueno"), path)  # v1 crea el fichero (sin backup aún)
    store.save(Project(name="Bueno v2"), path)  # v2 crea .bak con el estado v1
    path.write_text("{ esto no es json", encoding="utf-8")  # corromper el principal

    _auto_click_restore(monkeypatch)
    w = MainWindow()
    try:
        w._open_project_path(str(path))
        loaded = w.controller.ps.active_project
        assert loaded is not None, "debería haberse restaurado desde .bak"
        assert loaded.name in ("Bueno", "Bueno v2")
    finally:
        w.controller.close()
        w.close()
        app.processEvents()


def test_offer_backup_restore_returns_false_without_backups(app, tmp_path):
    from hosts.DesktopHostPySide.main_window import MainWindow

    w = MainWindow()
    try:
        # Ruta sin ninguna copia .bak → no hay nada que ofrecer (sin modal).
        assert w._offer_backup_restore(str(tmp_path / "inexistente.json"), "boom") is False
    finally:
        w.controller.close()
        w.close()
        app.processEvents()
