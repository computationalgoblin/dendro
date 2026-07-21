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
    import faulthandler

    prev_hook, prev_notifier = sys.excepthook, desktop_main._crash_notifier
    prev_stderr = sys.stderr
    yield
    sys.excepthook = prev_hook
    desktop_main._crash_notifier = prev_notifier
    sys.stderr = prev_stderr
    faulthandler.disable()
    stream = desktop_main._faulthandler_stream
    if stream is not None:
        try:
            stream.close()
        except Exception:  # noqa: BLE001 — limpieza best-effort
            pass
        desktop_main._faulthandler_stream = None
    for synthetic in desktop_main._stdio_refs:
        try:
            synthetic.close()
        except Exception:  # noqa: BLE001 — limpieza best-effort
            pass
    desktop_main._stdio_refs.clear()
    desktop_main._stdio_synthesized = False


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


def test_guard_survives_windowed_mode_without_stderr(tmp_path, monkeypatch):
    """SHIP-06: en el exe PyInstaller windowed sys.stderr es None — el guard no
    puede reventar al instalarse (era el crash de arranque del 0.9.0b1 inicial)."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(sys, "stderr", None)
    desktop_main._install_crash_guard()  # no debe lanzar RuntimeError
    # El volcado nativo queda apuntando al fichero de crashes del data_dir.
    assert desktop_main._faulthandler_stream is not None

    notified: list[Path] = []
    desktop_main.set_crash_notifier(notified.append)
    try:
        raise ValueError("boom sin consola")
    except ValueError:
        sys.excepthook(*sys.exc_info())  # el hook tampoco puede tocar stderr=None

    log = tmp_path / ".narrative-architect" / "dendro_crash.log"
    assert "boom sin consola" in log.read_text(encoding="utf-8")
    assert notified == [log]


def test_windowed_stdio_synthesized(monkeypatch):
    """SHIP-06: el exe windowed sintetiza stdout/stderr reales — los imports del
    árbol dejan de reventar con streams None (causa raíz del segundo crash)."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    desktop_main._ensure_windowed_stdio()
    assert sys.stdout is not None
    assert sys.stderr is not None
    sys.stderr.write("escribible de verdad\n")  # no revienta
    assert desktop_main._stdio_synthesized is True


def test_main_orders_stdio_then_guard_then_imports():
    """El orden es el seguro: stdio → guard → imports pesados (así un fallo de
    import acaba en dendro_crash.log, no en el diálogo mudo del bootloader)."""
    src = Path("hosts/DesktopHostPySide/main.py").read_text(encoding="utf-8")
    body = src.split("def main():")[1]
    stdio = body.index("_ensure_windowed_stdio()")
    guard = body.index("_install_crash_guard()")
    heavy = body.index("from hosts.DesktopHostPySide.main_window import MainWindow")
    assert stdio < guard < heavy


def test_wizard_creation_asks_for_save_path():
    src = _MAIN_WINDOW.read_text(encoding="utf-8")
    body = src.split("def _create_project_from_wizard(self")[1].split("\n    def ")[0]
    assert "QFileDialog.getSaveFileName" in body  # el proyecto nace CON ruta
    assert "self.controller.create(name, path)" in body
