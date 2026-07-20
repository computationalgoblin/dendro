"""Cliente de búsqueda de imágenes en Openverse (BETA2-IMG-02).

API pública y estable de imágenes con licencia abierta
(https://api.openverse.org/v1/images/): sin API key ni registro. Mismo patrón
HTTP que ``openai_compatible_provider.py`` (``urllib.request`` de stdlib, sin
dependencias nuevas). Lo consume el host desktop directamente (precedente:
``workspaces.py`` con ``get_provider``); la capa application no lo importa —
la deuda application→infrastructure está congelada en ``tests/architecture``.

El cliente es síncrono y bloqueante a propósito: el host lo envuelve en
workers ``QThread`` (``image_search_dialog.py``) y aquí solo viven la petición
y el parseo.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from packages.domain.result import Error, Ok, Result

DEFAULT_BASE_URL = "https://api.openverse.org/v1"
DEFAULT_TIMEOUT = 15

# Identificación honesta ante la API (Openverse la pide para clientes anónimos).
_USER_AGENT = "narrative-architect/beta2 (buscador de retratos de entidad)"

# Tope de descarga de una imagen elegida: contra respuestas desbocadas.
_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class OpenverseImage:
    """Resultado de búsqueda: lo justo para la rejilla y la descarga."""

    id: str
    title: str
    creator: str
    license: str
    thumbnail_url: str
    image_url: str


def _friendly_http_error(http_err: urllib.error.HTTPError) -> str:
    if http_err.code == 429:
        return "Demasiadas búsquedas seguidas — espera un momento y reintenta."
    return f"Openverse respondió HTTP {http_err.code}: {http_err.reason}"


class OpenverseClient:
    """Búsqueda y descarga de imágenes con licencia abierta."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(
        self, query: str, page: int = 1, page_size: int = 20
    ) -> Result[list[OpenverseImage], str]:
        """Busca imágenes; devuelve resultados con miniatura y URL completa."""
        query = query.strip()
        if not query:
            return Error("Escribe algo que buscar")
        params = urllib.parse.urlencode(
            {"q": query, "page": max(1, page), "page_size": max(1, page_size)}
        )
        url = f"{self.base_url}/images/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as http_err:
            return Error(_friendly_http_error(http_err))
        except urllib.error.URLError as url_err:
            return Error(f"Sin conexión con Openverse: {url_err.reason}")
        except (json.JSONDecodeError, UnicodeDecodeError, TimeoutError) as exc:
            return Error(f"Respuesta ilegible de Openverse: {exc}")
        raw_results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(raw_results, list):
            return Error("Respuesta inesperada de Openverse (sin resultados)")
        images: list[OpenverseImage] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            image_url = str(item.get("url") or "")
            if not image_url:
                continue
            images.append(
                OpenverseImage(
                    id=str(item.get("id") or ""),
                    title=str(item.get("title") or ""),
                    creator=str(item.get("creator") or ""),
                    license=str(item.get("license") or ""),
                    thumbnail_url=str(item.get("thumbnail") or image_url),
                    image_url=image_url,
                )
            )
        return Ok(images)

    def download(self, url: str) -> Result[bytes, str]:
        """Descarga una imagen (miniatura o completa) como bytes."""
        scheme = urllib.parse.urlparse(url).scheme
        if scheme not in ("http", "https"):
            return Error(f"URL de imagen no válida: {url!r}")
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read(_MAX_DOWNLOAD_BYTES + 1)
        except urllib.error.HTTPError as http_err:
            return Error(_friendly_http_error(http_err))
        except urllib.error.URLError as url_err:
            return Error(f"No se pudo descargar la imagen: {url_err.reason}")
        except TimeoutError:
            return Error("La descarga de la imagen tardó demasiado")
        if not data:
            return Error("La imagen descargada llegó vacía")
        if len(data) > _MAX_DOWNLOAD_BYTES:
            return Error("La imagen es demasiado grande (más de 20 MB)")
        return Ok(data)
