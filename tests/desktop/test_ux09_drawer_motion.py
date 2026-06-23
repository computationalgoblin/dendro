"""Movimiento de apertura/cierre de drawers (BETA1-UX09).

La apertura entra con presencia (OutQuint, más larga) y el cierre es algo más
rápido y directo (OutCubic), coherente con el glide del canvas (UX06). Verifica
duración/curva por dirección y que se alcanzan los anchos objetivo.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEasingCurve
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from hosts.DesktopHostPySide.widgets import design_system as ds
from hosts.DesktopHostPySide.widgets.right_drawer import RightDrawer


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _drawer() -> RightDrawer:
    parent = QWidget()
    parent.resize(1100, 800)
    parent.show()
    d = RightDrawer(parent)
    d.set_content(QLabel("contenido"), "Título")
    return d


def test_apertura_usa_curva_y_duracion_de_entrada() -> None:
    d = _drawer()
    d.open()
    anim = d._animation
    assert anim is not None
    assert anim.duration() == ds.MOTION_SLOW
    assert anim.easingCurve().type() == QEasingCurve.Type.OutQuint
    # Al final del tiempo, el cajón alcanza su ancho objetivo.
    anim.setCurrentTime(anim.duration())
    assert d.maximumWidth() == d._target_width


def test_cierre_es_mas_rapido_y_directo() -> None:
    d = _drawer()
    d.open()
    d._animation.setCurrentTime(d._animation.duration())  # abierto del todo
    d.close()
    anim = d._animation
    assert anim is not None
    assert anim.duration() == ds.MOTION_BASE
    assert anim.easingCurve().type() == QEasingCurve.Type.OutCubic
    anim.setCurrentTime(anim.duration())
    assert d.maximumWidth() == 0
