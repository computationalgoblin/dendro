"""AI-backed command-bar planner for E02.

The planner is intentionally an application-layer service: it asks the active
provider to interpret the user's free-form command and returns a constrained
plan. It never generates final narrative content and never mutates canon.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import json
import re

from packages.application.context_sanitizer import sanitize_nested
from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import AIProvider


ALLOWED_INTENT_TYPES: frozenset[str] = frozenset({
    "generate_entities",
    "generate_tree",
    "suggest_relations",
    "analyze_coherence",
    "expand_worldbuilding",
    "explain_from_causes",
    "review_graph",
    "freeform_planning",
    "edit_entities",
    "propose_milestones",
    "unknown",
})

ALLOWED_ACTION_TYPES: frozenset[str] = frozenset({
    "answer_question",
    "suggest_hojas",
    "suggest_ramas",
    "suggest_relations",
    "suggest_milestones",
    "analyze_coherence",
    "review_graph",
    "edit_selection",
    "expand_worldbuilding",
    "ask_clarification",
})

STRUCTURAL_ACTION_TYPES: frozenset[str] = frozenset({
    "suggest_hojas",
    "suggest_ramas",
    "suggest_relations",
    "suggest_milestones",
    "edit_selection",
    "expand_worldbuilding",
})

FORBIDDEN_DIRECT_ACTIONS: frozenset[str] = frozenset({
    "create_entity",
    "update_entity",
    "delete_entity",
    "create_relation",
    "update_relation",
    "delete_relation",
    "save_project",
    "canonize",
    "persist",
})

DEFAULT_EXPECTED_OUTPUT_BY_INTENT: dict[str, str] = {
    "generate_entities": "entity_candidates",
    "generate_tree": "tree_candidates",
    "suggest_relations": "relation_candidates",
    "analyze_coherence": "analysis_report",
    "expand_worldbuilding": "worldbuilding_candidates",
    "explain_from_causes": "explanation_report",
    "review_graph": "analysis_report",
    "freeform_planning": "plan_report",
    "edit_entities": "edit_candidates",
    "propose_milestones": "milestone_candidates",
    "unknown": "clarification_or_plan",
}

COMMAND_BAR_PLANNER_SYSTEM_PROMPT_ES = """Eres el planner de la command bar de Dendro.

Tu tarea NO es generar contenido narrativo final. Tu tarea es interpretar el
prompt del usuario y devolver SOLO JSON valido con un plan de acciones
revisables.

Reglas obligatorias:
- Nunca propongas modificar canon directamente.
- Las acciones estructurales deben producir candidatos, previews, informes o
  preguntas de aclaracion.
- Si la peticion es ambigua, usa intent_type "unknown", action
  "ask_clarification" y clarifying_question.
- No inventes IDs. Usa "selection", "visible_graph" o IDs ya presentes en el
  contexto.
- El prompt del usuario manda sobre palabras clave sueltas.

JSON esperado:
{
  "intent_type": "generate_entities | generate_tree | suggest_relations | analyze_coherence | expand_worldbuilding | explain_from_causes | review_graph | freeform_planning | edit_entities | propose_milestones | unknown",
  "confidence": 0.0,
  "target_scope": "selection | focused_view | visible_graph | project_summary | named_entities",
  "expected_output_type": "entity_candidates | tree_candidates | relation_candidates | analysis_report | worldbuilding_candidates | explanation_report | plan_report | edit_candidates | milestone_candidates | clarification_or_plan",
  "needs_confirmation": true,
  "rationale": "breve explicacion",
  "actions": [
    {
      "type": "answer_question | suggest_hojas | suggest_ramas | suggest_relations | suggest_milestones | analyze_coherence | review_graph | edit_selection | expand_worldbuilding | ask_clarification",
      "output_type": "report | entity_candidates | tree_candidates | relation_candidates | milestone_candidates | edit_candidates | open_question",
      "target_refs": ["selection"],
      "rationale": "por que esta accion es necesaria",
      "parameters": {}
    }
  ],
  "retrieval_needs": ["selection", "relations", "chronology", "milestones", "issues", "creative_config"],
  "clarifying_question": null
}
"""


@dataclass(frozen=True)
class CommandBarPlanAction:
    type: str
    output_type: str
    target_refs: list[str] = field(default_factory=list)
    rationale: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "output_type": self.output_type,
            "target_refs": list(self.target_refs),
            "rationale": self.rationale,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class CommandBarPlan:
    intent_type: str
    confidence: float
    target_scope: str
    expected_output_type: str
    needs_confirmation: bool
    rationale: str
    actions: list[CommandBarPlanAction] = field(default_factory=list)
    retrieval_needs: list[str] = field(default_factory=list)
    clarifying_question: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_type": self.intent_type,
            "confidence": self.confidence,
            "target_scope": self.target_scope,
            "expected_output_type": self.expected_output_type,
            "needs_confirmation": self.needs_confirmation,
            "rationale": self.rationale,
            "actions": [action.to_dict() for action in self.actions],
            "retrieval_needs": list(self.retrieval_needs),
            "clarifying_question": self.clarifying_question,
        }


def build_planner_user_message(prompt: str, context: dict[str, Any] | None = None) -> str:
    safe_context = sanitize_nested(dict(context or {}))
    return json.dumps(
        {
            "prompt_exacto_usuario": (prompt or "").strip(),
            "contexto_autorizado": safe_context,
            "allowed_intent_types": sorted(ALLOWED_INTENT_TYPES),
            "allowed_action_types": sorted(ALLOWED_ACTION_TYPES),
            "canon_policy": {
                "no_canon_automatico": True,
                "solo_candidatos_o_informes": True,
                "no_ids_inventados": True,
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def parse_command_bar_plan(text: str | None) -> Result:
    payload = _extract_json_object(text or "")
    if isinstance(payload, Error):
        return payload
    return _normalize_plan_payload(payload.value)


class CommandBarPlannerService:
    """Provider-backed planner for command-bar prompts."""

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def plan(self, prompt: str, context: dict[str, Any] | None = None, *, timeout_seconds: int = 300) -> Result:
        prompt = (prompt or "").strip()
        if not prompt:
            return Error("El prompt no puede estar vacio")
        try:
            text, error = self.provider.chat(
                COMMAND_BAR_PLANNER_SYSTEM_PROMPT_ES,
                build_planner_user_message(prompt, context),
                timeout=timeout_seconds,
            )
        except Exception as exc:
            return Error(str(exc))
        if error:
            return Error(str(error))
        parsed = parse_command_bar_plan(text)
        if isinstance(parsed, Error):
            return parsed
        return parsed


def _extract_json_object(text: str) -> Result:
    raw = (text or "").strip()
    if not raw:
        return Error("El planner IA no devolvio contenido")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return Error("El planner IA no devolvio JSON valido")
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return Error("El planner IA no devolvio JSON valido")
    if not isinstance(parsed, dict):
        return Error("El planner IA debe devolver un objeto JSON")
    return Ok(parsed)


def _normalize_plan_payload(payload: dict[str, Any]) -> Result:
    intent_type = _clean_choice(payload.get("intent_type") or payload.get("intent"), ALLOWED_INTENT_TYPES, "unknown")
    confidence = _coerce_confidence(payload.get("confidence"))
    target_scope = _clean_scope(payload.get("target_scope") or payload.get("scope"))
    expected = str(payload.get("expected_output_type") or DEFAULT_EXPECTED_OUTPUT_BY_INTENT.get(intent_type, "plan_report")).strip()
    rationale = str(payload.get("rationale") or "").strip()
    retrieval_needs = _string_list(payload.get("retrieval_needs") or payload.get("needs_retrieval"))
    clarifying_question = _optional_string(payload.get("clarifying_question"))

    actions_result = _normalize_actions(payload.get("actions"))
    if isinstance(actions_result, Error):
        return actions_result
    actions = actions_result.value
    if not actions:
        actions = _default_actions_for_intent(intent_type, expected)
    if intent_type == "unknown" and not clarifying_question:
        clarifying_question = "Puedes concretar que quieres que haga Dendro con esta peticion?"

    has_structural_action = any(action.type in STRUCTURAL_ACTION_TYPES for action in actions)
    needs_confirmation = bool(payload.get("needs_confirmation", False) or has_structural_action)

    plan = CommandBarPlan(
        intent_type=intent_type,
        confidence=confidence,
        target_scope=target_scope,
        expected_output_type=expected,
        needs_confirmation=needs_confirmation,
        rationale=rationale,
        actions=actions,
        retrieval_needs=retrieval_needs,
        clarifying_question=clarifying_question,
        raw=dict(payload),
    )
    return Ok(plan)


def _normalize_actions(value: Any) -> Result:
    raw_actions = value if isinstance(value, list) else []
    actions: list[CommandBarPlanAction] = []
    for raw in raw_actions:
        if isinstance(raw, str):
            raw = {"type": raw}
        if not isinstance(raw, dict):
            continue
        action_type = str(raw.get("type") or "").strip()
        if action_type in FORBIDDEN_DIRECT_ACTIONS:
            return Error(f"El planner IA propuso una accion directa no permitida: {action_type}")
        if action_type not in ALLOWED_ACTION_TYPES:
            continue
        output_type = str(raw.get("output_type") or _default_output_for_action(action_type)).strip()
        actions.append(CommandBarPlanAction(
            type=action_type,
            output_type=output_type,
            target_refs=_string_list(raw.get("target_refs")),
            rationale=str(raw.get("rationale") or "").strip(),
            parameters=dict(raw.get("parameters") or {}) if isinstance(raw.get("parameters"), dict) else {},
        ))
    return Ok(actions)


def _default_actions_for_intent(intent_type: str, expected_output_type: str) -> list[CommandBarPlanAction]:
    mapping = {
        "generate_entities": "suggest_hojas",
        "generate_tree": "suggest_ramas",
        "suggest_relations": "suggest_relations",
        "analyze_coherence": "analyze_coherence",
        "expand_worldbuilding": "expand_worldbuilding",
        "explain_from_causes": "answer_question",
        "review_graph": "review_graph",
        "freeform_planning": "answer_question",
        "edit_entities": "edit_selection",
        "propose_milestones": "suggest_milestones",
        "unknown": "ask_clarification",
    }
    action_type = mapping.get(intent_type, "answer_question")
    return [CommandBarPlanAction(
        type=action_type,
        output_type=expected_output_type or _default_output_for_action(action_type),
        target_refs=["selection" if intent_type in {"edit_entities", "suggest_relations", "propose_milestones"} else "visible_graph"],
        rationale="Accion derivada de la intencion principal.",
    )]


def _default_output_for_action(action_type: str) -> str:
    return {
        "answer_question": "report",
        "suggest_hojas": "entity_candidates",
        "suggest_ramas": "tree_candidates",
        "suggest_relations": "relation_candidates",
        "suggest_milestones": "milestone_candidates",
        "analyze_coherence": "analysis_report",
        "review_graph": "analysis_report",
        "edit_selection": "edit_candidates",
        "expand_worldbuilding": "worldbuilding_candidates",
        "ask_clarification": "open_question",
    }.get(action_type, "report")


def _clean_choice(value: Any, allowed: frozenset[str], fallback: str) -> str:
    candidate = str(value or "").strip()
    return candidate if candidate in allowed else fallback


def _clean_scope(value: Any) -> str:
    scope = str(value or "").strip()
    allowed = {"selection", "focused_view", "visible_graph", "project_summary", "named_entities"}
    return scope if scope in allowed else "visible_graph"


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
