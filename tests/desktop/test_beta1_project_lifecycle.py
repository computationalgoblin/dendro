"""BETA1-B04/B05 desktop lifecycle contracts."""
from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.main_window import MainWindow, _IDX_CREATION, _IDX_HOME


@pytest.fixture()
def qapp():
    if not HAS_QT:
        pytest.skip("PySide6 no disponible")
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _preferencias_aisladas(tmp_path, monkeypatch):
    """Aisla `settings.json` del usuario REAL.

    Cierre de la oleada BETA2: sin esto, `MainWindow()` autoabre el
    ultimo proyecto de las preferencias de la maquina, la premisa del fichero
    ("no hay proyecto activo") se vuelve falsa y el `window.close()` del
    `finally` levanta un `QMessageBox.question` MODAL que, bajo
    `QT_QPA_PLATFORM=offscreen`, CUELGA el proceso para siempre — y con el, el
    barrido entero de `tests/desktop`. Es un fallo de aislamiento del test, no
    del producto.
    """
    if not HAS_QT:
        yield
        return
    from hosts.DesktopHostPySide import app_context

    monkeypatch.setattr(app_context, "PREFERENCES_PATH", tmp_path / "settings.json")
    yield


class _FakeCloseEvent:
    def __init__(self):
        self.accepted = False
        self.ignored = False

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


def test_main_window_blocks_creation_without_active_project(qapp):
    window = MainWindow()
    try:
        assert window.controller.ps.active_project is None

        window._go_space(_IDX_CREATION)

        assert window.stack.currentIndex() == _IDX_HOME
    finally:
        window.close()


def test_close_event_accepts_when_no_project_is_active(qapp):
    window = MainWindow()
    event = _FakeCloseEvent()
    try:
        window.closeEvent(event)

        assert event.accepted is True
        assert event.ignored is False
    finally:
        window.close()


def test_close_event_can_cancel_with_active_project(qapp, monkeypatch):
    window = MainWindow()
    event = _FakeCloseEvent()
    try:
        window.controller.create("Proyecto activo")
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
        )

        window.closeEvent(event)

        assert event.accepted is False
        assert event.ignored is True
    finally:
        window.controller.close()
        window.close()


def test_close_event_saves_active_project_when_requested(qapp, monkeypatch):
    window = MainWindow()
    event = _FakeCloseEvent()
    saved = {"called": False}
    try:
        window.controller.create("Proyecto activo")
        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Save,
        )
        monkeypatch.setattr(
            window,
            "_save_active_project",
            lambda: saved.__setitem__("called", True) or True,
        )

        window.closeEvent(event)

        assert saved["called"] is True
        assert event.accepted is True
        assert event.ignored is False
    finally:
        window.controller.close()
        window.close()
