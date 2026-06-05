"""OpenAI-compatible HTTP AI provider with safe fallback (pre-B27 audit)."""

from __future__ import annotations
import json, os, time, urllib.request, urllib.error, uuid
from packages.infrastructure.ai_provider import AIProvider
from packages.domain.ai_models import AIResponse

class OpenAICompatibleProvider(AIProvider):
    provider_name = "openai_compatible"

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = base_url or os.environ.get("NARRATIVE_AI_BASE_URL", "")
        self.api_key = api_key or os.environ.get("NARRATIVE_AI_API_KEY", "")
        self.model = model or os.environ.get("NARRATIVE_AI_MODEL", "gpt-4o-mini")
        self.timeout = int(os.environ.get("NARRATIVE_AI_TIMEOUT", str(timeout or 300)))

    def invoke(self, operation):
        """Legacy invoke — do not use in new features (B42+).

        New code should use AIRequestGateway or provider.chat() instead.
        This method uses a trivially basic prompt that loses all B40 context.
        """
        t0 = time.time()
        if not self.base_url or not self.api_key:
            return self._fallback(operation, "Missing API key or base URL", t0)
        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            prompt = self._build_prompt(operation)
            data = json.dumps({"model": self.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 500, "temperature": 0.7}).encode()
            req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, method="POST")
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            body = json.loads(resp.read())
            text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            return self._parse(operation, text, t0, body)
        except Exception as e:
            return self._fallback(operation, str(e), t0)

    def _build_prompt(self, operation):
        mode = operation.mode.value if hasattr(operation.mode, 'value') else str(operation.mode)
        return f"[{mode}] instruction. Context: {operation.context or ''}. Respond concisely."

    def _parse(self, operation, text, t0, raw_body=None):
        if not text or len(text.strip()) < 3:
            return self._fallback(operation, "Empty response", t0)
        candidates = []
        try:
            if "entity" in str(operation.mode).lower():
                candidates = [{"name": l.strip("- "), "entity_type": "personaje"} for l in text.split("\n") if len(l.strip()) > 3][:operation.max_candidates or 2]
            else:
                candidates = [{"text": text}]
        except Exception:
            candidates = [{"text": text}]
        return AIResponse(id=str(uuid.uuid4()), operation=operation, raw_text=text, candidates=candidates, provider=f"{self.provider_name}/{self.model}", latency_ms=(time.time()-t0)*1000)

    def _fallback(self, operation, reason, t0):
        from packages.infrastructure.ai_provider import SimulatedAIProvider
        resp = SimulatedAIProvider().invoke(operation)
        resp.observations.append(f"[{self.provider_name}/{self.model}] {reason} — fallback to simulated")
        resp.provider = f"{self.provider_name}/{self.model} (fallback)"
        resp.error = reason
        resp.latency_ms = (time.time()-t0)*1000
        return resp

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        """Direct chat completion with custom system prompt."""
        t0 = time.time()
        if not self.base_url or not self.api_key:
            return None, "Configura API key y base URL para usar el asistente."
        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
            data = json.dumps({
                "model": self.model,
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.7,
            }).encode()
            req = urllib.request.Request(url, data=data, headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }, method="POST")
            timeout_val = timeout or self.timeout
            resp = urllib.request.urlopen(req, timeout=timeout_val)
            body = json.loads(resp.read())
            text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            return text, None
        except Exception as e:
            return None, str(e)

def get_provider() -> AIProvider:
    provider_type = os.environ.get("NARRATIVE_AI_PROVIDER", "")
    if provider_type == "openai_compatible":
        return OpenAICompatibleProvider()
    from packages.infrastructure.ai_provider import SimulatedAIProvider
    return SimulatedAIProvider()
