"""Ajustes de drawers de configuración (feedback post-UX10).

- La rueda del ratón sobre combos/spin/slider dentro de un cajón NO cambia su
  valor (solo desplaza el menú) → `install_wheel_guard`.
- El ancho mínimo del cajón es amplio para que la configuración no se corte.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QComboBox, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets.design_system import install_wheel_guard
from hosts.DesktopHostPySide.widgets.right_drawer import RightDrawer


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _wheel() -> QWheelEvent:
    return QWheelEvent(
        QPointF(8, 8), QPointF(8, 8), QPoint(0, 0), QPoint(0, -120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )


def test_wheel_guard_no_cambia_combo_sin_foco() -> None:
    cont = QWidget()
    lay = QVBoxLayout(cont)
    combo = QComboBox()
    combo.addItems(["uno", "dos", "tres", "cuatro"])
    combo.setCurrentIndex(1)
    lay.addWidget(combo)
    install_wheel_guard(cont)

    assert combo.focusPolicy() == Qt.FocusPolicy.StrongFocus
    combo.clearFocus()
    QApplication.sendEvent(combo, _wheel())
    assert combo.currentIndex() == 1  # la rueda no lo cambió


def test_drawer_ancho_minimo_amplio() -> None:
    parent = QWidget()
    parent.resize(900, 700)  # ventana estrecha → 42% = 378, por debajo del mínimo
    d = RightDrawer(parent)
    d.update_target_width()
    assert d._target_width >= 480
