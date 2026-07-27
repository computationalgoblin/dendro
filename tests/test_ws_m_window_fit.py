"""BETA-CIERRE WS-M / B3: la ventana cabe en portátiles comunes.

El mínimo anterior (1180×760) desbordaba 1366×768 y 1080p@150% (1280×720 lógico): la
ventana no cabía ni se podía encoger, y Guardar/toasts quedaban bajo la barra de tareas.
Guarda estática (sin Qt) para que no vuelva a subir.
"""

from __future__ import annotations

import re
from pathlib import Path

_HOST = Path(__file__).resolve().parents[1] / "hosts" / "DesktopHostPySide"


def test_main_window_min_height_fits_common_laptops():
    src = (_HOST / "main_window.py").read_text(encoding="utf-8")
    m = re.search(r"self\.setMinimumSize\((\d+),\s*(\d+)\)", src)
    assert m, "no se encontró self.setMinimumSize en MainWindow"
    width, height = int(m.group(1)), int(m.group(2))
    # Debe caber en 1280×720 lógico (1080p@150%) y 1366×768 tras barra de tareas.
    assert height <= 680, f"altura mínima {height} no cabe en 1280×720 / 1366×768"
    assert width <= 1180, f"anchura mínima {width} demasiado grande"


def test_main_opens_maximized():
    src = (_HOST / "main.py").read_text(encoding="utf-8")
    assert "showMaximized(" in src, "la entrada debe abrir maximizada (WS-M/B3)"
