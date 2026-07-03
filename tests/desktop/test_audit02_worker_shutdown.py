"""BETA1-AUDIT-02: apagado ordenado de QThreads del host.

Cerrar la app con un worker de IA en vuelo destruía QThreads corriendo
("QThread: Destroyed while thread is still running" → abort). El registro
`track_worker`/`shutdown_workers` de qt_lifecycle debe pararlos en bloque.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.qt_lifecycle import (  # noqa: E402
    _TRACKED_WORKERS,
    shutdown_workers,
    track_worker,
)


def _ensure_app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _SlowWorker(QThread):
    """Simula un job largo pero cooperativo (respeta isInterruptionRequested)."""

    def run(self) -> None:  # pragma: no cover - cuerpo trivial
        while not self.isInterruptionRequested():
            self.msleep(10)


def test_shutdown_workers_stops_running_threads():
    _ensure_app()
    worker = _SlowWorker()
    track_worker(worker)
    worker.start()
    assert worker.isRunning()

    shutdown_workers(wait_ms=2000)

    assert not worker.isRunning()
    assert worker not in _TRACKED_WORKERS


def test_track_worker_self_prunes_when_thread_finishes():
    app = _ensure_app()

    class _Quick(QThread):
        def run(self) -> None:  # pragma: no cover - cuerpo trivial
            pass

    worker = _Quick()
    track_worker(worker)
    worker.start()
    assert worker.wait(2000)
    app.processEvents()  # entrega el finished→discard encolado

    assert worker not in _TRACKED_WORKERS


def test_shutdown_workers_is_idempotent_and_tolerates_empty_registry():
    _ensure_app()
    shutdown_workers()
    shutdown_workers()
