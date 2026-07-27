"""BETA-CIERRE WS-F: endurecer los QThread de imagen y Ajustes-IA.

Sin `track_worker` la app podía abortar al cerrarse con un worker en vuelo
("QThread: Destroyed while thread is still running"); y los slots por closure
tocaban widgets ya destruidos. El `done()` del buscador de imágenes esperaba solo
2 s, insuficiente para un HTTP de Openverse (~15 s). Aquí: comportamiento del
apagado ordenado + firmas estáticas del cableado.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_SETTINGS = Path("hosts/DesktopHostPySide/widgets/settings_panels.py")
_IMAGE = Path("hosts/DesktopHostPySide/widgets/image_search_dialog.py")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _Spin(QThread):
    def run(self):
        while not self.isInterruptionRequested():
            self.msleep(10)


def test_shutdown_workers_stops_a_running_worker(app):
    from hosts.DesktopHostPySide.widgets.qt_lifecycle import (
        _TRACKED_WORKERS,
        shutdown_workers,
        track_worker,
    )

    worker = _Spin()
    track_worker(worker)
    assert worker in _TRACKED_WORKERS
    worker.start()
    assert worker.isRunning()
    shutdown_workers(wait_ms=2000)  # el apagado ordenado lo detiene
    assert not worker.isRunning()
    assert worker not in _TRACKED_WORKERS


def test_settings_workers_are_tracked_and_guarded():
    src = _SETTINGS.read_text(encoding="utf-8")
    assert src.count("track_worker(worker)") >= 2  # test de conexión + chat
    # Los slots por closure comprueban que el widget sigue vivo antes de tocarlo.
    assert "if not _qt_alive(ia_status_label):" in src
    assert "if not _qt_alive(chat_history):" in src


def test_image_dialog_tracks_workers_and_done_terminates():
    src = _IMAGE.read_text(encoding="utf-8")
    assert src.count("track_worker(self._") >= 3  # search + thumbs + download
    done_body = src.split("def done(self, result")[1].split("\n    def ")[0]
    assert "requestInterruption()" in done_body
    assert "worker.terminate()" in done_body  # si sigue bloqueado tras el wait
