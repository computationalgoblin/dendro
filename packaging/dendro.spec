# -*- mode: python ; coding: utf-8 -*-
# ruff: noqa
"""Spec de PyInstaller para el host de escritorio Dendro (BETA2-SHIP-05).

Build one-folder para Windows sobre ``hosts/DesktopHostPySide/main.py``:

    python scripts/build_desktop.py
    # o directamente:
    python -m PyInstaller --noconfirm packaging/dendro.spec

Resultado: ``dist/Dendro/`` con ``Dendro.exe`` (sin consola) y ``_internal/``.

Notas de diseño:
- ``hosts`` NO es un paquete regular (no tiene ``__init__.py``): es un paquete
  namespace PEP 420. Por eso el exe se construye desde el PATH del script de
  entrada y ``pathex`` apunta a la raíz del repo, de modo que los imports
  absolutos ``hosts.*`` y ``packages.*`` resuelvan durante el análisis.
- ``packages`` se recoge entero vía ``collect_submodules``: la CLI y algún
  servicio hacen imports perezosos (dentro de funciones) y algún
  ``__import__`` dinámico que el análisis estático podría perderse.
- Los SVG de ``hosts/DesktopHostPySide/assets`` se copian conservando la ruta
  relativa, porque ``widgets/icons.py`` los resuelve con
  ``Path(__file__).parent.parent / "assets" / "icons"`` (en el bundle,
  ``__file__`` cuelga de ``_internal/`` y la ruta relativa se mantiene).
- PySide6/shiboken6 los gestionan los hooks oficiales de PyInstaller
  (plugins de Qt incluidos); no hace falta datas manual para Qt.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

# SPECPATH lo inyecta PyInstaller: directorio de este spec (packaging/).
REPO_ROOT = os.path.dirname(SPECPATH)  # noqa: F821
sys.path.insert(0, REPO_ROOT)

APP_NAME = "Dendro"
ENTRY_SCRIPT = os.path.join(REPO_ROOT, "hosts", "DesktopHostPySide", "main.py")
ASSETS_DIR = os.path.join(REPO_ROOT, "hosts", "DesktopHostPySide", "assets")

datas = [
    (ASSETS_DIR, os.path.join("hosts", "DesktopHostPySide", "assets")),
]

# Todo el árbol de application/domain/persistence/infrastructure/ui (stdlib puro).
hiddenimports = collect_submodules("packages")

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[REPO_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
