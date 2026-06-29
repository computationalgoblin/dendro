"""Geometría OVERLAY de los cajones (fix command bar aplastada).

Antes los cajones vivían en el `QHBoxLayout` del shell (modelo *push*): al abrir
uno, el stack —y con él la command bar— se estrechaba y los controles se
solapaban. Ahora los cajones FLOTAN sobre el área del grafo (overlay) anclados a
su lado y terminan JUSTO encima de la command bar, sin tocar su ancho.

Este test fija ese contrato a nivel de `BaseSlideDrawer`: con un área overlay que
reserva el alto de la command bar abajo, el cajón abierto queda anclado a su lado,
con el ancho objetivo, y su borde inferior NO invade la franja reservada.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from hosts.DesktopHostPySide.widgets.left_drawer import LeftDrawer
from hosts.DesktopHostPySide.widgets.right_drawer import RightDrawer

_PARENT_W = 1000
_PARENT_H = 800
_BAR_H = 68  # franja reservada al fondo (command bar)


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _drawer(cls):
    parent = QWidget()
    parent.resize(_PARENT_W, _PARENT_H)
    parent.show()
    d = cls(parent)
    # Área overlay = todo el padre MENOS la command bar inferior.
    d.set_area_provider(lambda: QRect(0, 0, _PARENT_W, _PARENT_H - _BAR_H))
    d.set_content(QLabel("contenido"), "Título")
    return d


def _open_full(d):
    d.open()
    d._animation.setCurrentTime(d._animation.duration())
    return d


def test_overlay_no_invade_la_command_bar():
    """El borde inferior del cajón queda en (o por encima de) el tope de la barra."""
    for cls in (LeftDrawer, RightDrawer):
        d = _open_full(_drawer(cls))
        geo = d.geometry()
        assert geo.y() == 0
        assert geo.height() == _PARENT_H - _BAR_H
        # Nada del cajón cae dentro de la franja reservada para la command bar.
        assert geo.y() + geo.height() <= _PARENT_H - _BAR_H


def test_right_drawer_anclado_al_borde_derecho():
    d = _open_full(_drawer(RightDrawer))
    target = d._target_width
    geo = d.geometry()
    assert geo.width() == target
    assert geo.x() == _PARENT_W - target          # pegado a la derecha
    assert geo.x() + geo.width() == _PARENT_W


def test_left_drawer_anclado_al_borde_izquierdo():
    d = _open_full(_drawer(LeftDrawer))
    target = d._target_width
    geo = d.geometry()
    assert geo.width() == target
    assert geo.x() == 0                            # pegado a la izquierda


def test_reposition_sigue_al_area_sin_reanimar():
    """`reposition()` reaplica la geometría con el ancho actual (resize de ventana)."""
    d = _open_full(_drawer(RightDrawer))
    target = d._target_width
    # El área crece (ventana más ancha): el cajón se re-ancla al nuevo borde.
    new_w = 1400
    d.set_area_provider(lambda: QRect(0, 0, new_w, _PARENT_H - _BAR_H))
    d.reposition()
    geo = d.geometry()
    assert geo.width() == target                   # mismo ancho, sin reanimar
    assert geo.x() == new_w - target               # re-anclado al nuevo borde derecho
