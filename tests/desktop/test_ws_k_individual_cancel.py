"""BETA-CIERRE WS-K: cancelar el job de IA en curso (Regar/Sugerencia individual).

El lote ya se podía cancelar; un Regar/Sugerencia suelto no. Ahora el floater de
estado lleva un «Cancelar» (visible solo mientras hay un job corriendo) que marca
el job CANCELLED (el worker descarta su resultado) e interrumpe cooperativamente.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _ws():
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    ws = CreationWorkspace.__new__(CreationWorkspace)  # sin construir el QWidget

    class _Lbl:
        def __init__(self):
            self.text_val = ""

        def setText(self, t):  # noqa: N802 (mock de Qt)
            self.text_val = t

    ws._job_status_label = _Lbl()
    ws._schedule_status_clear = lambda *a, **k: None
    ws._refresh_busy_indicator = lambda: None
    return ws


def test_cancel_marks_job_and_interrupts_worker(app):
    ws = _ws()
    cancelled = []

    class _Svc:
        def cancel_job(self, jid):
            cancelled.append(jid)

    class _Worker:
        def __init__(self):
            self.interrupted = False

        def isRunning(self):  # noqa: N802 (mock de Qt)
            return True

        def requestInterruption(self):  # noqa: N802 (mock de Qt)
            self.interrupted = True

    worker = _Worker()
    ws._ai_workers = {"j1": worker}
    ws.ai_job_service = _Svc()

    ws._cancel_active_ai_jobs()

    assert cancelled == ["j1"]  # el job se marca CANCELLED
    assert worker.interrupted  # y se pide interrupción cooperativa
    assert ws._job_status_label.text_val == "Cancelado"


def test_cancel_is_noop_without_running_jobs(app):
    ws = _ws()

    class _Svc:
        def cancel_job(self, jid):  # no debe llamarse
            raise AssertionError("no hay jobs que cancelar")

    ws._ai_workers = {}
    ws.ai_job_service = _Svc()
    ws._cancel_active_ai_jobs()  # no revienta, no cancela nada
    assert ws._job_status_label.text_val == ""


def test_busy_refresh_toggles_cancel_button_visibility():
    # El botón se muestra/oculta según haya jobs de IA en vuelo (chequeo de fuente:
    # la lógica vive antes del early-return del indicador para actualizarse siempre).
    src = _WORKSPACES.read_text(encoding="utf-8")
    body = src.split("def _refresh_busy_indicator(self):")[1].split("\n    def ")[0]
    assert 'cancel_btn = getattr(self, "_job_cancel_btn", None)' in body
    assert 'cancel_btn.setVisible(bool(getattr(self, "_ai_workers", None)))' in body
    # Y el botón se cablea al handler de cancelación.
    assert "self._job_cancel_btn.clicked.connect(self._cancel_active_ai_jobs)" in src
