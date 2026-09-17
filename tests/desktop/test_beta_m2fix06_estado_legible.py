"""BETA2-FIX-06 (G2-09): lo pagado se lee entero y no se tira.

Un guionista pidió tres mecanismos dramáticos, esperó trece minutos, la IA respondió
exactamente lo que pedía — y la app se lo enseñó en **una línea cortada por el borde
derecho de la ventana durante seis segundos**, y luego lo borró. Leyó su propia
respuesta volcando el objeto ``job`` desde su guion de pilotaje.

Tres cosas se verifican aquí:
- el ``_StatusLabel`` envuelve el texto y tiene un ancho acotado;
- la recolocación del floater lo deja SIEMPRE dentro del lienzo (función pura, sin
  ``MainWindow``): el ``max(12, …)` viejo clavaba x=12 y el resto se salía;
- existe una superficie de historial de sesión alimentada por ``list_jobs()`` (que
  hasta hoy tenía CERO llamadas en ``hosts/``), alcanzable desde el indicador.
"""

from __future__ import annotations

import os
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.views.workspaces import (  # noqa: E402
    _STATUS_FLOATER_MARGIN,
    CreationWorkspace,
    _AIHistoryDialog,
    _StatusLabel,
    geometria_floater_estado,
)

_HOSTS = Path("hosts/DesktopHostPySide")
_WORKSPACES = _HOSTS / "views/workspaces.py"

_MENSAJE_250 = (
    "Tres mecanismos para el giro de la temporada: (1) la carta que Aria nunca envió "
    "aparece en manos del gremio; (2) el juramento de sangre obliga a Beto a delatar a "
    "su propia hermana ante el tribunal; y (3) la sequía adelanta el cerco un mes entero, "
    "forzando la decisión antes del juicio público."
)
assert len(_MENSAJE_250) >= 250  # el caso que el ticket exige mostrar entero


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


def _method_body(src: str, name: str) -> str:
    return src.split(f"def {name}(self")[1].split("\n    def ")[0]


# ── El estado se lee entero (criterio 6) ─────────────────────────────────────


def test_beta_m2fix06_status_label_envuelve_y_acota_su_ancho():
    label = _StatusLabel()
    assert label.wordWrap() is True
    assert 0 < label.maximumWidth() < 16777215  # acotado, no el máximo de Qt
    label.setText(_MENSAJE_250)
    assert len(label.text()) >= 250
    assert label.text() == _MENSAJE_250  # no se recorta el texto: se envuelve
    label.deleteLater()


def test_beta_m2fix06_el_texto_largo_no_ensancha_el_label_sin_limite():
    label = _StatusLabel()
    label.setText(_MENSAJE_250)
    assert label.sizeHint().width() <= label.maximumWidth()
    label.deleteLater()


@pytest.mark.parametrize("ancho", [1024, 1280, 1440, 1920, 2560])
def test_beta_m2fix06_el_floater_cabe_siempre_en_el_lienzo(ancho):
    """`x >= 12` Y `x + width <= ancho - 12` para todo ancho de ventana."""
    for ancho_floater in (200, 640, ancho - 100, ancho, ancho + 800):
        x, y, w = geometria_floater_estado(ancho, 900, ancho_floater, 60)
        assert x >= _STATUS_FLOATER_MARGIN
        assert x + w <= ancho - _STATUS_FLOATER_MARGIN
        assert y >= _STATUS_FLOATER_MARGIN


def test_beta_m2fix06_el_floater_se_centra_cuando_cabe():
    x, _y, w = geometria_floater_estado(1440, 900, 600, 60)
    assert w == 600
    assert abs((x + w // 2) - 720) <= 1  # centrado de verdad, no clavado a la izquierda


def test_beta_m2fix06_el_calculo_viejo_se_salia_y_el_nuevo_no():
    """Reproduce el caso fotografiado: floater más ancho que la ventana."""
    ancho_lienzo, ancho_floater = 1024, 1600
    viejo_x = max(12, (ancho_lienzo - ancho_floater) // 2)
    assert viejo_x + ancho_floater > ancho_lienzo  # el viejo se salía
    x, _y, w = geometria_floater_estado(ancho_lienzo, 900, ancho_floater, 60)
    assert x + w <= ancho_lienzo - _STATUS_FLOATER_MARGIN


def test_beta_m2fix06_ventana_absurdamente_estrecha_no_revienta():
    x, y, w = geometria_floater_estado(40, 40, 900, 60)
    assert w >= 1 and x >= 0 and y >= 0


def test_beta_m2fix06_sync_status_floater_usa_la_funcion_pura():
    body = _method_body(_WORKSPACES.read_text(encoding="utf-8"), "_sync_status_floater")
    assert "geometria_floater_estado(" in body
    assert "max(12, (self.width() - floater.width()) // 2)" not in body  # el viejo, fuera


# ── Lo pagado no se tira (criterio 7) ────────────────────────────────────────


def _job(tipo="suggest_composite", estado="completed", mensaje="", error=""):
    return SimpleNamespace(
        type=SimpleNamespace(value=tipo),
        status=SimpleNamespace(value=estado),
        created_at="2026-08-04T10:00:00",
        updated_at="2026-08-04T10:13:00",
        message=mensaje,
        error=error,
    )


def test_beta_m2fix06_el_historial_lista_tipo_hora_estado_y_mensaje_entero():
    texto = _AIHistoryDialog.texto_de_jobs([_job(mensaje=_MENSAJE_250)])
    assert "suggest_composite" in texto
    assert "completed" in texto
    assert "2026-08-04T10:13:00" in texto
    assert _MENSAJE_250 in texto  # el mensaje ENTERO, no una línea cortada


def test_beta_m2fix06_el_historial_conserva_los_errores():
    texto = _AIHistoryDialog.texto_de_jobs([_job(estado="failed", error="HTTP 401")])
    assert "failed" in texto and "HTTP 401" in texto


def test_beta_m2fix06_historial_vacio_lo_dice():
    assert "Todavía no hay" in _AIHistoryDialog.texto_de_jobs([])


def test_beta_m2fix06_la_ventana_de_historial_pinta_los_jobs():
    dialog = _AIHistoryDialog()
    dialog.set_jobs([_job(mensaje=_MENSAJE_250)])
    assert _MENSAJE_250 in dialog._body.toPlainText()
    assert dialog._body.isReadOnly()
    dialog.deleteLater()


def test_beta_m2fix06_el_workspace_alimenta_el_historial_con_list_jobs():
    fake = SimpleNamespace()
    jobs = [_job(mensaje="uno"), _job(mensaje="dos")]
    fake.ai_job_service = SimpleNamespace(list_jobs=lambda: jobs)
    leidos = types.MethodType(CreationWorkspace._session_jobs, fake)()
    assert [j.message for j in leidos] == ["dos", "uno"]  # el más reciente primero


def test_beta_m2fix06_el_historial_es_fail_soft_sin_servicio():
    fake = SimpleNamespace(ai_job_service=None)
    assert types.MethodType(CreationWorkspace._session_jobs, fake)() == []

    class _Roto:
        def list_jobs(self):
            raise RuntimeError("servicio caído")

    fake2 = SimpleNamespace(ai_job_service=_Roto())
    assert types.MethodType(CreationWorkspace._session_jobs, fake2)() == []


def test_beta_m2fix06_el_boton_de_historial_cuenta_los_jobs():
    fake = SimpleNamespace()
    fake.ai_job_service = SimpleNamespace(list_jobs=lambda: [_job(), _job(), _job()])
    fake._job_history_btn = SimpleNamespace(
        visible=None,
        texto="",
        setVisible=lambda v: setattr(fake._job_history_btn, "visible", v),
        setText=lambda t: setattr(fake._job_history_btn, "texto", t),
    )
    fake._session_jobs = types.MethodType(CreationWorkspace._session_jobs, fake)
    hay = types.MethodType(CreationWorkspace._sync_history_button, fake)()
    assert hay is True
    assert fake._job_history_btn.visible is True
    assert fake._job_history_btn.texto == "Historial (3)"


def test_beta_m2fix06_sin_jobs_el_boton_se_esconde():
    fake = SimpleNamespace()
    fake.ai_job_service = SimpleNamespace(list_jobs=lambda: [])
    fake._job_history_btn = SimpleNamespace(
        visible=None,
        setVisible=lambda v: setattr(fake._job_history_btn, "visible", v),
        setText=lambda t: None,
    )
    fake._session_jobs = types.MethodType(CreationWorkspace._session_jobs, fake)
    assert types.MethodType(CreationWorkspace._sync_history_button, fake)() is False
    assert fake._job_history_btn.visible is False


def test_beta_m2fix06_los_hooks_no_op_del_pipeline_ya_no_son_no_op():
    """`_refresh_ai_jobs_panel_if_open` / `_sync_jobs_indicator` los invoca el pipeline
    en sus TRES transiciones; ahí es donde va el historial."""
    src = _WORKSPACES.read_text(encoding="utf-8")
    assert "self._fill_ai_history()" in _method_body(src, "_refresh_ai_jobs_panel_if_open")
    assert "self._sync_history_button()" in _method_body(src, "_sync_jobs_indicator")


def test_beta_m2fix06_list_jobs_ya_tiene_llamador_en_el_host():
    """Antes: cero llamadas a `list_jobs()` en todo `hosts/`."""
    llamadas = [
        ruta
        for ruta in _HOSTS.rglob("*.py")
        if "list_jobs()" in ruta.read_text(encoding="utf-8")
    ]
    assert llamadas, "el historial de IA no consume list_jobs()"


def test_beta_m2fix06_se_llega_al_historial_desde_el_indicador():
    body = _method_body(_WORKSPACES.read_text(encoding="utf-8"), "_build_status_floater")
    assert "self._job_history_btn" in body
    assert "self._open_ai_history" in body
    # WS-K: el botón «Cancelar» del floater sigue ahí (criterio 11).
    assert "self._job_cancel_btn" in body
    assert "self._cancel_active_ai_jobs" in body


def test_beta_m2fix06_el_autoborrado_de_6s_sigue_existiendo():
    """WIKI-13 se mantiene: la respuesta desaparece del floater, pero es recuperable."""
    src = _WORKSPACES.read_text(encoding="utf-8")
    assert "def _schedule_status_clear(self, delay_ms: int = 6000)" in src
    assert "self._schedule_status_clear()" in _method_body(src, "_on_ai_job_finished")
