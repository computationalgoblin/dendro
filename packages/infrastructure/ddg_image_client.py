"""Cliente de búsqueda de imágenes en DuckDuckGo (BETA2-IMG-04).

Remediación del smoke de BETA2-IMG-02: Openverse (solo licencia libre,
etiquetado en inglés) devolvía resultados poco relevantes para consultas como
«guerrero». DuckDuckGo Images busca en toda la web y entiende español, sin API
key. Su endpoint es NO oficial (el que usa su propia web): flujo en dos pasos
— obtener el token ``vqd`` de la página de búsqueda y pedir ``i.js`` con él.
Estable desde hace años, pero puede cambiar; por eso el cliente acepta un
``fallback`` (Openverse) al que degrada ante CUALQUIER fallo del flujo DDG.

Mismo patrón que ``openverse_client.py``: ``urllib`` de stdlib + ``Result``,
síncrono y bloqueante (el host lo envuelve en workers QThread). Uso privado:
los retratos son material del proyecto del usuario, sin avisos de licencia
(decisión de producto 2026-07-05).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from packages.domain.result import Error, Ok, Result

DEFAULT_TIMEOUT = 15

# UA de navegador: tanto DDG como los hosts de imágenes de la web abierta
# rechazan o degradan user-agents no-navegador.
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Tope de descarga de una imagen elegida: contra respuestas desbocadas.
_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024

# El token vqd aparece en la página como vqd=4-123…, vqd="…" o vqd='…'.
_VQD_PATTERNS = (
    re.compile(r"vqd=\"([\d-]+)\""),
    re.compile(r"vqd='([\d-]+)'"),
    re.compile(r"vqd=([\d-]+)"),
)

# i.js exige parecer una petición XHR del propio buscador: sin estas cabeceras
# Sec-Fetch + Accept JSON responde 403 (verificado en vivo 2026-07-05).
_IJS_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


@dataclass(frozen=True)
class WebImage:
    """Resultado de búsqueda web — misma forma (duck-typed) que OpenverseImage."""

    id: str
    title: str
    creator: str
    license: str
    thumbnail_url: str
    image_url: str


def _domain_of(url: str) -> str:
    return urllib.parse.urlparse(str(url or "")).netloc


class DdgImageClient:
    """Búsqueda de imágenes en la web abierta vía DuckDuckGo, con fallback."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, fallback=None):
        self.timeout = timeout
        self.fallback = fallback

    # ── búsqueda ────────────────────────────────────────────────────────

    def search(self, query: str, page: int = 1, page_size: int = 20) -> Result[list[WebImage], str]:
        """Busca imágenes; ante cualquier fallo DDG degrada al fallback."""
        query = query.strip()
        if not query:
            return Error("Escribe algo que buscar")
        result = self._search_ddg(query, page, page_size)
        if isinstance(result, Error) and self.fallback is not None:
            return self.fallback.search(query, page=page, page_size=page_size)
        return result

    def _search_ddg(self, query: str, page: int, page_size: int) -> Result[list[WebImage], str]:
        vqd = self._fetch_vqd(query)
        if isinstance(vqd, Error):
            return vqd
        params = urllib.parse.urlencode(
            {
                "l": "es-es",
                "o": "json",
                "q": query,
                "vqd": vqd.value,
                "f": ",,,",
                "p": max(1, page),
            }
        )
        url = f"https://duckduckgo.com/i.js?{params}"
        body = self._get(url, extra_headers=_IJS_HEADERS)
        if isinstance(body, Error):
            return body
        try:
            data = json.loads(body.value.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return Error(f"DuckDuckGo devolvió una respuesta ilegible: {exc}")
        raw_results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(raw_results, list):
            return Error("DuckDuckGo no devolvió resultados de imágenes")
        images: list[WebImage] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            image_url = str(item.get("image") or "")
            if not image_url:
                continue
            source_page = str(item.get("url") or "")
            images.append(
                WebImage(
                    id=image_url,
                    title=str(item.get("title") or ""),
                    creator=_domain_of(source_page),
                    license="",  # web abierta: sin metadato de licencia
                    thumbnail_url=str(item.get("thumbnail") or image_url),
                    image_url=image_url,
                )
            )
            if len(images) >= max(1, page_size):
                break
        return Ok(images)

    def _fetch_vqd(self, query: str) -> Result[str, str]:
        """Paso 1 del flujo no oficial: token ``vqd`` de la página de búsqueda."""
        params = urllib.parse.urlencode({"q": query, "iax": "images", "ia": "images"})
        body = self._get(f"https://duckduckgo.com/?{params}")
        if isinstance(body, Error):
            return body
        text = body.value.decode("utf-8", "replace")
        for pattern in _VQD_PATTERNS:
            match = pattern.search(text)
            if match:
                return Ok(match.group(1))
        return Error("DuckDuckGo no respondió como se esperaba (token de búsqueda no encontrado)")

    # ── descarga ────────────────────────────────────────────────────────

    def download(self, url: str) -> Result[bytes, str]:
        """Descarga una imagen (miniatura o completa) como bytes."""
        scheme = urllib.parse.urlparse(url).scheme
        if scheme not in ("http", "https"):
            return Error(f"URL de imagen no válida: {url!r}")
        result = self._get(url)
        if isinstance(result, Error):
            return result
        data = result.value
        if not data:
            return Error("La imagen descargada llegó vacía")
        if len(data) > _MAX_DOWNLOAD_BYTES:
            return Error("La imagen es demasiado grande (más de 20 MB)")
        return Ok(data)

    # ── HTTP común ──────────────────────────────────────────────────────

    def _get(self, url: str, extra_headers: dict | None = None) -> Result[bytes, str]:
        headers = {
            "User-Agent": _BROWSER_USER_AGENT,
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        }
        # El Referer de DDG solo para el propio DDG: los hosts de imágenes con
        # protección anti-hotlink reaccionan mal a referers de terceros.
        if _domain_of(url).endswith("duckduckgo.com"):
            headers["Referer"] = "https://duckduckgo.com/"
        headers.update(extra_headers or {})
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return Ok(resp.read(_MAX_DOWNLOAD_BYTES + 1))
        except urllib.error.HTTPError as http_err:
            return Error(f"DuckDuckGo respondió HTTP {http_err.code}: {http_err.reason}")
        except urllib.error.URLError as url_err:
            return Error(f"Sin conexión: {url_err.reason}")
        except TimeoutError:
            return Error("La petición tardó demasiado")


def default_image_search_client():
    """Cliente por defecto del diálogo: DuckDuckGo con fallback a Openverse."""
    from packages.infrastructure.openverse_client import OpenverseClient

    return DdgImageClient(fallback=OpenverseClient())
