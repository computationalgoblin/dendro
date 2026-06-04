"""AIController — wraps OrchestratorService for Desktop UI."""
from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

from packages.application.candidate_service import CandidateService
from packages.application.orchestrator_service import OrchestratorService
from packages.application.source_service import SourceService
from packages.domain.ai_models import AIMode


def _safe_base_url(value: str) -> str:
    if not value:
        return ""
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return value.replace(os.environ.get("NARRATIVE_AI_API_KEY", "__never__"), "***")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


class AIController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("AIController requires project_service")
        self.ps = project_service
        self.cs = CandidateService(project_service=self.ps)
        self.ss = SourceService(project_service=self.ps)
        provider_name = os.environ.get("NARRATIVE_AI_PROVIDER", "simulated") or "simulated"
        self.orchestrator = OrchestratorService(
            project_service=self.ps,
            candidate_service=self.cs,
            source_service=self.ss,
            provider_name=provider_name,
        )

    def provider_status(self) -> dict[str, str | bool]:
        provider = os.environ.get("NARRATIVE_AI_PROVIDER", "") or "simulated"
        model = os.environ.get("NARRATIVE_AI_MODEL", "") or "?"
        base_url = _safe_base_url(os.environ.get("NARRATIVE_AI_BASE_URL", ""))
        has_key = bool(os.environ.get("NARRATIVE_AI_API_KEY"))
        fallback = False
        reason = ""
        if provider == "openai_compatible":
            missing = []
            if not base_url:
                missing.append("BASE_URL")
            if not has_key:
                missing.append("API_KEY")
            if missing:
                fallback = True
                reason = "missing " + ",".join(missing)
        elif provider == "simulated":
            fallback = False
        else:
            fallback = True
            reason = f"unknown provider {provider}"
        return {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "fallback": fallback,
            "fallback_reason": reason,
            "has_key": has_key,
        }

    def provider_info(self):
        status = self.provider_status()
        provider = status["provider"]
        model = status["model"]
        base_url = status["base_url"] or "—"
        fallback = "yes" if status["fallback"] else "no"
        reason = status["fallback_reason"] or "—"
        if provider == "openai_compatible":
            return (
                f"provider=openai_compatible model={model} base={base_url} "
                f"fallback={fallback} reason={reason}"
            )
        return f"provider={provider} model={model} base={base_url} fallback={fallback} reason={reason}"

    def test_provider(self):
        return self.orchestrator.invoke(AIMode.GENERATE_ENTITY, prompt_hint="desktop ui provider test")

    def chat(self, system_prompt: str, user_message: str):
        """Send a chat message with custom system prompt. Returns (text, error_string)."""
        provider = self.orchestrator._provider
        timeout = int(os.environ.get("NARRATIVE_AI_TIMEOUT", "300"))
        return provider.chat(system_prompt, user_message, timeout=timeout)

    def generate_entity_candidates(self, prompt_hint):
        return self.orchestrator.generate_candidates(AIMode.GENERATE_ENTITY, prompt_hint=prompt_hint)

    def rewrite_entity(self, entity_id, prompt_hint=""):
        return self.orchestrator.generate_candidates(AIMode.REWRITE_DESCRIPTION, entity_id=entity_id, prompt_hint=prompt_hint)
