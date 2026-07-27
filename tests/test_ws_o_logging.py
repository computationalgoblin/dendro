"""BETA-CIERRE WS-O: `ctx.log` persiste en un fichero rotativo (señal de la beta).

Antes, los avisos/errores (incluidos los fallos del proveedor de IA) solo vivían en RAM
+ un widget oculto: un reporte de tester llegaba sin rastro que adjuntar. Ahora dejan
traza en `~/.narrative-architect/dendro.log`, con un sello de versión/OS al arrancar.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    import hosts.DesktopHostPySide.app_context as ac

    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(ac, "_log_dir", lambda: tmp_path / "logs")
    monkeypatch.setattr(ac, "_FILE_LOGGER", None)
    return ac


def test_ctx_log_writes_to_rotating_file(isolated, tmp_path):
    ctx = isolated.AppContext()
    ctx.log("error", "fallo del proveedor 401 marcador-unico-xyz")
    log_file = tmp_path / "logs" / "dendro.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "marcador-unico-xyz" in content  # el error dejó traza
    assert "Dendro" in content  # sello de arranque (versión/OS)


def test_data_dir_points_at_log_folder(isolated, tmp_path):
    ctx = isolated.AppContext()
    assert ctx.data_dir() == tmp_path / "logs"
