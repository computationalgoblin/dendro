"""Construye el distribuible de escritorio Dendro (PyInstaller one-folder).

Uso (desde la raíz del repo, con el venv activo):

    python scripts/build_desktop.py

Requiere PyInstaller Y PySide6 (extras ``dev`` y ``desktop``). OJO: ``.[dev]`` solo
NO trae PySide6 y produciría un exe que no arranca:

    pip install -e ".[dev,desktop]"

El resultado queda en ``dist/Dendro/`` (``Dendro.exe`` + ``_internal/``).
Si existe ``README-USUARIO.md`` en la raíz, se copia junto al exe para que
viaje dentro del zip de distribución.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "packaging" / "dendro.spec"
DIST_DIR = REPO_ROOT / "dist" / "Dendro"
README_USUARIO = REPO_ROOT / "README-USUARIO.md"
# SHIP-06: la licencia de evaluación beta viaja dentro del zip.
LICENSE_PATH = REPO_ROOT / "LICENSE"
# SHIP-05: proyecto de ejemplo curado — viaja junto al exe para que la primera
# apertura no sea un lienzo vacío.
EJEMPLOS_DIR = REPO_ROOT / "ejemplos"


def _pyinstaller_disponible() -> bool:
    """True si PyInstaller está instalado en el intérprete actual."""
    return importlib.util.find_spec("PyInstaller") is not None


def _pyside6_disponible() -> bool:
    """True si PySide6 está instalado (el spec analiza el host PySide6)."""
    return importlib.util.find_spec("PySide6") is not None


def _regen_version_info() -> None:
    """(Re)genera packaging/version_info.txt desde app_version — una sola fuente (WS-I).

    Si algo falla (p.ej. utils win32 de PyInstaller fuera de Windows), se salta: el spec
    usa el fichero ya existente o construye el exe sin recurso de versión.
    """
    try:
        import re

        from PyInstaller.utils.win32.versioninfo import (
            FixedFileInfo,
            StringFileInfo,
            StringStruct,
            StringTable,
            VarFileInfo,
            VarStruct,
            VSVersionInfo,
        )

        from packages.domain.config import AppConfig

        v = AppConfig().app_version
        m = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
        vt = (int(m.group(1)), int(m.group(2)), int(m.group(3)), 0) if m else (0, 0, 0, 0)
        vi = VSVersionInfo(
            ffi=FixedFileInfo(
                filevers=vt, prodvers=vt, mask=0x3F, flags=0x0,
                OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0),
            ),
            kids=[
                StringFileInfo([StringTable("040904B0", [
                    StringStruct("CompanyName", "Angel Exposito"),
                    StringStruct("ProductName", "Dendro"),
                    StringStruct("FileDescription", "Dendro - arquitecto narrativo"),
                    StringStruct("FileVersion", v),
                    StringStruct("ProductVersion", v),
                    StringStruct("LegalCopyright", "Proprietary - Beta Evaluation License"),
                    StringStruct("OriginalFilename", "Dendro.exe"),
                    StringStruct("InternalName", "Dendro"),
                ])]),
                VarFileInfo([VarStruct("Translation", [0x0409, 0x04B0])]),
            ],
        )
        out = REPO_ROOT / "packaging" / "version_info.txt"
        out.write_text(
            "# Generado por scripts/build_desktop.py desde AppConfig().app_version (WS-I).\n"
            + str(vi) + "\n",
            encoding="utf-8",
        )
        print(f"[BUILD] version_info.txt regenerado para {v}.")
    except Exception as exc:  # noqa: BLE001 — el build sigue sin recurso de versión
        print(f"[AVISO] no se pudo regenerar version_info.txt: {exc}")


def main() -> int:
    if not SPEC_PATH.exists():
        print(f"[ERROR] No existe el spec de PyInstaller: {SPEC_PATH}")
        return 1

    if not _pyinstaller_disponible():
        print("[ERROR] PyInstaller no está instalado en este entorno.")
        print('        Instálalo con:   pip install -e ".[dev,desktop]"')
        return 1

    if not _pyside6_disponible():
        print("[ERROR] PySide6 no está instalado (el spec analiza el host PySide6);")
        print("        sin él, el build produciría un exe que no arranca.")
        print('        Instálalo con:   pip install -e ".[dev,desktop]"')
        return 1

    _regen_version_info()

    print(f"[BUILD] Lanzando PyInstaller sobre {SPEC_PATH.relative_to(REPO_ROOT)} ...")
    comando = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(REPO_ROOT / "dist"),
        "--workpath",
        str(REPO_ROOT / "build"),
        str(SPEC_PATH),
    ]
    resultado = subprocess.run(comando, cwd=REPO_ROOT)
    if resultado.returncode != 0:
        print(f"[ERROR] PyInstaller terminó con código {resultado.returncode}.")
        return resultado.returncode

    exe = DIST_DIR / "Dendro.exe"
    if not exe.exists():
        print(f"[ERROR] El build terminó pero no se encontró {exe}.")
        return 1

    if README_USUARIO.exists():
        shutil.copy2(README_USUARIO, DIST_DIR / README_USUARIO.name)
        print(f"[BUILD] Copiado {README_USUARIO.name} junto al exe.")
    else:
        print("[AVISO] No existe README-USUARIO.md; el zip irá sin manual de usuario.")

    if EJEMPLOS_DIR.is_dir():
        shutil.copytree(EJEMPLOS_DIR, DIST_DIR / "ejemplos", dirs_exist_ok=True)
        print("[BUILD] Copiada la carpeta ejemplos/ (proyecto de muestra) junto al exe.")
    else:
        print("[AVISO] No existe ejemplos/; el zip irá sin proyecto de muestra.")

    if LICENSE_PATH.exists():
        shutil.copy2(LICENSE_PATH, DIST_DIR / "LICENSE.txt")
        print("[BUILD] Copiada la LICENSE junto al exe.")
    else:
        print("[AVISO] No existe LICENSE; el zip irá sin licencia (no distribuir así).")

    print(f"[OK] Distribuible listo en {DIST_DIR}")
    print("     Para publicar: comprime la carpeta dist/Dendro/ en un zip.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
