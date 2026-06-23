"""I17 (desktop) — worker de extracción IA en segundo plano: progreso, fin, error, cancelar."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.app_context import AppContext  # noqa: E402
from hosts.DesktopHostPySide.views.import_export_view import (  # noqa: E402
    ImportExportView,
    _ImportExtractionWorker,
)
from packages.domain.project import Project  # noqa: E402
from packages.domain.result import Error, Ok  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeController:
    """Controller falso: simula la extracción con progreso y un resultado fijo."""

    def __init__(self, result, *, segments=2):
        self._result = result
        self._segments = segments
        self.cancelled = False

    def extract_ai_candidates(self, basket_id, *, progress_callback=None, should_cancel=None):
        for i in range(self._segments):
            if should_cancel is not None and should_cancel():
                self.cancelled = True
                break
            if progress_callback is not None:
                progress_callback(i, self._segments, f"seg{i}")
        if progress_callback is not None:
            progress_callback(self._segments, self._segments, "completado")
        return self._result


def _run_worker(controller):
    """Ejecuta el worker de forma SÍNCRONA (run() directo) y captura señales."""
    captured = {"progress": [], "ok": None, "failed": None}
    worker = _ImportExtractionWorker(controller, "basket-1")
    worker.progress.connect(lambda d, t, l: captured["progress"].append((d, t)))
    worker.finishedOk.connect(lambda items: captured.__setitem__("ok", items))
    worker.failed.connect(lambda err: captured.__setitem__("failed", err))
    worker.run()
    return captured


def test_worker_emits_progress_and_finished(qapp):
    cand = type("C", (), {"id": "c1"})()
    captured = _run_worker(_FakeController(Ok([cand]), segments=2))
    assert captured["failed"] is None
    assert captured["ok"] == [cand]
    assert (0, 2) in captured["progress"]
    assert captured["progress"][-1] == (2, 2)


def test_worker_emits_failed_on_error(qapp):
    captured = _run_worker(_FakeController(Error("Configura un proveedor IA")))
    assert captured["ok"] is None
    assert "proveedor" in (captured["failed"] or "")


def test_worker_cancel_stops(qapp):
    controller = _FakeController(Ok([]), segments=5)
    worker = _ImportExtractionWorker(controller, "basket-1")
    worker.cancel()
    worker.run()
    assert controller.cancelled is True


class _Ctrl:
    ps = None


def test_view_progress_slots_update_ui(qapp):
    proj = Project(name="V")

    class PS:
        active_project = proj
        _current_path = Path("/tmp/x.json")

    ctrl = _Ctrl()
    ctrl.ps = PS()
    ctx = AppContext()
    view = ImportExportView(ctx, ctrl)

    view._set_extraction_busy(True)
    assert not view.progress_row.isHidden()  # flag explícito (la vista no está shown)
    view._on_extract_progress(1, 3, "Capitulo")
    assert "2/3" in view.progress_label.text()

    view._on_extract_done([1, 2])
    assert view.progress_row.isHidden()
    assert "2 candidato" in view.detail.toPlainText()
