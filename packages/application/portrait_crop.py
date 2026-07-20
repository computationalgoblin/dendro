"""Encuadre del retrato de entidad (BETA2-IMG-01).

Modelo PURO (stdlib, sin Qt) del encuadre elegido por el usuario en el editor
de retrato: un recorte CUADRADO canónico sobre la imagen fuente, definido de
forma normalizada e independiente de la resolución:

- ``cx``, ``cy`` ∈ [0, 1]: centro del recorte en fracciones del ancho/alto de
  la imagen fuente;
- ``zoom`` ≥ 1: factor sobre el recorte máximo — el lado del cuadrado es
  ``min(w, h) / zoom``.

El encuadre se persiste en ``custom_metadata["_image_crop"]`` (ver
``docs/contracts/evolucion-esquema.md``). Cada superficie proyecta el mismo
encuadre a su forma: círculo en el grafo/satélites (recorte cuadrado) y banda
vertical en la tarjeta del foco (``source_rect_for_aspect``). Ojo con el
nombre: «viñeta» ya significa el gradiente radial de fondo de los lienzos
(``CHRONO_VIGNETTE``); esta feature usa siempre «retrato/portrait».
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Zoom máximo del editor: más allá el recorte degenera en píxeles sueltos.
MAX_ZOOM = 8.0

# Clave reservada de custom_metadata donde viaja el encuadre.
IMAGE_CROP_KEY = "_image_crop"

# Clave reservada de custom_metadata donde viaja la ruta de la imagen
# (relativa al asset store del proyecto; las absolutas son legacy BETA1-F04).
IMAGE_PATH_KEY = "_image_path"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _as_float(value: object, default: float) -> float:
    """Convierte tolerante a float finito; basura ⇒ ``default``."""
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


@dataclass(frozen=True)
class PortraitCrop:
    """Encuadre normalizado del retrato: centro fraccional + zoom."""

    cx: float = 0.5
    cy: float = 0.5
    zoom: float = 1.0

    def normalize(self) -> PortraitCrop:
        """Devuelve un encuadre con centro en [0,1] y zoom en [1, MAX_ZOOM]."""
        return PortraitCrop(
            cx=_clamp(_as_float(self.cx, 0.5), 0.0, 1.0),
            cy=_clamp(_as_float(self.cy, 0.5), 0.0, 1.0),
            zoom=_clamp(_as_float(self.zoom, 1.0), 1.0, MAX_ZOOM),
        )

    def source_rect(self, width: int, height: int) -> tuple[int, int, int]:
        """Recorte cuadrado canónico ``(x, y, lado)`` DENTRO de la imagen.

        El lado es ``min(w, h) / zoom`` y el rect se desplaza (clamp) para no
        salirse jamás de la imagen: el marco nunca muestra vacío. Dimensiones
        no positivas ⇒ rect degenerado ``(0, 0, 0)``.
        """
        if width <= 0 or height <= 0:
            return (0, 0, 0)
        crop = self.normalize()
        side = max(1, round(min(width, height) / crop.zoom))
        x = round(crop.cx * width - side / 2)
        y = round(crop.cy * height - side / 2)
        x = int(_clamp(x, 0, width - side))
        y = int(_clamp(y, 0, height - side))
        return (x, y, side)

    def source_rect_for_aspect(
        self, width: int, height: int, aspect: float
    ) -> tuple[int, int, int, int]:
        """Proyección del encuadre a proporción ``aspect`` (ancho/alto).

        Mismo centro y mismo zoom que el recorte canónico, pero el rect
        resultante es el mayor rectángulo de esa proporción que cabe en la
        imagen, dividido por el zoom y clampado dentro. Devuelve
        ``(x, y, ancho, alto)``. Usado por la banda vertical del foco.
        """
        if width <= 0 or height <= 0 or aspect <= 0:
            return (0, 0, 0, 0)
        crop = self.normalize()
        # Mayor rect con la proporción pedida que cabe en (width, height).
        base_w = float(width)
        base_h = base_w / aspect
        if base_h > height:
            base_h = float(height)
            base_w = base_h * aspect
        rect_w = max(1, round(base_w / crop.zoom))
        rect_h = max(1, round(base_h / crop.zoom))
        x = round(crop.cx * width - rect_w / 2)
        y = round(crop.cy * height - rect_h / 2)
        x = int(_clamp(x, 0, width - rect_w))
        y = int(_clamp(y, 0, height - rect_h))
        return (x, y, rect_w, rect_h)

    def to_dict(self) -> dict[str, float]:
        crop = self.normalize()
        return {"cx": crop.cx, "cy": crop.cy, "zoom": crop.zoom}

    def as_tuple(self) -> tuple[float, float, float]:
        """Tupla hashable ``(cx, cy, zoom)`` para view-models y caches."""
        crop = self.normalize()
        return (crop.cx, crop.cy, crop.zoom)


DEFAULT_CROP = PortraitCrop()


def parse_crop(value: object) -> PortraitCrop:
    """Encuadre desde metadata persistida; tolerante a basura ⇒ defaults.

    Acepta el dict guardado en ``custom_metadata["_image_crop"]`` o la tupla
    de un view-model; cualquier otra cosa (None, tipos raros, claves
    ausentes o corruptas) degrada al encuadre por defecto, campo a campo.
    """
    if isinstance(value, dict):
        return PortraitCrop(
            cx=_as_float(value.get("cx"), 0.5),
            cy=_as_float(value.get("cy"), 0.5),
            zoom=_as_float(value.get("zoom"), 1.0),
        ).normalize()
    if isinstance(value, (tuple, list)) and len(value) == 3:
        return PortraitCrop(
            cx=_as_float(value[0], 0.5),
            cy=_as_float(value[1], 0.5),
            zoom=_as_float(value[2], 1.0),
        ).normalize()
    return DEFAULT_CROP
