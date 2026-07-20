"""Tests de packages/infrastructure/openverse_client.py (BETA2-IMG-02).

Sin red: ``urllib.request.urlopen`` se monkeypatchea siempre (el suite corre
con ``filterwarnings = error`` y sin conectividad garantizada).
"""

import io
import json
import urllib.error

import pytest

from packages.domain.result import Error, Ok
from packages.infrastructure.openverse_client import OpenverseClient, OpenverseImage

SAMPLE_RESPONSE = {
    "result_count": 2,
    "results": [
        {
            "id": "abc-1",
            "title": "Dragón rojo",
            "creator": "Alguien",
            "license": "cc0",
            "url": "https://img.example/full1.jpg",
            "thumbnail": "https://img.example/thumb1.jpg",
        },
        {
            "id": "abc-2",
            "title": "Castillo",
            "creator": "",
            "license": "by",
            "url": "https://img.example/full2.png",
            # sin thumbnail: debe caer a la URL completa
        },
        {"id": "abc-3", "title": "sin url — se descarta"},
        "basura-no-dict",
    ],
}


class _FakeResponse(io.BytesIO):
    """Respuesta mínima compatible con el context manager de urlopen."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def _patch_urlopen(monkeypatch, handler):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["timeout"] = timeout
        return handler(req)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return captured


class TestSearch:
    def test_parsea_resultados_reales(self, monkeypatch):
        _patch_urlopen(
            monkeypatch,
            lambda req: _FakeResponse(json.dumps(SAMPLE_RESPONSE).encode("utf-8")),
        )
        result = OpenverseClient().search("dragón rojo")
        assert isinstance(result, Ok)
        images = result.value
        assert len(images) == 2  # los items sin url o no-dict se descartan
        assert images[0] == OpenverseImage(
            id="abc-1",
            title="Dragón rojo",
            creator="Alguien",
            license="cc0",
            thumbnail_url="https://img.example/thumb1.jpg",
            image_url="https://img.example/full1.jpg",
        )
        assert images[1].thumbnail_url == images[1].image_url

    def test_codifica_query_y_paginacion_en_la_url(self, monkeypatch):
        captured = _patch_urlopen(
            monkeypatch, lambda req: _FakeResponse(b'{"results": []}')
        )
        OpenverseClient().search("dragón rojo", page=2, page_size=10)
        assert "q=drag%C3%B3n+rojo" in captured["url"]
        assert "page=2" in captured["url"]
        assert "page_size=10" in captured["url"]
        assert captured["url"].startswith("https://api.openverse.org/v1/images/?")
        assert any("narrative-architect" in v for v in captured["headers"].values())

    def test_query_vacia_es_error_sin_red(self, monkeypatch):
        def boom(req, timeout=None):
            raise AssertionError("no debe tocar la red")

        monkeypatch.setattr("urllib.request.urlopen", boom)
        assert isinstance(OpenverseClient().search("   "), Error)

    def test_timeout_configurado_se_propaga(self, monkeypatch):
        captured = _patch_urlopen(
            monkeypatch, lambda req: _FakeResponse(b'{"results": []}')
        )
        OpenverseClient(timeout=7).search("x")
        assert captured["timeout"] == 7

    def test_http_429_mensaje_amable(self, monkeypatch):
        def raise_429(req):
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

        _patch_urlopen(monkeypatch, raise_429)
        result = OpenverseClient().search("x")
        assert isinstance(result, Error)
        assert "espera" in result.error.lower()

    def test_http_error_generico(self, monkeypatch):
        def raise_500(req):
            raise urllib.error.HTTPError(req.full_url, 500, "Server Error", {}, None)

        _patch_urlopen(monkeypatch, raise_500)
        result = OpenverseClient().search("x")
        assert isinstance(result, Error)
        assert "500" in result.error

    def test_sin_conexion_es_error(self, monkeypatch):
        def raise_url_error(req):
            raise urllib.error.URLError("dns caído")

        _patch_urlopen(monkeypatch, raise_url_error)
        result = OpenverseClient().search("x")
        assert isinstance(result, Error)

    def test_json_invalido_es_error(self, monkeypatch):
        _patch_urlopen(monkeypatch, lambda req: _FakeResponse(b"<html>no json</html>"))
        assert isinstance(OpenverseClient().search("x"), Error)

    def test_forma_inesperada_es_error(self, monkeypatch):
        _patch_urlopen(monkeypatch, lambda req: _FakeResponse(b'{"detail": "rarito"}'))
        assert isinstance(OpenverseClient().search("x"), Error)


class TestDownload:
    def test_descarga_bytes(self, monkeypatch):
        _patch_urlopen(monkeypatch, lambda req: _FakeResponse(b"imagen-bytes"))
        result = OpenverseClient().download("https://img.example/full1.jpg")
        assert result == Ok(b"imagen-bytes")

    def test_esquema_no_http_es_error_sin_red(self, monkeypatch):
        def boom(req, timeout=None):
            raise AssertionError("no debe tocar la red")

        monkeypatch.setattr("urllib.request.urlopen", boom)
        assert isinstance(OpenverseClient().download("file:///etc/passwd"), Error)

    def test_vacia_es_error(self, monkeypatch):
        _patch_urlopen(monkeypatch, lambda req: _FakeResponse(b""))
        assert isinstance(OpenverseClient().download("https://img.example/x.png"), Error)

    def test_http_error_es_error(self, monkeypatch):
        def raise_404(req):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

        _patch_urlopen(monkeypatch, raise_404)
        result = OpenverseClient().download("https://img.example/x.png")
        assert isinstance(result, Error)
        assert "404" in result.error


@pytest.mark.parametrize("kind", ["search", "download"])
def test_never_raises_en_fallos_de_red(monkeypatch, kind):
    def raise_url_error(req):
        raise urllib.error.URLError(TimeoutError("timed out"))

    _patch_urlopen(monkeypatch, raise_url_error)
    client = OpenverseClient()
    result = client.search("x") if kind == "search" else client.download("https://a/b.png")
    assert isinstance(result, Error)
