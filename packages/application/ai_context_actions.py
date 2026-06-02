"""Contextual AI actions for B31-T08.

All actions build context with NarrativeContextBuilder and produce reviewable
candidates/previews. They never mutate canon directly.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from packages.application.narrative_context_builder import NarrativeContextBuilder
from packages.domain.ai_models import AIMode, AIOperation, AuthorizedContext
from packages.domain.candidate_issue import Candidate, CandidateType
from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import AIProvider, create_provider


_NODE_ACTIONS: dict[str, AIMode] = {
    "generate_text": AIMode.EXPAND_ENTITY,
    "improve_text": AIMode.REWRITE_DESCRIPTION,
    "suggest_relations": AIMode.SUGGEST_RELATIONS,
    "suggest_conflict": AIMode.CRITICAL_ANALYSIS,
    "suggest_secrets": AIMode.CONTINUITY_QUESTION,
    "suggest_clues": AIMode.CONTINUITY_QUESTION,
    "detect_contradictions": AIMode.CONSISTENCY_ANALYSIS,
    "summarize": AIMode.SUMMARIZE,
    "create_candidate": AIMode.GENERATE_ENTITY,
}
_RELATION_ACTIONS: dict[str, AIMode] = {
    "deepen": AIMode.EXPAND_ENTITY,
    "suggest_evolution": AIMode.CONTINUITY_QUESTION,
    "suggest_scene": AIMode.GENERATE_ENTITY,
    "detect_contradiction": AIMode.CONSISTENCY_ANALYSIS,
    "suggest_secret_clue": AIMode.CONTINUITY_QUESTION,
    "create_candidate": AIMode.GENERATE_RELATION,
}
_GRAPH_ACTIONS: dict[str, AIMode] = {
    "suggest_missing_nodes": AIMode.GENERATE_ENTITY,
    "suggest_missing_relations": AIMode.SUGGEST_RELATIONS,
    "detect_isolated_zones": AIMode.CRITICAL_ANALYSIS,
    "detect_inconsistencies": AIMode.CONSISTENCY_ANALYSIS,
    "suggest_emergent_plots": AIMode.CONTINUITY_QUESTION,
}
_PREVIEW_ACTIONS = {"summarize", "detect_contradictions", "detect_contradiction", "detect_isolated_zones", "detect_inconsistencies"}


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _context_hash(context: dict[str, Any]) -> str:
    return hashlib.sha256(_json_dumps(context).encode("utf-8")).hexdigest()[:16]


def _candidate_type_for(action_type: str, payload: dict[str, Any], fallback: CandidateType = CandidateType.SUGERENCIA_IA) -> str:
    if "relation_type" in payload or {"source_id", "target_id"}.issubset(payload.keys()) or "relations" in action_type:
        return CandidateType.RELACION.value
    if "name" in payload or "entity_type" in payload or "nodes" in action_type:
        return CandidateType.ENTIDAD.value
    if "contrad" in action_type or "detect" in action_type:
        return CandidateType.INCIDENCIA.value
    if "text" in action_type or "description" in payload or "summar" in action_type:
        return CandidateType.CAMBIO.value
    return fallback.value


def _compact_context_summary(context: dict[str, Any]) -> dict[str, Any]:
    project = context.get("project") or {}
    target = context.get("target") or {}
    neighborhood = context.get("neighborhood") or {}
    knowledge = context.get("knowledge") or {}
    return {
        "schema": context.get("schema"),
        "target_type": context.get("target_type"),
        "target_id": context.get("target_id"),
        "audience": context.get("audience"),
        "project_name": project.get("name"),
        "target_name": target.get("name") or target.get("id"),
        "neighbor_relation_count": len(neighborhood.get("relations") or []),
        "neighbor_entity_count": len(neighborhood.get("entities") or []),
        "visible_secret_count": len(knowledge.get("secrets") or []),
        "visible_clue_count": len(knowledge.get("clues") or []),
    }


def _authorized_context(context: dict[str, Any]) -> AuthorizedContext:
    project = context.get("project") or {}
    target_type = context.get("target_type")
    target_id = context.get("target_id")
    selected_entities = [target_id] if target_type == "entity" and target_id else []
    selected_relations = [target_id] if target_type == "relation" and target_id else []
    neighborhood = context.get("neighborhood") or {}
    entities = []
    target = context.get("target")
    if isinstance(target, dict) and target.get("id") and target_type == "entity":
        entities.append(target)
    entities.extend(neighborhood.get("entities") or [])
    relations = []
    if isinstance(target, dict) and target.get("id") and target_type == "relation":
        relations.append(target)
    relations.extend(neighborhood.get("relations") or [])
    return AuthorizedContext(
        project_name=project.get("name", ""),
        selected_entity_ids=selected_entities,
        selected_relation_ids=selected_relations,
        audience=context.get("audience", "gm"),
        project_config_snapshot={
            "tone": project.get("tone", {}),
            "genre": project.get("genre", {}),
            "realism": project.get("realism", {}),
            "constraints": context.get("constraints", {}),
            "context_hash": _context_hash(context),
        },
        context_entities=entities,
        context_relations=relations,
        context_history=context.get("history") or [],
        context_issues=context.get("issues") or [],
    )


@dataclass
class AIContextActionResult:
    action_type: str
    target_type: str
    target_id: str | None
    context_hash: str
    raw_text: str
    candidates: list[Candidate]
    previews: list[dict[str, Any]]
    observations: list[str]
    provider: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "context_hash": self.context_hash,
            "raw_text": self.raw_text,
            "candidate_ids": [c.id for c in self.candidates],
            "previews": list(self.previews),
            "observations": list(self.observations),
            "provider": self.provider,
        }


class AIContextActionService:
    """Runs contextual AI actions and records reviewable candidates."""

    def __init__(
        self,
        project_service: Any,
        candidate_service: Any,
        provider: AIProvider | None = None,
        provider_name: str = "simulated",
    ):
        self.project_service = project_service
        self.candidate_service = candidate_service
        self.context_builder = NarrativeContextBuilder(project_service)
        self.provider = provider or create_provider(provider_name)

    def run_node_action(self, entity_id: str, action_type: str, *, prompt_hint: str = "", audience: str = "gm") -> Result[AIContextActionResult, str]:
        mode = _NODE_ACTIONS.get(action_type)
        if mode is None:
            return Error(f"Unknown node AI action: {action_type}")
        context = self.context_builder.build_for_entity(entity_id, audience=audience)
        return self._run("node", entity_id, action_type, mode, context, prompt_hint)

    def run_relation_action(self, relation_id: str, action_type: str, *, prompt_hint: str = "", audience: str = "gm") -> Result[AIContextActionResult, str]:
        mode = _RELATION_ACTIONS.get(action_type)
        if mode is None:
            return Error(f"Unknown relation AI action: {action_type}")
        context = self.context_builder.build_for_relation(relation_id, audience=audience)
        return self._run("relation", relation_id, action_type, mode, context, prompt_hint)

    def run_graph_action(
        self,
        action_type: str,
        *,
        entity_ids: list[str] | None = None,
        relation_ids: list[str] | None = None,
        prompt_hint: str = "",
        audience: str = "gm",
    ) -> Result[AIContextActionResult, str]:
        mode = _GRAPH_ACTIONS.get(action_type)
        if mode is None:
            return Error(f"Unknown graph AI action: {action_type}")
        context = self.context_builder.build_for_graph_selection(entity_ids=entity_ids or [], relation_ids=relation_ids or [], audience=audience)
        return self._run("graph", None, action_type, mode, context, prompt_hint)

    def _run(
        self,
        target_type: str,
        target_id: str | None,
        action_type: str,
        mode: AIMode,
        context: dict[str, Any],
        prompt_hint: str,
    ) -> Result[AIContextActionResult, str]:
        if context.get("target") == {"redacted": True, "reason": "not_visible_for_audience"}:
            return Error("Target not visible for requested audience")
        context_hash = _context_hash(context)
        operation = AIOperation(
            mode=mode,
            context=_authorized_context(context),
            prompt_hint=self._prompt(action_type, prompt_hint, context),
            entity_id=target_id if target_type == "node" else None,
            entity_ids=[target_id] if target_type == "node" and target_id else [],
            max_candidates=3,
        )
        try:
            response = self.provider.invoke(operation)
        except Exception as exc:
            return Error(f"Provider error: {exc}")
        if response.error:
            return Error(response.error)

        candidates: list[Candidate] = []
        previews: list[dict[str, Any]] = []
        for index, payload in enumerate(response.candidates or []):
            payload = dict(payload)
            payload.setdefault("canonical_status", "candidate_non_canon")
            payload.setdefault("facts_status", "proposal_only_not_confirmed")
            if action_type in _PREVIEW_ACTIONS:
                previews.append(self._preview_payload(action_type, target_type, target_id, payload, response.raw_text, context_hash))
                continue
            created = self._create_candidate(
                action_type=action_type,
                target_type=target_type,
                target_id=target_id,
                context=context,
                context_hash=context_hash,
                payload=payload,
                raw_text=response.raw_text,
                provider=response.provider,
                index=index,
            )
            if isinstance(created, Error):
                return Error(created.error)
            candidates.append(created.value)

        if not candidates and not previews and (response.raw_text or response.observations):
            previews.append(self._preview_payload(action_type, target_type, target_id, {}, response.raw_text, context_hash))

        return Ok(AIContextActionResult(
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            context_hash=context_hash,
            raw_text=response.raw_text,
            candidates=candidates,
            previews=previews,
            observations=list(response.observations or []),
            provider=response.provider,
        ))

    def _create_candidate(
        self,
        *,
        action_type: str,
        target_type: str,
        target_id: str | None,
        context: dict[str, Any],
        context_hash: str,
        payload: dict[str, Any],
        raw_text: str,
        provider: str,
        index: int,
    ) -> Result[Candidate, str]:
        title = payload.get("name") or payload.get("title") or f"IA {action_type} #{index + 1}"
        metadata = {
            "origin": "AIContextActionService",
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "context_hash": context_hash,
            "context_summary": _compact_context_summary(context),
            "provider": provider,
            "raw_text_preview": raw_text[:500],
            "canonical_status": "candidate_non_canon",
        }
        data = {
            "title": title,
            "candidate_type": _candidate_type_for(action_type, payload),
            "proposed_data": payload,
            "affected_entity_ids": [target_id] if target_type == "node" and target_id else [],
            "affected_relation_ids": [target_id] if target_type == "relation" and target_id else [],
            "source": "ia",
            "source_id": None,
            "confidence": float(payload.get("confidence", 0.5) or 0.5),
            "justification": payload.get("justification") or raw_text[:500],
            "expected_impact": payload.get("expected_impact", "Sugerencia revisable; no canon hasta aceptación explícita."),
            "possible_contradictions": payload.get("possible_contradictions", []),
            "metadata": metadata,
        }
        return self.candidate_service.create_candidate(data)

    def _preview_payload(self, action_type: str, target_type: str, target_id: str | None, payload: dict[str, Any], raw_text: str, context_hash: str) -> dict[str, Any]:
        return {
            "action_type": action_type,
            "target_type": target_type,
            "target_id": target_id,
            "context_hash": context_hash,
            "raw_text": raw_text,
            "payload": payload,
            "canonical_status": "preview_non_canon",
        }

    def _prompt(self, action_type: str, prompt_hint: str, context: dict[str, Any]) -> str:
        return (
            "Acción IA contextual: " + action_type + "\n"
            "Restricciones: no modificar canon; producir candidatos/previews revisables; "
            "no tratar candidatos no canonizados como hechos.\n"
            f"Context hash: {_context_hash(context)}\n"
            f"Resumen: {_json_dumps(_compact_context_summary(context))}\n"
            f"Instrucción adicional: {prompt_hint or '—'}"
        )


__all__ = ["AIContextActionResult", "AIContextActionService"]
