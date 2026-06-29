"""Hover-lift canvas-safe (BETA1-UX18)."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QFrame

from hosts.DesktopHostPySide.widgets import design_system as ds


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _enter(w):
    QApplication.sendEvent(w, QEvent(QEvent.Type.Enter))


def _leave(w):
    QApplication.sendEvent(w, QEvent(QEvent.Type.Leave))


def test_install_devuelve_filtro_sin_graphics_effect() -> None:
    w = QFrame()
    w.setStyleSheet("QFrame { background: white; }")
    flt = ds.install_hover_lift(w)
    assert flt is not None
    # Canvas-safe: jamás un graphics effect sobre la superficie.
    assert w.graphicsEffect() is None


def test_enter_resalta_borde_y_leave_restaura() -> None:
    w = QFrame()
    base = "QFrame { background: white; }"
    w.setStyleSheet(base)
    ds.install_hover_lift(w, hover_border=ds.GOLD_SOFT)
    _enter(w)
    assert ds.GOLD_SOFT in w.styleSheet()
    assert "border" in w.styleSheet()
    _leave(w)
    assert w.styleSheet() == base


def test_tolera_kwargs_legados() -> None:
    w = QFrame()
    # Llamada al estilo antiguo: no debe romper (kwargs descartados).
    flt = ds.install_hover_lift(
        w, rest_blur=20.0, rest_y=6.0, rest_alpha=38, lift_blur=38.0, lift_y=12.0, lift_alpha=64
    )
    assert flt is not None
    assert w.graphicsEffect() is None
