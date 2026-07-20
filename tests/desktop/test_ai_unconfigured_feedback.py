"""BETA2-SHIP-01: la IA sin configurar NUNCA es un no-op silencioso.

Auditoría de lanzamiento 2026-07-21: Regar/Sugerencias sin proveedor cortaban con
``ctx.log`` (panel oculto → botón muerto) y la única ayuda mandaba a variables de
entorno + reiniciar, cuando existen Ajustes de IA in-app con refresco en vivo.

CreationWorkspace no se instancia sin AppContext completo (patrón de la casa, ver
``test_wiki_recorte_fixes``): el cableado del workspace se valida por FUENTE; el
resto (AppContext, _human_error, mensaje de ai_jobs) por comportamiento real.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.settings_panels import _human_error
from packages.application.ai_jobs import AIJobService, AIJobType
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import SimulatedAIProvider

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")
_MAIN_WINDOW = Path("hosts/DesktopHostPySide/main_window.py")


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


def _method_body(src: str, name: str) -> str:
    return src.split(f"def {name}(self")[1].split("\n    def ")[0]


# ── Regar/Sugerencias sin proveedor → aviso VISIBLE, no log oculto ───────────


def test_water_and_suggest_use_visible_warning():
    src = _WORKSPACES.read_text(encoding="utf-8")
    water = _method_body(src, "_on_foco_water")
    suggest = _method_body(src, "_on_foco_suggest")
    assert 'self._warn_ai_unconfigured("regar")' in water
    assert 'self._warn_ai_unconfigured("pedir sugerencias")' in suggest
    # El patrón viejo (solo ctx.log, invisible) desapareció de ambos caminos.
    assert "IA no configurada: define el proveedor" not in src


def test_warn_helper_notifies_and_opens_help():
    src = _WORKSPACES.read_text(encoding="utf-8")
    body = _method_body(src, "_warn_ai_unconfigured")
    assert 'kind="error"' in body  # toast visible (ctx.notify), no ctx.log a un panel oculto
    assert "self.ctx.notify(" in body
    assert "self._show_ai_config_help()" in body


def test_help_dialog_is_actionable_and_truthful():
    src = _WORKSPACES.read_text(encoding="utf-8")
    body = _method_body(src, "_show_ai_config_help")
    assert '"Abrir Ajustes de IA"' in body  # botón que abre los ajustes in-app
    assert "open_ai_settings" in body
    # Fuera el volcado de variables de entorno y la exigencia de reiniciar.
    assert "Define estas variables de entorno" not in body
    assert "NARRATIVE_AI_PROVIDER" not in body


def test_job_failed_humanizes_error():
    src = _WORKSPACES.read_text(encoding="utf-8")
    body = _method_body(src, "_on_ai_job_failed")
    assert "_human_ai_error(" in body
    # El crudo sigue en el log para depurar.
    assert 'self.ctx.log("error", f"Job IA fallido' in body


# ── Cableado del acceso a Ajustes de IA ──────────────────────────────────────


def test_appcontext_exposes_open_ai_settings():
    ctx = AppContext()
    assert hasattr(ctx, "open_ai_settings")
    assert ctx.open_ai_settings is None  # fail-soft por defecto (CLI/tests)


def test_main_window_wires_open_ai_settings():
    src = _MAIN_WINDOW.read_text(encoding="utf-8")
    assert "self.ctx.open_ai_settings = self._open_ai_settings" in src


# ── Errores humanizados y mensaje veraz del borde IA ─────────────────────────


def test_human_error_translates_common_failures():
    assert "credenciales" in _human_error("HTTP 401 unauthorized").lower()
    assert "conectar" in _human_error("ConnectionError: refused").lower()


def test_provider_unconfigured_message_points_to_settings():
    service = AIJobService(provider=SimulatedAIProvider(), allow_simulated=False)
    assert service.provider_unconfigured() is True
    created = service.create_job(AIJobType.SUGGEST_RELATIONS, "una prueba", explicit=True)
    assert isinstance(created, Ok)
    result = service.execute_job(created.value.id)
    assert isinstance(result, Error)
    assert "Ajustes de IA" in result.error
    assert "reinicia" not in result.error
    assert "simulado" in result.error  # el contrato D05 sigue explícito
