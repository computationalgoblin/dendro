"""Paridad de cierre entre LeftDrawer y RightDrawer (BETA1-UX6).

Ambos cajones comparten `BaseSlideDrawer`, así que el cierre debe comportarse
igual en los dos: el suelo de ancho (minimumWidth) se anima EN LOCKSTEP con el
techo (maximumWidth), de modo que el cajón se encoge frame a frame en vez de
"desaparecer de golpe" dejando hueco. Antes LeftDrawer no animaba el suelo al
cerrar (regresión por lógica duplicada). También verifica que reabrir estando
visible fija el ancho correcto.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from hosts.DesktopHostPySide.widgets.base_slide_drawer import BaseSlideDrawer
from hosts.DesktopHostPySide.widgets.left_drawer import LeftDrawer
from hosts.DesktopHostPySide.widgets.right_drawer import RightDrawer


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _drawer(cls):
    parent = QWidget()
    parent.resize(1100, 800)
    parent.show()
    d = cls(parent)
    d.set_content(QLabel("contenido"), "Título")
    return d


@pytest.mark.parametrize("cls", [LeftDrawer, RightDrawer])
def test_ambos_cajones_comparten_base(cls):
    d = _drawer(cls)
    assert isinstance(d, BaseSlideDrawer)


@pytest.mark.parametrize("cls", [LeftDrawer, RightDrawer])
def test_cierre_anima_suelo_en_lockstep(cls):
    """A mitad de cierre, el suelo sigue al techo (no queda clavado a tope)."""
    d = _drawer(cls)
    d.open()
    d._animation.setCurrentTime(d._animation.duration())  # abierto del todo
    target = d._target_width
    assert d.maximumWidth() == target

    d.close()
    anim = d._animation
    assert anim is not None
    anim.setCurrentTime(anim.duration() // 2)
    # Lockstep: el suelo acompaña al techo, y ambos por debajo del objetivo.
    assert d.minimumWidth() == d.maximumWidth()
    assert d.maximumWidth() < target

    anim.setCurrentTime(anim.duration())
    assert d.maximumWidth() == 0
    assert d.minimumWidth() == 0


@pytest.mark.parametrize("cls", [LeftDrawer, RightDrawer])
def test_reabrir_visible_fija_ancho(cls):
    """open() estando ya abierto fija el ancho objetivo (no se queda a medias)."""
    d = _drawer(cls)
    d.open()
    d._animation.setCurrentTime(d._animation.duration())
    d.open()  # ya visible y al ancho correcto
    assert d.maximumWidth() == d._target_width
    assert d.minimumWidth() == d._target_width


@pytest.mark.parametrize("cls", [LeftDrawer, RightDrawer])
def test_cancel_animation_guarda_carrera(cls):
    """Abrir/cerrar rápido cancela la animación previa (no deja callbacks vivos)."""
    d = _drawer(cls)
    d.open()
    opening = d._animation
    d.close()  # cancela la apertura a medias
    assert d._animation is not opening  # la apertura fue reemplazada
    # La finalización de la apertura cancelada no debe disparar limpieza.
    opening.finished.emit()
    assert d._animation is not None  # sigue viva la animación de cierre
