"""BETA-CIERRE WS-O: banner de recuperación PERSISTENTE y accionable.

Los fallos serios (apertura/guardado) usaban un toast fugaz con ruta incopiable y
podían spamear en tormentas de error. Ahora hay un banner persistente con «Abrir
registro» y de-dup; ctx.notify_recovery lo alimenta (fail-soft a notify/log).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _isolate_logs(tmp_path, monkeypatch):
    # No tocar el log real ni las prefs del dev; cerrar el handler evita el
    # ResourceWarning (filterwarnings=error) que contaminaba a otros tests.
    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(ac, "_log_dir", lambda: tmp_path / "logs")
    monkeypatch.setattr(ac, "_FILE_LOGGER", None)
    yield
    logger = ac._FILE_LOGGER
    if logger is not None:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


def _layer(app):
    from hosts.DesktopHostPySide.widgets.toast_layer import ToastLayer

    parent = QWidget()
    parent.resize(800, 600)
    return ToastLayer(parent), parent


def test_recovery_is_persistent_with_action(app):
    layer, _parent = _layer(app)
    opened = []
    toast = layer.show_recovery(
        "No se pudo abrir el proyecto: x", on_open_log=lambda: opened.append(1)
    )
    assert toast in layer.toasts
    assert not toast._timer.isActive()  # persistente: no se autodescarta
    assert hasattr(toast, "action_button")
    assert toast.action_button.text() == "Abrir registro"
    toast.action_button.click()
    assert opened == [1]  # la acción abre el registro
    assert toast not in layer.toasts  # y luego se descarta


def test_recovery_dedups_identical_messages(app):
    layer, _parent = _layer(app)
    layer.show_recovery("mismo fallo")
    layer.show_recovery("mismo fallo")  # idéntico → no se repite
    assert len(layer.toasts) == 1


def test_show_toast_dedup_by_key(app):
    layer, _parent = _layer(app)
    layer.show_toast("a", dedup_key="k1")
    layer.show_toast("distinto texto", dedup_key="k1")  # misma clave → uno solo
    assert len(layer.toasts) == 1


def test_ctx_notify_recovery_routes_to_sink(app):
    ctx = ac.AppContext()
    got = []
    ctx.recovery_sink = lambda msg: got.append(msg)
    ctx.notify_recovery("uh oh")
    assert got == ["uh oh"]


def test_ctx_notify_recovery_failsoft_to_notify(app):
    ctx = ac.AppContext()
    ctx.recovery_sink = None  # sin banner disponible
    notified = []
    ctx.notify_sink = lambda msg, kind="info": notified.append((msg, kind))
    ctx.notify_recovery("again")
    assert notified == [("again", "error")]
