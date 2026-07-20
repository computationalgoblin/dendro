"""Asset store de imágenes del proyecto (BETA2-IMG-01).

El proyecto persiste como UN JSON (``packages/persistence/store.py``); los
binarios de imagen NO viajan dentro. Este servicio los guarda en una carpeta
hermana del JSON — ``<stem>.assets/images/`` — para que el proyecto sea
autocontenido y portable: mover el JSON junto con su ``.assets/`` conserva
todos los retratos.

Los archivos se nombran por contenido (``sha256[:16] + ext``): importar dos
veces la misma imagen no duplica nada y las caches de pixmaps del host nunca
necesitan invalidación (imagen distinta ⇒ nombre distinto). En
``custom_metadata["_image_path"]`` se guarda la ruta RELATIVA al asset store
(separador ``/`` siempre); las rutas absolutas son legacy BETA1-F04 y se
siguen leyendo como fallback.

Solo stdlib (pathlib/shutil/hashlib): la deuda application→infrastructure/
persistence está congelada en ``tests/architecture`` y aquí no se añade nada.
La UI nunca escribe assets por su cuenta — siempre a través de este servicio.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from packages.domain.result import Error, Ok, Result

# Subcarpeta de retratos dentro del asset store (deja sitio a futuros tipos).
IMAGES_SUBDIR = "images"

# Formatos aceptados; "jpeg" se normaliza a "jpg" para nombrado estable.
ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".webp"})

# Longitud del prefijo de hash usado como nombre de archivo.
_HASH_LENGTH = 16


def assets_root_for(project_path: Path) -> Path:
    """Carpeta de assets hermana del JSON: ``mi-mundo.json`` → ``mi-mundo.assets``."""
    project_path = Path(project_path)
    return project_path.parent / f"{project_path.stem}.assets"


def _normalize_extension(ext: str) -> str | None:
    """``"JPEG"``/``".jpeg"``/``"jpg"`` → ``".jpg"``; no soportada ⇒ None."""
    cleaned = ext.strip().lower().lstrip(".")
    if cleaned == "jpeg":
        cleaned = "jpg"
    candidate = f".{cleaned}"
    return candidate if candidate in ALLOWED_EXTENSIONS else None


class ImageAssetService:
    """Importa, resuelve y limpia los binarios de imagen del proyecto."""

    def import_image_bytes(self, project_path: Path, data: bytes, ext: str) -> Result[str, str]:
        """Guarda ``data`` en el asset store y devuelve su ruta relativa.

        Content-addressed: si el archivo ya existe (misma imagen) no se
        reescribe. La escritura es a archivo nuevo con nombre final único por
        contenido, así una escritura fallida a medias se sobreescribe en el
        siguiente intento sin corromper nada ya referenciado.
        """
        if not data:
            return Error("Imagen vacía: no hay datos que importar")
        normalized = _normalize_extension(ext)
        if normalized is None:
            return Error(f"Formato de imagen no soportado: {ext!r} (png/jpg/webp)")
        digest = hashlib.sha256(data).hexdigest()[:_HASH_LENGTH]
        rel_path = f"{IMAGES_SUBDIR}/{digest}{normalized}"
        target = assets_root_for(project_path) / IMAGES_SUBDIR / f"{digest}{normalized}"
        try:
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        except OSError as exc:
            return Error(f"No se pudo guardar la imagen en el proyecto: {exc}")
        return Ok(rel_path)

    def import_image_file(self, project_path: Path, source: Path) -> Result[str, str]:
        """Importa un archivo del disco del usuario (lee y delega en bytes)."""
        source = Path(source)
        try:
            data = source.read_bytes()
        except OSError as exc:
            return Error(f"No se pudo leer la imagen {source.name}: {exc}")
        return self.import_image_bytes(project_path, data, source.suffix)

    def resolve(self, project_path: Path, rel_path: str) -> Path:
        """Ruta absoluta de un asset relativo (no comprueba existencia)."""
        return assets_root_for(project_path) / Path(rel_path)

    def delete_if_unreferenced(
        self, project_path: Path, rel_path: str, referenced: set[str]
    ) -> Result[bool, str]:
        """Borra el asset si ninguna entidad lo referencia ya.

        El llamador (host) recopila las rutas ``_image_path`` vivas de TODO el
        proyecto y las pasa en ``referenced``; aquí solo se decide y borra.
        Devuelve ``Ok(True)`` si se borró, ``Ok(False)`` si sigue referenciado
        o ya no existía.
        """
        if not rel_path or rel_path in referenced:
            return Ok(False)
        target = self.resolve(project_path, rel_path)
        try:
            if not target.exists():
                return Ok(False)
            target.unlink()
        except OSError as exc:
            return Error(f"No se pudo limpiar el asset huérfano: {exc}")
        return Ok(True)

    def copy_assets(self, old_project_path: Path, new_project_path: Path) -> Result[int, str]:
        """Copia el asset store al destino de un «guardar como».

        Devuelve el número de archivos copiados. Sin carpeta de origen (o
        origen == destino) no hay nada que hacer: ``Ok(0)``.
        """
        old_root = assets_root_for(old_project_path)
        new_root = assets_root_for(new_project_path)
        if not old_root.is_dir() or old_root == new_root:
            return Ok(0)
        copied = 0
        try:
            for source in sorted(old_root.rglob("*")):
                if not source.is_file():
                    continue
                target = new_root / source.relative_to(old_root)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied += 1
        except OSError as exc:
            return Error(f"No se pudieron copiar los assets del proyecto: {exc}")
        return Ok(copied)
