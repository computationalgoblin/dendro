"""El proveedor compatible OpenAI debe SURFACE el cuerpo de un error HTTP.

Antes, un 400 (longitud de contexto, parámetro no soportado, max_tokens alto…) se
reportaba como un opaco "HTTP Error 400: Bad Request" porque solo se usaba
``str(HTTPError)``. El cuerpo JSON del error (``error.message``) es el dato que
permite diagnosticar y actuar; este test fija que se incluya.
"""

from __future__ import annotations

import io
import urllib.error

from packages.infrastructure.openai_compatible_provider import OpenAICompatibleProvider


def _http_error(code: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="http://x/chat/completions", code=code, msg="Bad Request",
        hdrs=None, fp=io.BytesIO(body),
    )


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url="http://x", api_key="k", model="m", timeout=5
    )


def test_http_400_surfaces_json_error_message(monkeypatch):
    body = (
        b'{"error": {"message": "max_tokens is too large: 4000",'
        b' "type": "invalid_request_error"}}'
    )

    def _raise(_req, timeout=None):
        raise _http_error(400, body)

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    text, error = _provider().chat("sys", "user")
    assert text is None
    assert "400" in error
    assert "max_tokens is too large" in error  # el motivo real, no solo "Bad Request"


def test_http_400_non_json_body_is_truncated(monkeypatch):
    def _raise(_req, timeout=None):
        raise _http_error(400, b"upstream proxy error: gateway said no")

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    _text, error = _provider().chat("sys", "user")
    assert "400" in error and "gateway said no" in error


def test_json_mode_400_retries_without_response_format(monkeypatch):
    """Si el endpoint no soporta response_format, el 400 inicial reintenta en
    texto plano; un reintento OK devuelve contenido (no error)."""
    calls = {"n": 0}

    class _Resp(io.BytesIO):
        def read(self, *a):  # noqa: D401 - file-like
            return b'{"choices": [{"message": {"content": "ok"}}]}'

    def _fake(_req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(400, b'{"error": {"message": "response_format unsupported"}}')
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _fake)
    text, error = _provider().chat("sys", "user", json_mode=True)
    assert error is None and text == "ok"
    assert calls["n"] == 2  # primer intento (json) + reintento (texto plano)


def test_json_mode_400_retry_also_fails_surfaces_body(monkeypatch):
    """Si el reintento sin json también da 400, se surface su cuerpo (intacto)."""
    def _fake(_req, timeout=None):
        raise _http_error(400, b'{"error": {"message": "context_length_exceeded"}}')

    monkeypatch.setattr("urllib.request.urlopen", _fake)
    text, error = _provider().chat("sys", "user", json_mode=True)
    assert text is None
    assert "context_length_exceeded" in error
