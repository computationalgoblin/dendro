"""AIContextController — Desktop adapter for contextual B31-T08 actions."""
from __future__ import annotations

import os

from packages.application.ai_context_actions import AIContextActionService
from packages.application.candidate_service import CandidateService
from packages.domain.result import Error
from hosts.DesktopHostPySide.app_trace import _apptrace


class AIContextController:
    """Thin UI controller: delegates all AI/candidate logic to application service."""

    def __init__(self, project_service, ai_job_service=None):
        if project_service is None:
            raise ValueError("AIContextController requires project_service")
        self.ps = project_service
        self.candidate_service = CandidateService(project_service=self.ps)
        provider_name = os.environ.get("NARRATIVE_AI_PROVIDER", "simulated") or "simulated"
        # Share the host's command-bar AIJobService when given, so contextual
        # jobs are tracked in the same registry / jobs tray.
        self.service = AIContextActionService(
            project_service=self.ps,
            candidate_service=self.candidate_service,
            provider_name=provider_name,
            ai_job_service=ai_job_service,
        )

    def node_action(self, entity_id: str, action_type: str, prompt_hint: str = ""):
        _apptrace(f"CTRL AIContextController.node_action entity_id={entity_id!r} action={action_type!r}"[:120])
        return self.service.run_node_action(entity_id, action_type, prompt_hint=prompt_hint, audience="gm")

    def node_text_suggestion(self, entity_id: str, prompt_hint: str = "", language: str = "es"):
        """Text-only entity improvement for inline UI suggestions.

        This deliberately bypasses candidate creation: no graph nodes, no
        relations, no canon mutation.
        """
        _apptrace(f"CTRL AIContextController.node_text_suggestion entity_id={entity_id!r}"[:120])
        return self.service.run_node_text_suggestion(
            entity_id,
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def chat(self, system_prompt: str, user_message: str):
        """Direct chat with the underlying AI provider. Returns (text, error_string)."""
        _apptrace(f"CTRL AIContextController.chat prompt_len={len(system_prompt)} msg_len={len(user_message)}"[:120])
        provider = getattr(self.service, "provider", None)
        if provider is None or not hasattr(provider, "chat"):
            return None, "Proveedor IA no disponible para chat directo."
        timeout = int(os.environ.get("NARRATIVE_AI_TIMEOUT", "300"))
        return provider.chat(system_prompt, user_message, timeout=timeout)

    def relation_action(self, relation_id: str, action_type: str, prompt_hint: str = ""):
        _apptrace(f"CTRL AIContextController.relation_action relation_id={relation_id!r} action={action_type!r}"[:120])
        return self.service.run_relation_action(relation_id, action_type, prompt_hint=prompt_hint, audience="gm")

    def relation_text_suggestion(self, relation_id: str, prompt_hint: str = "", language: str = "es"):
        """Text-only relation improvement for inline UI suggestions."""
        _apptrace(f"CTRL AIContextController.relation_text_suggestion relation_id={relation_id!r}"[:120])
        return self.service.run_relation_text_suggestion(
            relation_id,
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def graph_action(self, action_type: str, entity_ids=None, relation_ids=None, prompt_hint: str = "", language: str = "es"):
        _apptrace(f"CTRL AIContextController.graph_action action={action_type!r} n_entities={len(entity_ids or [])} n_relations={len(relation_ids or [])}"[:120])
        return self.service.run_graph_action(
            action_type,
            entity_ids=list(entity_ids or []),
            relation_ids=list(relation_ids or []),
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def analyze_coherence(self, entity_ids=None, relation_ids=None, prompt_hint: str = "", language: str = "es"):
        _apptrace(f"CTRL AIContextController.analyze_coherence n_entities={len(entity_ids or [])} n_relations={len(relation_ids or [])}"[:120])
        return self.service.run_selection_coherence_analysis(
            entity_ids=list(entity_ids or []),
            relation_ids=list(relation_ids or []),
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def repair_coherence(self, entity_ids=None, relation_ids=None, proposal: str = "", prompt_hint: str = "", language: str = "es"):
        _apptrace(f"CTRL AIContextController.repair_coherence n_entities={len(entity_ids or [])} n_relations={len(relation_ids or [])}"[:120])
        return self.service.run_selection_coherence_repair(
            entity_ids=list(entity_ids or []),
            relation_ids=list(relation_ids or []),
            proposal=proposal,
            prompt_hint=prompt_hint,
            audience="gm",
            language=language,
        )

    def result_summary(self, result) -> str:
        _apptrace(f"CTRL AIContextController.result_summary"[:120])
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
