"""Tests de packages/infrastructure/ddg_image_client.py (BETA2-IMG-04).

Sin red: ``urllib.request.urlopen`` monkeypatcheado siempre. Cubre el flujo en
dos pasos (token vqd + i.js), el parseo a WebImage, el User-Agent de navegador
y el fallback automático ante cualquier fallo del flujo DDG.
"""

import io
import json
import urllib.error

import pytest

from packages.domain.result import Error, Ok
from packages.infrastructure.ddg_image_client import (
    DdgImageClient,
    WebImage,
    default_image_search_client,
)

VQD_PAGE = b"...;vqd=\"4-123456789012345\";..."

SAMPLE_IJS = {
    "results": [
        {
            "title": "Guerrero medieval",
            "image": "https://img.example/full1.jpg",
            "thumbnail": "https://img.example/thumb1.jpg",
            "url": "https://blog.example/post",
            "width": 1200,
        },
        {
            "title": "Sin thumbnail",
            "image": "https://img.example/full2.png",
            "url": "https://otra.example/p",
        },
        {"title": "sin image — se descarta"},
        "basura-no-dict",
    ]
}


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def _patch_urlopen(monkeypatch, router):
    """``router(url)`` → bytes de respuesta (o lanza). Registra las peticiones."""
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append({"url": req.full_url, "headers": dict(req.header_items()), "timeout": timeout})
        return _FakeResponse(router(req.full_url))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return calls


def _happy_router(url: str) -> bytes:
    if url.startswith("https://duckduckgo.com/?"):
        return VQD_PAGE
    if url.startswith("https://duckduckgo.com/i.js?"):
        return json.dumps(SAMPLE_IJS).encode("utf-8")
    raise AssertionError(f"URL inesperada: {url}")


class TestSearch:
    def test_flujo_en_dos_pasos_y_parseo(self, monkeypatch):
        calls = _patch_urlopen(monkeypatch, _happy_router)
        result = DdgImageClient().search("guerrero medieval")
        assert isinstance(result, Ok)
        images = result.value
        assert len(images) == 2  # sin image o no-dict se descartan
        assert images[0] == WebImage(
            id="https://img.example/full1.jpg",
            title="Guerrero medieval",
            creator="blog.example",
            license="",
            thumbnail_url="https://img.example/thumb1.jpg",
            image_url="https://img.example/full1.jpg",
        )
        assert images[1].thumbnail_url == images[1].image_url
        # dos peticiones: página (vqd) + i.js
        assert len(calls) == 2
        assert "q=guerrero+medieval" in calls[0]["url"]
        ijs = calls[1]["url"]
        assert ijs.startswith("https://duckduckgo.com/i.js?")
        assert "vqd=4-123456789012345" in ijs
        assert "l=es-es" in ijs and "o=json" in ijs

    @pytest.mark.parametrize(
        "page_bytes",
        [
            b"vqd=\"4-111\";",
            b"vqd='4-222';",
            b"load('/d.js?q=x&vqd=4-333&kl=es');",
        ],
    )
    def test_vqd_variantes_de_comillas(self, monkeypatch, page_bytes):
        def router(url):
            if url.startswith("https://duckduckgo.com/?"):
                return page_bytes
            return json.dumps({"results": []}).encode("utf-8")

        calls = _patch_urlopen(monkeypatch, router)
        assert isinstance(DdgImageClient().search("x"), Ok)
        assert "vqd=4-" in calls[1]["url"]

    def test_user_agent_de_navegador(self, monkeypatch):
        calls = _patch_urlopen(monkeypatch, _happy_router)
        DdgImageClient().search("x")
        for call in calls:
            agents = [v for k, v in call["headers"].items() if k.lower() == "user-agent"]
            assert agents and "Mozilla" in agents[0]

    def test_ijs_lleva_cabeceras_xhr(self, monkeypatch):
        # Sin Sec-Fetch + Accept JSON el endpoint i.js responde 403
        # (verificado en vivo 2026-07-05) — el contrato queda clavado aquí.
        calls = _patch_urlopen(monkeypatch, _happy_router)
        DdgImageClient().search("x")
        headers = {k.lower(): v for k, v in calls[1]["headers"].items()}
        assert headers.get("sec-fetch-mode") == "cors"
        assert headers.get("sec-fetch-site") == "same-origin"
        assert "application/json" in headers.get("accept", "")
        assert headers.get("referer") == "https://duckduckgo.com/"

    def test_page_size_recorta(self, monkeypatch):
        many = {"results": [{"title": f"t{i}", "image": f"https://a/{i}.jpg"} for i in range(30)]}

        def router(url):
            if url.startswith("https://duckduckgo.com/?"):
                return VQD_PAGE
            return json.dumps(many).encode("utf-8")

        _patch_urlopen(monkeypatch, router)
        result = DdgImageClient().search("x", page_size=5)
        assert isinstance(result, Ok)
        assert len(result.value) == 5

    def test_query_vacia_es_error_sin_red(self, monkeypatch):
        def boom(req, timeout=None):
            raise AssertionError("no debe tocar la red")

        monkeypatch.setattr("urllib.request.urlopen", boom)
        assert isinstance(DdgImageClient().search("  "), Error)

    def test_sin_vqd_sin_fallback_es_error(self, monkeypatch):
        _patch_urlopen(monkeypatch, lambda url: b"<html>pagina sin token</html>")
        result = DdgImageClient().search("x")
        assert isinstance(result, Error)
        assert "DuckDuckGo" in result.error


class _FakeFallback:
    def __init__(self):
        self.calls = []

    def search(self, query, page=1, page_size=20):
        self.calls.append((query, page, page_size))
        return Ok([WebImage("f", "Fallback", "", "cc0", "https://f/t.jpg", "https://f/i.jpg")])


class TestFallback:
    def test_fallo_ddg_degrada_al_fallback(self, monkeypatch):
        def raise_http(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

        monkeypatch.setattr("urllib.request.urlopen", raise_http)
        fallback = _FakeFallback()
        result = DdgImageClient(fallback=fallback).search("guerrero", page=2, page_size=7)
        assert isinstance(result, Ok)
        assert result.value[0].title == "Fallback"
        assert fallback.calls == [("guerrero", 2, 7)]

    def test_json_ilegible_tambien_degrada(self, monkeypatch):
        def router(url):
            if url.startswith("https://duckduckgo.com/?"):
                return VQD_PAGE
            return b"<html>no json</html>"

        _patch_urlopen(monkeypatch, router)
        fallback = _FakeFallback()
        assert isinstance(DdgImageClient(fallback=fallback).search("x"), Ok)
        assert len(fallback.calls) == 1

    def test_exito_ddg_no_toca_el_fallback(self, monkeypatch):
        _patch_urlopen(monkeypatch, _happy_router)
        fallback = _FakeFallback()
        result = DdgImageClient(fallback=fallback).search("x")
        assert isinstance(result, Ok)
        assert fallback.calls == []

    def test_query_vacia_no_degrada(self, monkeypatch):
        fallback = _FakeFallback()
        assert isinstance(DdgImageClient(fallback=fallback).search(" "), Error)
        assert fallback.calls == []


class TestDownload:
    def test_descarga_con_ua_navegador_y_sin_referer_externo(self, monkeypatch):
        calls = _patch_urlopen(monkeypatch, lambda url: b"imagen-bytes")
        result = DdgImageClient().download("https://img.example/full1.jpg")
        assert result == Ok(b"imagen-bytes")
        headers = {k.lower(): v for k, v in calls[0]["headers"].items()}
        assert "Mozilla" in headers["user-agent"]
        assert "referer" not in headers  # anti-hotlink: sin referer de terceros

    def test_esquema_no_http_es_error(self, monkeypatch):
        def boom(req, timeout=None):
            raise AssertionError("no debe tocar la red")

        monkeypatch.setattr("urllib.request.urlopen", boom)
        assert isinstance(DdgImageClient().download("file:///x"), Error)

    def test_vacia_o_http_error(self, monkeypatch):
        _patch_urlopen(monkeypatch, lambda url: b"")
        assert isinstance(DdgImageClient().download("https://a/b.png"), Error)

        def raise_404(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

        monkeypatch.setattr("urllib.request.urlopen", raise_404)
        assert isinstance(DdgImageClient().download("https://a/b.png"), Error)


def test_default_client_es_ddg_con_fallback_openverse():
    from packages.infrastructure.openverse_client import OpenverseClient

    client = default_image_search_client()
    assert isinstance(client, DdgImageClient)
    assert isinstance(client.fallback, OpenverseClient)
