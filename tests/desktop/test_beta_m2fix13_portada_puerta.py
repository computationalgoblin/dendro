"""BETA-MULTIAGENT2-FIX-13 · TANDA B — la puerta de entrada de la portada (G2-17).

    «Me quedé mirando el centro de la pantalla pensando "¿y ahora qué?". Aquí ya
    sentí lo de siempre: que el problema soy yo, que se me escapa algo evidente.
    Pues no era yo. En ese hueco vacío SÍ hay una tarjeta que pone "Creación /
    Abre o crea un proyecto / ENTRAR" —es la puerta de entrada de la aplicación—
    sólo que está pintada tan clarita que no se ve. Lo medí sobre mi propia
    captura: contraste 1,19 a 1.»

Los tokens estaban bien (GOLD_DEEP sobre SURFACE_HI = 5,73:1). Todo el daño lo
hacía un `QGraphicsOpacityEffect` a 0,45 sobre el widget entero.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect  # noqa: E402

from hosts.DesktopHostPySide.widgets import design_system as ds  # noqa: E402

_AA = 4.5
# Por debajo de esto la composición ya come más de lo que ningún color compensa.
_OPACIDAD_MINIMA_LEGIBLE = 0.8


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tarjeta_de_creacion(qapp):
    from hosts.DesktopHostPySide.views.home_view import HomeNode

    return HomeNode("Creación", "Tu mundo, tus reglas", "creation", "creation")


def test_beta_m2fix13_la_puerta_no_se_apaga_sin_proyecto(qapp):
    tarjeta = _tarjeta_de_creacion(qapp)
    try:
        tarjeta.set_dimmed(True)
        efecto = tarjeta.graphicsEffect()
        if isinstance(efecto, QGraphicsOpacityEffect):
            assert efecto.opacity() >= _OPACIDAD_MINIMA_LEGIBLE, (
                f"la tarjeta se compone a {efecto.opacity()}: el texto cae por debajo "
                "del umbral de lectura (el bug de Carmen, 1,19:1 medido)"
            )
    finally:
        tarjeta.deleteLater()
        qapp.processEvents()


def test_beta_m2fix13_entrar_y_creacion_se_leen_sobre_su_propio_fondo(qapp):
    """El título va en GOLD_DEEP y «E N T R A R» también; el fondo de la tarjeta
    atenuada es SURFACE (más plano que SURFACE_HI, que es el estado normal)."""
    for fondo in (ds.SURFACE, ds.SURFACE_HI, ds.WHITE):
        assert ds.contrast_ratio(ds.GOLD_DEEP, fondo) >= _AA, fondo
    # El subtítulo va en INK_SOFT: también tiene que leerse.
    for fondo in (ds.SURFACE, ds.SURFACE_HI):
        assert ds.contrast_ratio(ds.INK_SOFT, fondo) >= _AA, fondo


def test_beta_m2fix13_atenuar_sigue_diciendo_que_no_hay_proyecto(qapp):
    """El ticket NO cambia el comportamiento de la portada, solo su legibilidad:
    la tarjeta sigue comunicando que aún no hay nada."""
    tarjeta = _tarjeta_de_creacion(qapp)
    try:
        tarjeta.set_dimmed(True)
        assert tarjeta._subtitle_label.text() == "Abre o crea un proyecto"
        apagada = tarjeta.styleSheet()
        # El «apagado» se dice por otro medio: superficie plana + borde neutro.
        assert ds.SURFACE in apagada and ds.LINE_STRONG in apagada
        assert ds.GOLD_SOFT not in apagada, "el borde dorado es el estado NORMAL"

        tarjeta.set_dimmed(False)
        encendida = tarjeta.styleSheet()
        assert encendida != apagada, "encendida y apagada se ven igual"
        assert ds.SURFACE_HI in encendida and ds.GOLD_SOFT in encendida
    finally:
        tarjeta.deleteLater()
        qapp.processEvents()


def test_beta_m2fix13_la_tarjeta_sigue_siendo_clicable(qapp):
    """Atenuada no es deshabilitada: hoy se puede pulsar y debe seguir así."""
    tarjeta = _tarjeta_de_creacion(qapp)
    try:
        tarjeta.set_dimmed(True)
        assert tarjeta.isEnabled()
        # …y las animaciones de entrada siguen teniendo su efecto de opacidad.
        assert isinstance(tarjeta.graphicsEffect(), QGraphicsOpacityEffect)
        tarjeta.animate_restore()  # no debe reventar sin efecto instalado
    finally:
        tarjeta.deleteLater()
        qapp.processEvents()
