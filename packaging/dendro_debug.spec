# -*- mode: python ; coding: utf-8 -*-
# ruff: noqa
"""Variante DEBUG del spec de Dendro (BETA2-SHIP-06): igual que dendro.spec pero
CON consola, para capturar el traceback cuando el exe windowed muere al arrancar
(en windowed, stderr es None y el bootloader solo muestra un diálogo).

    python -m PyInstaller --noconfirm packaging/dendro_debug.spec
    dist/DendroDebug/DendroDebug.exe 2> traza.txt
"""

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

REPO_ROOT = os.path.dirname(SPECPATH)  # noqa: F821
sys.path.insert(0, REPO_ROOT)

APP_NAME = "DendroDebug"
ENTRY_SCRIPT = os.path.join(REPO_ROOT, "hosts", "DesktopHostPySide", "main.py")
ASSETS_DIR = os.path.join(REPO_ROOT, "hosts", "DesktopHostPySide", "assets")

datas = [
    (ASSETS_DIR, os.path.join("hosts", "DesktopHostPySide", "assets")),
]

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
    console=True,
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
