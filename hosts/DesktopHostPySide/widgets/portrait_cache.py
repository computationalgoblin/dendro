"""Cache de retratos recortados para las superficies (BETA2-IMG-03).

Los items del grafo/foco piden aquí el pixmap YA recortado y escalado — nunca
cargan del disco dentro de ``paint()``. Claves por ``(ruta, encuadre, tamaño)``
con tamaños en buckets (64/128/256) para que el zoom del lienzo no multiplique
entradas. Los assets se nombran por contenido (``image_asset_service``), así
que una imagen distinta siempre tiene ruta distinta y la cache no necesita
invalidación por mtime; ``clear_portrait_cache()`` queda para tests y para
«Quitar imagen».
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPixmap

from packages.application.portrait_crop import PortraitCrop, parse_crop

SIZE_BUCKETS = (64, 128, 256)

# Topes defensivos: al llegar se vacía entera (los retratos se regeneran
# baratos desde la cache de QImage; no merece un LRU de verdad).
_MAX_PIXMAPS = 512
_MAX_SOURCES = 32

_source_cache: dict[str, QImage | None] = {}
_pixmap_cache: dict[tuple, QPixmap | None] = {}


def clear_portrait_cache() -> None:
    _source_cache.clear()
    _pixmap_cache.clear()


def bucket_for(size: float) -> int:
    for bucket in SIZE_BUCKETS:
        if size <= bucket:
            return bucket
    return SIZE_BUCKETS[-1]


def resolve_stored(assets_root: Path | None, stored: str) -> Path | None:
    """Ruta absoluta de un ``_image_path`` guardado, o None si no localizable.

    Relativa ⇒ bajo ``assets_root`` (el lienzo lo recibe del workspace);
    absoluta ⇒ legacy BETA1-F04. Archivo ausente ⇒ None (degradación
    silenciosa: la superficie pinta su render clásico sin imagen).
    """
    stored = str(stored or "")
    if not stored:
        return None
    if os.path.isabs(stored):
        candidate = Path(stored)
        return candidate if candidate.exists() else None
    if assets_root is None:
        return None
    candidate = Path(assets_root) / stored
    return candidate if candidate.exists() else None


def _as_crop(crop) -> PortraitCrop:
    if isinstance(crop, PortraitCrop):
        return crop.normalize()
    return parse_crop(crop)


def _source_image(path: Path) -> QImage | None:
    key = str(path)
    if key not in _source_cache:
        if len(_source_cache) >= _MAX_SOURCES:
            _source_cache.clear()
        image = QImage(key)
        _source_cache[key] = None if image.isNull() else image
    return _source_cache[key]


def portrait_pixmap(path: Path | None, crop, size: float) -> QPixmap | None:
    """Retrato CUADRADO (encuadre canónico) escalado al bucket de ``size``."""
    if path is None:
        return None
    normalized = _as_crop(crop)
    bucket = bucket_for(size)
    key = ("sq", str(path), normalized.as_tuple(), bucket)
    if key in _pixmap_cache:
        return _pixmap_cache[key]
    result: QPixmap | None = None
    image = _source_image(Path(path))
    if image is not None:
        x, y, side = normalized.source_rect(image.width(), image.height())
        if side > 0:
            square = image.copy(QRect(x, y, side, side)).scaled(
                bucket,
                bucket,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            result = QPixmap.fromImage(square)
    if len(_pixmap_cache) >= _MAX_PIXMAPS:
        _pixmap_cache.clear()
    _pixmap_cache[key] = result
    return result


def portrait_band_pixmap(path: Path | None, crop, width: int, height: int) -> QPixmap | None:
    """Banda vertical de la tarjeta del foco: mismo centro/zoom, proporción w/h.

    El alto se bucketiza a saltos de 64 px para que el resize de la tarjeta no
    regenere el pixmap en cada frame (el widget lo estira el resto).
    """
    if path is None or width <= 0 or height <= 0:
        return None
    normalized = _as_crop(crop)
    bucket_h = max(64, round(height / 64.0) * 64)
    key = ("band", str(path), normalized.as_tuple(), int(width), bucket_h)
    if key in _pixmap_cache:
        return _pixmap_cache[key]
    result: QPixmap | None = None
    image = _source_image(Path(path))
    if image is not None:
        x, y, rect_w, rect_h = normalized.source_rect_for_aspect(
            image.width(), image.height(), width / bucket_h
        )
        if rect_w > 0 and rect_h > 0:
            band = image.copy(QRect(x, y, rect_w, rect_h)).scaled(
                int(width),
                bucket_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            result = QPixmap.fromImage(band)
    if len(_pixmap_cache) >= _MAX_PIXMAPS:
        _pixmap_cache.clear()
    _pixmap_cache[key] = result
    return result
