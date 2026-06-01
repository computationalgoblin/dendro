"""AIController — wraps OrchestratorService for Desktop UI."""
from __future__ import annotations

import os

from packages.application.candidate_service import CandidateService
from packages.application.orchestrator_service import OrchestratorService
from packages.application.source_service import SourceService
from packages.domain.ai_models import AIMode


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

    def provider_info(self):
        provider = os.environ.get("NARRATIVE_AI_PROVIDER", "")
        model = os.environ.get("NARRATIVE_AI_MODEL", "")
        if provider == "openai_compatible":
            if os.environ.get("NARRATIVE_AI_API_KEY"):
                return f"openai_compatible/{model or '?'}"
            return "openai_compatible (missing KEY)"
        return "simulated"

    def test_provider(self):
        return self.orchestrator.invoke(AIMode.GENERATE_ENTITY, prompt_hint="desktop ui provider test")

    def generate_entity_candidates(self, prompt_hint):
        return self.orchestrator.generate_candidates(AIMode.GENERATE_ENTITY, prompt_hint=prompt_hint)

    def rewrite_entity(self, entity_id, prompt_hint=""):
        return self.orchestrator.generate_candidates(AIMode.REWRITE_DESCRIPTION, entity_id=entity_id, prompt_hint=prompt_hint)
