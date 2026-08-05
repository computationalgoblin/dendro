"""BETA-MULTIAGENT2-FIX-14 (G2-30): la clave de IA se volcaba con la IA apagada.

`_apply_ai_environment` escribía `NARRATIVE_AI_API_KEY` **sin mirar el proveedor**, y
se ejecuta en CADA arranque y en CADA guardado. Una tester anti-IA lo comprobó: con
`ai_provider: "simulated"` su clave seguía en claro en `settings.json` y se volcaba
al entorno del proceso en cada arranque. Y no había forma de retirarla: `_save_ia_env`
solo la ESCRIBÍA cuando el campo traía texto, nunca la borraba.

HIGIENE DE ESTE TEST: clave FALSA (`sk-test-0000`) y `tmp_path`. Nunca se toca el
`settings.json` real del usuario ni se deja la variable en el entorno del proceso.
"""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402

_CLAVE = "sk-test-0000"
_VAR = "NARRATIVE_AI_API_KEY"


@pytest.fixture(autouse=True)
def _entorno_limpio(tmp_path, monkeypatch):
    """Aísla `settings.json` y el entorno: ni se lee ni se escribe el del usuario."""
    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")
    for var in (_VAR, "NARRATIVE_AI_PROVIDER", "NARRATIVE_AI_BASE_URL", "NARRATIVE_AI_MODEL"):
        monkeypatch.delenv(var, raising=False)
    yield


def _contexto(**ajustes):
    ctx = ac.AppContext()
    for clave, valor in ajustes.items():
        setattr(ctx, clave, valor)
    return ctx


def test_beta_m2fix14_proveedor_simulado_no_vuelca_la_clave_al_entorno():
    ctx = _contexto(ai_provider="simulated", ai_api_key=_CLAVE, ai_base_url="")
    ctx._apply_ai_environment()
    assert os.environ.get("NARRATIVE_AI_PROVIDER") == "simulated"
    assert _CLAVE not in (os.environ.get(_VAR) or ""), (
        "apagar la IA no apagaba nada: la clave seguía en el entorno del proceso"
    )
    assert ctx.provider_consumes_api_key() is False


def test_beta_m2fix14_proveedor_real_si_vuelca_la_clave():
    """La corrección no puede romper el caso que SÍ la necesita."""
    ctx = _contexto(
        ai_provider="openai_compatible",
        ai_api_key=_CLAVE,
        ai_base_url="https://api.example.com/v1",
    )
    ctx._apply_ai_environment()
    assert os.environ.get(_VAR) == _CLAVE
    assert ctx.provider_consumes_api_key() is True


def test_beta_m2fix14_cambiar_a_simulated_retira_la_clave_del_entorno():
    """Apagar la IA tiene que apagarla de verdad, no dejar el rastro anterior."""
    ctx = _contexto(
        ai_provider="openai_compatible",
        ai_api_key=_CLAVE,
        ai_base_url="https://api.example.com/v1",
    )
    ctx._apply_ai_environment()
    assert os.environ.get(_VAR) == _CLAVE

    ctx.ai_provider = "simulated"
    ctx._apply_ai_environment()

    assert _VAR not in os.environ, "la clave exportada por la app debe retirarse"


def test_beta_m2fix14_una_clave_puesta_a_mano_en_el_entorno_se_respeta():
    """Quien no quiera que Dendro toque el disco puede exportarla él mismo."""
    externa = "sk-test-externa-0000"
    os.environ[_VAR] = externa
    try:
        ctx = _contexto(ai_provider="simulated", ai_api_key="", ai_base_url="")
        ctx._apply_ai_environment()
        assert os.environ.get(_VAR) == externa, "no es nuestra: no se toca"
        ctx.save_preferences()
        datos = json.loads(ac.PREFERENCES_PATH.read_text(encoding="utf-8"))
        assert datos.get("ai_api_key") == "", "una clave del entorno no se persiste"
    finally:
        os.environ.pop(_VAR, None)


def test_beta_m2fix14_olvidar_la_clave_la_borra_del_fichero():
    ctx = _contexto(
        ai_provider="openai_compatible",
        ai_api_key=_CLAVE,
        ai_base_url="https://api.example.com/v1",
    )
    ctx.save_preferences()
    assert _CLAVE in ac.PREFERENCES_PATH.read_text(encoding="utf-8")

    ctx.forget_api_key()

    contenido = ac.PREFERENCES_PATH.read_text(encoding="utf-8")
    assert _CLAVE not in contenido, "la clave sigue en claro en el archivo de ajustes"
    assert json.loads(contenido).get("ai_api_key") == ""
    assert _VAR not in os.environ, "olvidar también la retira del proceso"


def test_beta_m2fix14_cambiar_a_simulated_desde_ajustes_no_reexporta_la_clave():
    """`_save_ia_env` reexportaba la clave a mano, saltándose la guarda."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    fuente = (raiz / "hosts/DesktopHostPySide/widgets/settings_panels.py").read_text(
        encoding="utf-8"
    )
    cuerpo = fuente.split("def _save_ia_env()", 1)[1].split("\n    save_ia_btn")[0]
    assert 'os.environ["NARRATIVE_AI_API_KEY"]' not in cuerpo, (
        "el volcado al entorno lo hace `_apply_ai_environment`, que mira el proveedor"
    )
    assert "ctx.save_preferences()" in cuerpo
    # Y existe la puerta para retirarla.
    assert "Olvidar la clave" in fuente
    assert "forget_api_key" in fuente


def test_beta_m2fix14_no_se_promete_una_proteccion_de_fichero_inexistente():
    """En Windows `Path.chmod` no toca ACL: no protege nada. No se finge que sí."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    fuente = (raiz / "hosts/DesktopHostPySide/app_context.py").read_text(encoding="utf-8")
    bloque = fuente.split("PREFERENCES_PATH.write_text", 1)[1][:1200]
    assert 'os.name == "posix"' in bloque, (
        "el chmod(0o600) sugería una protección que en la plataforma de la beta no existe"
    )
    if os.name != "posix":
        ctx = _contexto(ai_provider="simulated", ai_api_key="", ai_base_url="")
        ctx.save_preferences()
        assert ac.PREFERENCES_PATH.exists()


def test_beta_m2fix14_la_ui_dice_la_verdad_sobre_donde_vive_la_clave():
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    fuente = (raiz / "hosts/DesktopHostPySide/widgets/settings_panels.py").read_text(
        encoding="utf-8"
    )
    assert "texto plano" in fuente, "el usuario tiene derecho a saber que no se cifra"
