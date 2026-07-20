"""BETA2-SHIP-03: crash-guard honesto — registro en el data_dir y aviso al usuario.

Auditoría de lanzamiento 2026-07-21: el crash log iba al cwd (había un
dendro_crash.log de 419 KB en la raíz del repo) y la recuperación era muda.
La otra mitad del ticket (proyecto nuevo sin ruta) ya estaba cerrada: el wizard
pide la ruta de guardado AL CREAR (_create_project_from_wizard) — se documenta
aquí con una comprobación de fuente para que no regrese.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from hosts.DesktopHostPySide import main as desktop_main

_MAIN_WINDOW = Path("hosts/DesktopHostPySide/main_window.py")


@pytest.fixture(autouse=True)
def _restore_excepthook():
    prev_hook, prev_notifier = sys.excepthook, desktop_main._crash_notifier
    yield
    sys.excepthook = prev_hook
    desktop_main._crash_notifier = prev_notifier


def test_crash_log_lives_in_user_datadir(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    path = desktop_main._crash_log_path()
    assert path == tmp_path / ".narrative-architect" / "dendro_crash.log"
    assert path.parent.is_dir()  # el guard puede escribir desde el primer crash


def test_hook_writes_log_and_notifies(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    notified: list[Path] = []
    desktop_main.set_crash_notifier(notified.append)
    desktop_main._install_crash_guard()

    try:
        raise ValueError("boom de prueba")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    log = tmp_path / ".narrative-architect" / "dendro_crash.log"
    assert log.exists()
    assert "boom de prueba" in log.read_text(encoding="utf-8")
    assert notified == [log]


def test_notifier_failure_never_breaks_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    desktop_main.set_crash_notifier(lambda _p: (_ for _ in ()).throw(RuntimeError))
    desktop_main._install_crash_guard()
    try:
        raise ValueError("boom")
    except ValueError:
        sys.excepthook(*sys.exc_info())  # no debe propagar pese al notifier roto


def test_wizard_creation_asks_for_save_path():
    src = _MAIN_WINDOW.read_text(encoding="utf-8")
    body = src.split("def _create_project_from_wizard(self")[1].split("\n    def ")[0]
    assert "QFileDialog.getSaveFileName" in body  # el proyecto nace CON ruta
    assert "self.controller.create(name, path)" in body
