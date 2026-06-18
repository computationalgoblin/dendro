"""OpenAI-compatible HTTP AI provider with safe fallback (pre-B27 audit)."""

from __future__ import annotations
import json, os, urllib.request, urllib.error
from packages.infrastructure.ai_provider import AIProvider

class OpenAICompatibleProvider(AIProvider):
    provider_name = "openai_compatible"
    supports_command_bar_planner = True

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = base_url or os.environ.get("NARRATIVE_AI_BASE_URL", "")
        self.api_key = api_key or os.environ.get("NARRATIVE_AI_API_KEY", "")
        self.model = model or os.environ.get("NARRATIVE_AI_MODEL", "gpt-4o-mini")
        self.timeout = int(os.environ.get("NARRATIVE_AI_TIMEOUT", str(timeout or 300)))

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
            return body.get("choices", [{}])[0].get("message", {}).get("content", "")

        try:
            try:
                text = _send(json_mode)
            except urllib.error.HTTPError as http_err:
                # Endpoint may not support response_format → retry as plain text.
                if json_mode and http_err.code == 400:
                    text = _send(False)
                else:
                    raise
            return text, None
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
