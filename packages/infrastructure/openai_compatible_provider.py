"""OpenAI-compatible HTTP AI provider with safe fallback (pre-B27 audit)."""

from __future__ import annotations
import json, os, urllib.request, urllib.error
from packages.infrastructure.ai_provider import AIProvider


def _http_error_detail(http_err: urllib.error.HTTPError) -> str:
    """Mensaje de error legible que INCLUYE el cuerpo de la respuesta.

    Un 400 de un endpoint compatible con OpenAI casi siempre trae un cuerpo JSON
    (``{"error": {"message": ...}}``) explicando la causa real (longitud de
    contexto excedida, parámetro no soportado, max_tokens demasiado alto, …). Sin
    leerlo, el usuario solo veía "HTTP Error 400: Bad Request", inservible para
    diagnosticar. El cuerpo de un ``HTTPError`` solo puede leerse UNA vez."""
    base = f"HTTP {http_err.code}: {http_err.reason}"
    try:
        raw = http_err.read().decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001 — el detalle es best-effort
        return base
    if not raw:
        return base
    try:
        data = json.loads(raw)
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            message = err.get("message") or err.get("code") or ""
        elif isinstance(err, str):
            message = err
        else:
            message = data.get("message") if isinstance(data, dict) else ""
        if message:
            return f"{base} — {message}"
    except Exception:  # noqa: BLE001 — cuerpo no-JSON: recorta el texto crudo
        pass
    return f"{base} — {raw[:500]}"

class OpenAICompatibleProvider(AIProvider):
    provider_name = "openai_compatible"

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = base_url or os.environ.get("NARRATIVE_AI_BASE_URL", "")
        self.api_key = api_key or os.environ.get("NARRATIVE_AI_API_KEY", "")
        self.model = model or os.environ.get("NARRATIVE_AI_MODEL", "gpt-4o-mini")
        self.timeout = int(os.environ.get("NARRATIVE_AI_TIMEOUT", str(timeout or 300)))
        # WS-K: canal lateral con el `finish_reason` de la última respuesta
        # ("length" = truncada por max_tokens). No cambia la firma de chat().
        self.last_finish_reason = ""

    def chat(self, system_prompt: str, user_message: str, timeout=None, *,
             temperature: float | None = None, max_tokens: int | None = None,
             json_mode: bool = False):
        """Direct chat completion with a custom system prompt.

        BETA1-AI01: honours per-intent temperature/max_tokens and, when
        ``json_mode`` is set, asks for a strict JSON object response."""
        if not self.base_url or not self.api_key:
            return None, "Configura API key y base URL para usar el asistente."
        # OpenAI's json_object mode requires the word "json" somewhere in the
        # prompt; add a discreet hint if the caller didn't include it.
        if json_mode and "json" not in f"{system_prompt}\n{user_message}".lower():
            system_prompt = f"{system_prompt}\n\nResponde únicamente con un objeto JSON válido."
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        timeout_val = timeout or self.timeout

        def _send(use_json_mode: bool):
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": int(max_tokens) if max_tokens else 2000,
                "temperature": float(temperature) if temperature is not None else 0.7,
            }
            if use_json_mode:
                payload["response_format"] = {"type": "json_object"}
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=timeout_val)
            body = json.loads(resp.read())
            choice = body.get("choices", [{}])[0]
            # WS-K: registra por qué terminó la generación (length = truncada).
            self.last_finish_reason = str(choice.get("finish_reason", "") or "")
            return choice.get("message", {}).get("content", "")

        self.last_finish_reason = ""  # se rellena en _send con la respuesta real
        try:
            try:
                text = _send(json_mode)
            except urllib.error.HTTPError as http_err:
                # Endpoint may not support response_format → retry as plain text.
                # OJO: no leer el cuerpo aquí (read() lo consume); si el reintento
                # también falla, su HTTPError se formatea abajo con su cuerpo intacto.
                if json_mode and http_err.code == 400:
                    text = _send(False)
                else:
                    raise
            return text, None
        except urllib.error.HTTPError as http_err:
            # Surface the provider's actual reason (cuerpo JSON), no solo el código.
            return None, _http_error_detail(http_err)
        except Exception as e:
            return None, str(e)

def get_provider() -> AIProvider:
    """Pick the AI provider from NARRATIVE_AI_* env vars.

    BETA1-AI01: no longer a footgun. If base_url + api_key are configured, the
    real provider is used even when NARRATIVE_AI_PROVIDER isn't the exact magic
    string. Only an explicit ``simulated`` forces the local fallback.
    """
    from packages.infrastructure.ai_provider import SimulatedAIProvider

    provider_type = os.environ.get("NARRATIVE_AI_PROVIDER", "").strip().lower()
    base_url = os.environ.get("NARRATIVE_AI_BASE_URL", "").strip()
    api_key = os.environ.get("NARRATIVE_AI_API_KEY", "").strip()

    if provider_type == "simulated":
        return SimulatedAIProvider()
    if provider_type in ("openai_compatible", "openai") or (base_url and api_key):
        return OpenAICompatibleProvider()
    return SimulatedAIProvider()
