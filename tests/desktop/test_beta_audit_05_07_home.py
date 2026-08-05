"""BETA-AUDIT-05 y 07: el Inicio tiene canal de feedback y dice la verdad sobre la IA.

05 — La beta cerrada existe para recoger feedback y no tenía canal: lo único que había
     era «Abrir carpeta de registros» escondido dentro de «Acerca de». PRUEBA-GUIADA.md
     daba por hecho un botón «Reportar problema» dos veces, y WS-O lo declaraba Done.

07 — El banner decía «La IA está en modo simulado», que un lector razonable entiende
     como «va a inventarme contenido falso». No existe tal modo: sin proveedor los
     trabajos de IA FALLAN. Era además la primera frase que la app dirige al usuario.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402
from hosts.DesktopHostPySide.views.home_view import HomeView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _home():
    """Inicio sin proveedor de IA: el estado en el que arranca un tester."""
    ctx = ac.AppContext()
    ctx.ai_provider = "simulated"
    ctx.ai_base_url = ""
    ctx.ai_api_key = ""
    return HomeView(ctx)


def _textos(widget) -> str:
    return " ".join(w.text() for w in widget.findChildren(QLabel) if w.text())


def test_el_inicio_tiene_boton_de_reportar_problema(qapp):
    home = _home()
    try:
        assert hasattr(home, "_btn_report"), "no existe el botón de reportar problema"
        assert "Reportar problema" in home._btn_report.text(), (
            "el rótulo debe coincidir con el que promete PRUEBA-GUIADA.md"
        )
        # Debe estar colocado por un layout, no construido y olvidado.
        assert home._btn_report.parentWidget() is not None
    finally:
        home.deleteLater()
        qapp.processEvents()


def test_reportar_problema_esta_enrutado(qapp):
    """El botón tiene que llegar a MainWindow, no morir en un callback sin registrar."""
    home = _home()
    try:
        recibido = []
        home.register_callback("report_problem", lambda: recibido.append(True))
        home._btn_report.click()
        assert recibido == [True], "el botón no dispara la acción registrada"
    finally:
        home.deleteLater()
        qapp.processEvents()


def test_el_banner_no_promete_un_modo_simulado(qapp):
    home = _home()
    try:
        texto = _textos(home).lower()
        assert "modo simulado" not in texto, (
            "el banner sigue anunciando un modo simulado que el motor no permite"
        )
        assert "simulad" not in texto, "queda una fuga del nombre interno del proveedor"
    finally:
        home.deleteLater()
        qapp.processEvents()


def test_el_banner_dice_que_la_app_funciona_sin_ia(qapp):
    """Lo que el usuario novato necesitaba saber y el copy anterior no decía."""
    home = _home()
    try:
        texto = _textos(home).lower()
        assert "sin ella" in texto or "funciona sin" in texto, (
            "el banner no aclara que Dendro es usable sin conectar una IA"
        )
    finally:
        home.deleteLater()
        qapp.processEvents()
