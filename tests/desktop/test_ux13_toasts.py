"""Toasts / avisos transitorios (BETA1-UX13)."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from hosts.DesktopHostPySide.widgets.toast_layer import Toast, ToastLayer


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _host() -> QWidget:
    host = QWidget()
    host.resize(900, 600)
    return host


def test_show_toast_crea_y_muestra() -> None:
    host = _host()
    layer = ToastLayer(host)
    layer.show_toast("Guardado", kind="success")
    assert len(layer.toasts) == 1
    assert not layer.isHidden()
    host._t = layer  # mantener vivo


def test_kinds_validos_y_fallback() -> None:
    host = _host()
    layer = ToastLayer(host)
    for kind in ("success", "info", "error"):
        layer.show_toast(f"x-{kind}", kind=kind, duration_ms=0)
    # kind desconocido degrada a "info" sin romper.
    t = layer.show_toast("raro", kind="zzz", duration_ms=0)
    assert isinstance(t, Toast)
    assert t.kind == "info"
    host._t = layer


def test_click_descarta() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    host = _host()
    host.show()
    layer = ToastLayer(host)
    toast = layer.show_toast("clic para cerrar", duration_ms=0)
    assert len(layer.toasts) == 1
    QTest.mouseClick(toast, Qt.MouseButton.LeftButton)
    assert layer.toasts == []
    host._t = layer


def test_auto_dismiss_por_timer() -> None:
    host = _host()
    layer = ToastLayer(host)
    layer.show_toast("efímero", duration_ms=800)  # mínimo aplicado
    toast = layer.toasts[0]
    # Forzar el disparo del timer sin esperar (singleShot ya configurado).
    toast._dismiss()
    assert layer.toasts == []
    host._t = layer


def test_maximo_visible_descarta_antiguos() -> None:
    host = _host()
    layer = ToastLayer(host)
    for i in range(8):
        layer.show_toast(f"t{i}", duration_ms=0)
    assert len(layer.toasts) <= 4
    host._t = layer


def test_no_graphics_effect_en_layer() -> None:
    host = _host()
    layer = ToastLayer(host)
    layer.show_toast("x", duration_ms=0)
    assert layer.graphicsEffect() is None
    host._t = layer
