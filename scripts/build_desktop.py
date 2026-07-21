"""Construye el distribuible de escritorio Dendro (PyInstaller one-folder).

Uso (desde la raíz del repo, con el venv activo):

    python scripts/build_desktop.py

Requiere PyInstaller (está en el extra ``dev``):

    pip install -e .[dev]

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


def main() -> int:
    if not SPEC_PATH.exists():
        print(f"[ERROR] No existe el spec de PyInstaller: {SPEC_PATH}")
        return 1

    if not _pyinstaller_disponible():
        print("[ERROR] PyInstaller no está instalado en este entorno.")
        print("        Instálalo con:   pip install -e .[dev]")
        print("        (o directamente: pip install pyinstaller)")
        return 1

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
