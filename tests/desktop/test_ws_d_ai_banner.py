"""BETA-CIERRE WS-D: banner «configura la IA» no bloqueante en Home.

Antes, el único aviso de proveedor sin configurar aparecía por-clic al intentar
regar/sugerir (invisible hasta que ya usabas la IA). Ahora el Home lo muestra de
entrada y enlaza a Ajustes→IA; se oculta en cuanto hay un proveedor real.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _isolated_prefs(tmp_path, monkeypatch):
    # Prefs en fichero temporal → no leemos la config de IA real del dev.
    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")


def _home(app):
    from hosts.DesktopHostPySide.views.home_view import HomeView

    ctx = ac.AppContext()
    ctx.ai_provider = "simulated"
    ctx.ai_base_url = ""
    ctx.ai_api_key = ""
    return HomeView(ctx), ctx


def test_banner_visible_when_ai_simulated(app):
    home, _ctx = _home(app)
    assert not home._ai_configured()
    assert not home._ai_banner.isHidden()  # sin proveedor real → banner visible


def test_banner_hidden_when_provider_configured(app):
    home, ctx = _home(app)
    ctx.ai_provider = "openai_compatible"
    ctx.ai_base_url = "https://api.example.com/v1"
    ctx.ai_api_key = "sk-secret"
    home.refresh()
    assert home._ai_configured()
    assert home._ai_banner.isHidden()  # proveedor real → sin banner


def test_banner_hidden_when_openai_but_incomplete(app):
    home, ctx = _home(app)
    ctx.ai_provider = "openai_compatible"
    ctx.ai_base_url = "https://api.example.com/v1"
    ctx.ai_api_key = ""  # falta la clave → NO cuenta como configurado
    home.refresh()
    assert not home._ai_configured()
    assert not home._ai_banner.isHidden()


def test_dismiss_hides_for_session(app):
    home, _ctx = _home(app)
    assert not home._ai_banner.isHidden()
    home._dismiss_ai_banner()
    assert home._ai_banner.isHidden()
    home.refresh()  # un refresh posterior NO lo vuelve a mostrar
    assert home._ai_banner.isHidden()


def test_config_button_triggers_ai_settings_callback(app):
    home, _ctx = _home(app)
    fired = []
    home.register_callback("ai_settings", lambda: fired.append(True))
    # El botón «Configurar IA» es el QuietIconButton dentro del banner.
    from hosts.DesktopHostPySide.views.home_view import QuietIconButton

    buttons = [w for w in home._ai_banner.findChildren(QuietIconButton)]
    assert buttons, "el banner debe tener un botón de configurar"
    buttons[0].click()
    assert fired == [True]
