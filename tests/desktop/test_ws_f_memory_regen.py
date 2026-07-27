"""BETA-CIERRE WS-F / B2: «Regenerar con IA» corre FUERA del hilo de UI.

Antes, `MemoryViewerPanel._regenerate` llamaba a `update_memory` (provider-backed,
bloqueante hasta 300 s) directamente en el slot del botón → congelaba la app entera.
Ahora va en un QThread registrado; el hilo de UI no se bloquea y el botón se deshabilita.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import hosts.DesktopHostPySide.widgets.memory_viewer_panel as mod  # noqa: E402
from hosts.DesktopHostPySide.widgets.memory_viewer_panel import MemoryViewerPanel  # noqa: E402
from packages.domain.narrative_memory import MemoryTargetKind, NarrativeMemory  # noqa: E402
from packages.domain.result import Error, Ok  # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class _FakeMem:
    def __init__(self):
        self.block = NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY, target_id="e1", resumen_editorial="antes"
        )

    def list_memories(self, *a, **k):
        return Ok([self.block])


class _FakeAI:
    def __init__(self, result=None):
        self.thread_ident = None
        self.calls = 0
        self._result = result if result is not None else Ok({"ok": True})

    def update_memory(self, kind, tid, ctx, mode="regen"):
        self.thread_ident = threading.get_ident()
        self.calls += 1
        return self._result


def _panel(ai):
    panel = MemoryViewerPanel(_FakeMem(), ai)
    panel.list.setCurrentRow(0)  # selecciona el bloque → fija _current_key
    return panel


def _drain(app, panel, worker):
    assert worker.wait(5000), "el worker no terminó a tiempo"
    for _ in range(20):
        app.processEvents()
        if panel._regen_worker is None:
            break


def test_regenerate_runs_off_the_ui_thread(app):
    ai = _FakeAI()
    panel = _panel(ai)
    assert panel._current_key is not None

    panel._regenerate()
    worker = panel._regen_worker
    assert worker is not None  # se lanzó un worker en vez de bloquear
    assert panel.regen_btn.text() == "Regenerando…"  # estado ocupado visible
    assert not panel.regen_btn.isEnabled()  # el botón se deshabilita mientras corre

    _drain(app, panel, worker)

    assert ai.calls == 1
    assert ai.thread_ident is not None
    assert ai.thread_ident != threading.get_ident()  # corrió FUERA del hilo de UI
    assert panel._regen_worker is None  # el slot 'done' limpió el worker
    assert panel.regen_btn.text() == "Regenerar con IA"  # rehabilitado


def test_regenerate_error_surfaces_without_crashing(app, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        mod.QMessageBox, "warning", lambda *a, **k: captured.setdefault("msg", a[2])
    )
    ai = _FakeAI(result=Error("401 credenciales inválidas"))
    panel = _panel(ai)

    panel._regenerate()
    _drain(app, panel, panel._regen_worker)

    assert panel._regen_worker is None
    assert "msg" in captured  # se avisó (sin crash ni congelación)
    assert panel.regen_btn.isEnabled()  # se rehabilita tras el error
