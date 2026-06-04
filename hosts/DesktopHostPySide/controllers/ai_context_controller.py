"""AIContextController — Desktop adapter for contextual B31-T08 actions."""
from __future__ import annotations

import os

from packages.application.ai_context_actions import AIContextActionService
from packages.application.candidate_service import CandidateService
from packages.domain.result import Error


class AIContextController:
    """Thin UI controller: delegates all AI/candidate logic to application service."""

    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("AIContextController requires project_service")
        self.ps = project_service
        self.candidate_service = CandidateService(project_service=self.ps)
        provider_name = os.environ.get("NARRATIVE_AI_PROVIDER", "simulated") or "simulated"
        self.service = AIContextActionService(
            project_service=self.ps,
            candidate_service=self.candidate_service,
            provider_name=provider_name,
        )

    def node_action(self, entity_id: str, action_type: str, prompt_hint: str = ""):
        return self.service.run_node_action(entity_id, action_type, prompt_hint=prompt_hint, audience="gm")

    def node_text_suggestion(self, entity_id: str, prompt_hint: str = "", language: str = "es"):
        """Text-only entity improvement for inline UI suggestions.

        This deliberately bypasses candidate creation: no graph nodes, no
        relations, no canon mutation.
        """
        return self.service.run_node_text_suggestion(
            entity_id,
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def chat(self, system_prompt: str, user_message: str):
        """Direct chat with the underlying AI provider. Returns (text, error_string)."""
        provider = getattr(self.service, "provider", None)
        if provider is None or not hasattr(provider, "chat"):
            return None, "Proveedor IA no disponible para chat directo."
        timeout = int(os.environ.get("NARRATIVE_AI_TIMEOUT", "300"))
        return provider.chat(system_prompt, user_message, timeout=timeout)

    def relation_action(self, relation_id: str, action_type: str, prompt_hint: str = ""):
        return self.service.run_relation_action(relation_id, action_type, prompt_hint=prompt_hint, audience="gm")

    def relation_text_suggestion(self, relation_id: str, prompt_hint: str = "", language: str = "es"):
        """Text-only relation improvement for inline UI suggestions."""
        return self.service.run_relation_text_suggestion(
            relation_id,
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def graph_action(self, action_type: str, entity_ids=None, relation_ids=None, prompt_hint: str = "", language: str = "es"):
        return self.service.run_graph_action(
            action_type,
            entity_ids=list(entity_ids or []),
            relation_ids=list(relation_ids or []),
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def analyze_coherence(self, entity_ids=None, relation_ids=None, prompt_hint: str = "", language: str = "es"):
        return self.service.run_selection_coherence_analysis(
            entity_ids=list(entity_ids or []),
            relation_ids=list(relation_ids or []),
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def repair_coherence(self, entity_ids=None, relation_ids=None, proposal: str = "", prompt_hint: str = "", language: str = "es"):
        return self.service.run_selection_coherence_repair(
            entity_ids=list(entity_ids or []),
            relation_ids=list(relation_ids or []),
            proposal=proposal,
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def result_summary(self, result) -> str:
        if isinstance(result, Error):
            return f"Error IA: {result.error}"
        value = result.value
        candidate_count = len(value.candidates)
        preview_count = len(value.previews)
        parts = []
        if candidate_count:
            ids = ", ".join(candidate.id[:8] for candidate in value.candidates)
            parts.append(f"{candidate_count} candidato(s): {ids}")
        if preview_count:
            parts.append(f"{preview_count} preview(s)")
        if value.observations:
            parts.append(f"{len(value.observations)} observación(es)")
        if not parts:
            parts.append("sin resultados revisables")
        return "IA contextual: " + "; ".join(parts)
