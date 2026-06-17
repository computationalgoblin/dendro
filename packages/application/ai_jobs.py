"""B39 AI command-bar jobs.

AI jobs are the command-bar unit of work. They never mutate canon directly:
results are staged as reviewable candidates, reports, suggestions or open
questions. The command-bar pipeline is intentionally split into:

1. classify_intent(prompt, context)
2. build_job_plan(intent, prompt, context)
3. execute_job(plan) through a provider-backed job service
4. stage_results(result)

Production execution must use the exact user prompt as the primary instruction.
If no real provider is configured, command-bar jobs fail clearly instead of
returning fake success. Tests may inject explicit mock providers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
import json
import re
import time
import uuid

from packages.domain.result import Error, Ok, Result
from packages.application.ai_observability import AIJobRecord, AIObservabilityLog
from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest, ModelParams
from packages.infrastructure.ai_provider import AIProvider, SimulatedAIProvider, create_provider


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _opt_float(value: Any) -> float | None:
    """Coerce a context value to float, or None when absent/invalid."""
    return float(value) if isinstance(value, (int, float)) else None


def _opt_int(value: Any) -> int | None:
    """Coerce a context value to int, or None when absent/invalid."""
    return int(value) if isinstance(value, (int, float)) else None


from packages.application.prompt_registry import get_prompt
from packages.application.command_prompts import system_prompt_for_intent

# Legacy constant — now sourced from Prompt Registry (B43-T01)
COMMAND_BAR_SYSTEM_PROMPT_ES = get_prompt("command_bar", lang="es") or ""
DEFAULT_AI_TIMEOUT_SECONDS = 300


class AIJobStatus(str, Enum):
    QUEUED = "queued"
    BUILDING_CONTEXT = "building_context"
    PLANNING = "planning"
    WAITING_FOR_MODEL = "waiting_for_model"
    RUNNING = "running"  # backward-compatible alias for older tests/UI
    POSTPROCESSING = "postprocessing"
    READY_FOR_REVIEW = "ready_for_review"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIJobType(str, Enum):
    GENERATE_ENTITIES = "generate_entities"
    GENERATE_TREE = "generate_tree"
    SUGGEST_RELATIONS = "suggest_relations"
    ANALYZE_COHERENCE = "analyze_coherence"
    EXPAND_WORLDBUILDING = "expand_worldbuilding"
    EXPLAIN_FROM_CAUSES = "explain_from_causes"
    REVIEW_GRAPH = "review_graph"
    FREEFORM_PLANNING = "freeform_planning"
    EDIT_ENTITIES = "edit_entities"
    PROPOSE_MILESTONES = "propose_milestones"
    # Deterministic command matrix (Acción × Ámbito) — new focused job types.
    CREATE_RING_TEMPLATE = "create_ring_template"
    EDIT_RELATION = "edit_relation"
    EDIT_RING = "edit_ring"
    EDIT_MILESTONE = "edit_milestone"
    # BETA1-AI02: text-only intents. Free text, no JSON staging — the suggestion
    # stays inline (e.g. the entity detail panel) until the user saves.
    IMPROVE_TEXT = "improve_text"
    GENERATE_TEXT = "generate_text"
    UNKNOWN = "unknown"


# BETA1-AI02: intents that return free text instead of staged candidates.
_TEXT_INTENTS: frozenset[AIJobType] = frozenset({AIJobType.IMPROVE_TEXT, AIJobType.GENERATE_TEXT})


def _is_text_intent(intent_type: Any) -> bool:
    try:
        key = intent_type if isinstance(intent_type, AIJobType) else AIJobType(str(intent_type))
    except ValueError:
        return False
    return key in _TEXT_INTENTS


def _text_result(text: str) -> dict[str, Any]:
    """Result shape for text-only intents: free text, no staged candidates."""
    cleaned = (text or "").strip()
    return {
        "summary": "Sugerencia de texto lista",
        "report": "",
        "text": cleaned,
        "candidates": [],
        "open_questions": [],
        "model_payload": {},
    }


# BETA1-AI02: single registry of "focused tasks" — the context-menu/panel
# action_type maps directly to an explicit AIJobType (no classification). This
# replaces the legacy `_NODE_ACTIONS`/`_GRAPH_ACTIONS` AIMode maps.
ACTION_TO_JOB_TYPE: dict[str, AIJobType] = {
    # Graph / selection menu
    "suggest_nodes": AIJobType.GENERATE_ENTITIES,
    "suggest_branches": AIJobType.GENERATE_TREE,
    "suggest_relations": AIJobType.SUGGEST_RELATIONS,
    "analyze_coherence": AIJobType.ANALYZE_COHERENCE,
    "suggest_missing_nodes": AIJobType.GENERATE_ENTITIES,
    "suggest_missing_relations": AIJobType.SUGGEST_RELATIONS,
    "detect_isolated_zones": AIJobType.ANALYZE_COHERENCE,
    "detect_inconsistencies": AIJobType.ANALYZE_COHERENCE,
    "suggest_emergent_plots": AIJobType.EXPAND_WORLDBUILDING,
    # Node / relation menu
    "create_candidate": AIJobType.GENERATE_ENTITIES,
    "expand_causal_down": AIJobType.EXPAND_WORLDBUILDING,
    "explain_from_causes": AIJobType.EXPLAIN_FROM_CAUSES,
    "suggest_conflict": AIJobType.ANALYZE_COHERENCE,
    "detect_contradictions": AIJobType.ANALYZE_COHERENCE,
    "detect_contradiction": AIJobType.ANALYZE_COHERENCE,
    "propose_milestones": AIJobType.PROPOSE_MILESTONES,
    # Text-only (detail panel / inline)
    "improve_text": AIJobType.IMPROVE_TEXT,
    "generate_text": AIJobType.GENERATE_TEXT,
    "deepen": AIJobType.IMPROVE_TEXT,
    "summarize": AIJobType.GENERATE_TEXT,
    "describe_tree": AIJobType.GENERATE_TEXT,
}


def job_type_for_action(action_type: str) -> AIJobType:
    """Resolve a context-menu/panel action_type to its focused AIJobType."""
    return ACTION_TO_JOB_TYPE.get(action_type, AIJobType.UNKNOWN)


# ---------------------------------------------------------------------------
# Deterministic command matrix (Acción × Ámbito)
#
# Replaces the fragile keyword classifier on the command bar: the user picks an
# action and a scope from two selectors and we resolve the AIJobType verbatim.
# Every command-bar job is now explicit-intent, exactly like a focused job.
# ---------------------------------------------------------------------------
class CommandAction(str, Enum):
    CREAR = "crear"
    EDITAR = "editar"
    ANALIZAR = "analizar"
    EXPLICAR = "explicar"
    EXPANDIR = "expandir"


class CommandScope(str, Enum):
    HOJA = "hoja"
    RAMA = "rama"
    RELACION = "relacion"
    ANILLO = "anillo"
    HITO = "hito"


# UI labels (Spanish), kept beside the enums so the host and tests share them.
ACTION_LABELS: dict[CommandAction, str] = {
    CommandAction.CREAR: "Crear",
    CommandAction.EDITAR: "Editar",
    CommandAction.ANALIZAR: "Analizar",
    CommandAction.EXPLICAR: "Explicar",
    CommandAction.EXPANDIR: "Expandir",
}

SCOPE_LABELS: dict[CommandScope, str] = {
    CommandScope.HOJA: "Hoja",
    CommandScope.RAMA: "Rama",
    CommandScope.RELACION: "Relación",
    CommandScope.ANILLO: "Anillo/Estrato",
    CommandScope.HITO: "Hito",
}

_ALL_SCOPES: tuple[CommandScope, ...] = tuple(CommandScope)

# Per-scope mappings for the generative/edit actions; the analytical trio
# (ANALIZAR/EXPLICAR/EXPANDIR) collapses to one job type for every scope.
COMMAND_MATRIX: dict[tuple[CommandAction, CommandScope], AIJobType] = {
    (CommandAction.CREAR, CommandScope.HOJA): AIJobType.GENERATE_ENTITIES,
    (CommandAction.CREAR, CommandScope.RAMA): AIJobType.GENERATE_TREE,
    (CommandAction.CREAR, CommandScope.RELACION): AIJobType.SUGGEST_RELATIONS,
    (CommandAction.CREAR, CommandScope.ANILLO): AIJobType.CREATE_RING_TEMPLATE,
    (CommandAction.CREAR, CommandScope.HITO): AIJobType.PROPOSE_MILESTONES,
    (CommandAction.EDITAR, CommandScope.HOJA): AIJobType.EDIT_ENTITIES,
    (CommandAction.EDITAR, CommandScope.RAMA): AIJobType.EDIT_ENTITIES,
    (CommandAction.EDITAR, CommandScope.RELACION): AIJobType.EDIT_RELATION,
    (CommandAction.EDITAR, CommandScope.ANILLO): AIJobType.EDIT_RING,
    (CommandAction.EDITAR, CommandScope.HITO): AIJobType.EDIT_MILESTONE,
}
# Analytical trio: same job type regardless of scope.
for _scope in _ALL_SCOPES:
    COMMAND_MATRIX[(CommandAction.ANALIZAR, _scope)] = AIJobType.ANALYZE_COHERENCE
    COMMAND_MATRIX[(CommandAction.EXPLICAR, _scope)] = AIJobType.EXPLAIN_FROM_CAUSES
    COMMAND_MATRIX[(CommandAction.EXPANDIR, _scope)] = AIJobType.EXPAND_WORLDBUILDING
del _scope


def _coerce_action(action: "CommandAction | str") -> CommandAction:
    return action if isinstance(action, CommandAction) else CommandAction(str(action))


def _coerce_scope(scope: "CommandScope | str") -> CommandScope:
    return scope if isinstance(scope, CommandScope) else CommandScope(str(scope))


def valid_scopes_for_action(action: "CommandAction | str") -> list[CommandScope]:
    """Scopes the second selector should offer for a given action.

    All five scopes are valid for every action today; kept as a function so the
    UI filters through one source of truth if combinations are restricted later.
    """
    act = _coerce_action(action)
    return [scope for scope in _ALL_SCOPES if (act, scope) in COMMAND_MATRIX]


def job_type_for_command(action: "CommandAction | str", scope: "CommandScope | str") -> AIJobType:
    """Resolve the two command-bar selectors to a deterministic AIJobType.

    Raises ValueError for an unmapped (action, scope) pair so the UI never
    silently runs the wrong job.
    """
    key = (_coerce_action(action), _coerce_scope(scope))
    try:
        return COMMAND_MATRIX[key]
    except KeyError as exc:
        raise ValueError(f"Combinación acción/ámbito no soportada: {key[0].value}/{key[1].value}") from exc


# BETA1-AI02: per-job generation params now live in the gateway's INTENT_PARAMS
# (keyed by AIJobType.value), so the command bar and the import track share a
# single source of truth. Resolve them via ModelParams.from_intent(job.type.value).


@dataclass
class CommandBarIntent:
    intent_type: AIJobType
    confidence: float
    target_scope: str
    expected_output_type: str
    needs_confirmation: bool = False
    rationale: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)
    retrieval_needs: list[str] = field(default_factory=list)
    clarifying_question: str | None = None
    planner_source: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "target_scope": self.target_scope,
            "expected_output_type": self.expected_output_type,
            "needs_confirmation": self.needs_confirmation,
            "rationale": self.rationale,
            "actions": list(self.actions),
            "retrieval_needs": list(self.retrieval_needs),
            "clarifying_question": self.clarifying_question,
            "planner_source": self.planner_source,
        }


@dataclass
class AIJobPlan:
    job_id: str
    intent: CommandBarIntent
    prompt: str
    context: dict[str, Any]
    title: str
    steps: list[str]
    target_scope: str
    expected_result: str
    creates: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "intent": self.intent.to_dict(),
            "prompt": self.prompt,
            "context": dict(self.context),
            "title": self.title,
            "steps": list(self.steps),
            "target_scope": self.target_scope,
            "expected_result": self.expected_result,
            "creates": list(self.creates),
        }


@dataclass
class AIJob:
    """Reviewable AI job created by the Creation command bar."""

    id: str = field(default_factory=lambda: f"job_{uuid.uuid4().hex[:10]}")
    type: AIJobType = AIJobType.REVIEW_GRAPH
    # BETA1-AI02: set for focused jobs (context menu / detail panel) so the
    # pipeline uses this intent verbatim instead of classifying the prompt.
    explicit_intent: AIJobType | None = None
    prompt: str = ""
    status: AIJobStatus = AIJobStatus.QUEUED
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    message: str = "En cola"
    progress: float = 0.0
    context_scope: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    cancellable: bool = True
    intent: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "explicit_intent": self.explicit_intent.value if self.explicit_intent else None,
            "prompt": self.prompt,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message": self.message,
            "progress": self.progress,
            "context_scope": dict(self.context_scope),
            "result": dict(self.result),
            "error": self.error,
            "cancellable": self.cancellable,
            "intent": dict(self.intent),
            "plan": dict(self.plan),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIJob":
        raw_explicit = data.get("explicit_intent")
        try:
            explicit_intent = AIJobType(raw_explicit) if raw_explicit else None
        except ValueError:
            explicit_intent = None
        return cls(
            id=data.get("id") or f"job_{uuid.uuid4().hex[:10]}",
            type=AIJobType(data.get("type") or AIJobType.REVIEW_GRAPH.value),
            explicit_intent=explicit_intent,
            prompt=data.get("prompt", ""),
            status=AIJobStatus(data.get("status") or AIJobStatus.QUEUED.value),
            created_at=data.get("created_at") or _now_iso(),
            updated_at=data.get("updated_at") or _now_iso(),
            message=data.get("message", ""),
            progress=float(data.get("progress", 0.0) or 0.0),
            context_scope=dict(data.get("context_scope") or {}),
            result=dict(data.get("result") or {}),
            error=data.get("error", ""),
            cancellable=bool(data.get("cancellable", True)),
            intent=dict(data.get("intent") or {}),
            plan=dict(data.get("plan") or {}),
        )


BRANCH_TYPES = {"faccion", "cultura", "sistema_magico", "religion", "institucion", "trama", "contenedor"}


def _norm(prompt: str) -> str:
    return (prompt or "").strip().lower()


def _has_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _scope_from_context(text: str, context: dict[str, Any]) -> str:
    selected = context.get("selected_entity_ids") or []
    focus = context.get("focus_label") or ""
    if selected:
        return "selection"
    if "devian" in text or "hermandad" in text:
        return "named_entities"
    if focus and str(focus).lower() != "global":
        return "focused_view"
    if "todo" in text or "grafo" in text or "proyecto" in text:
        return "project_summary"
    return "visible_graph"


def classify_intent(prompt: str, context: dict[str, Any] | None = None) -> CommandBarIntent:
    """DEPRECATED keyword classifier. The command bar now resolves intent from
    two deterministic selectors (see COMMAND_MATRIX / job_type_for_command); no
    UI surface calls this anymore. Retained only for the non-explicit create_job
    fallback and legacy tests, pending removal."""
    context = dict(context or {})
    text = _norm(prompt)
    worldbuilding = bool(context.get("worldbuilding_active", False))
    scope = _scope_from_context(text, context)

    if not text:
        return CommandBarIntent(AIJobType.UNKNOWN, 0.0, scope, "none", True, "Prompt vacío")

    # BUG 4 fix: detect edit/body fill intent before generation
    # Updated for B39: include hoja/rama terminology alongside legacy terms
    if _has_any(text, ["rellena", "rellenar", "completa", "completar", "cuerpo", "historia", "motivación", "motivaciones", "descripción", "desarrolla", "desarrollar", "expande", "expandir", "editar", "modifica", "modificar"]) and _has_any(text, ["entidad", "entidades", "existente", "existentes", "creada", "creadas", "nodo", "nodos", "personaje", "personajes", "hoja", "hojas", "rama", "ramas"]):
        return CommandBarIntent(AIJobType.EDIT_ENTITIES, 0.80, scope, "edit_candidates", False, "La petición pide editar/rellenar hojas o ramas existentes, no crear nuevas")

    # B39: detect "anillo" keyword for worldbuilding/causal strata
    if _has_any(text, ["anillo", "anillos", "estrato causal", "estratos causales", "capa metafísica"]):
        intent = AIJobType.EXPAND_WORLDBUILDING if worldbuilding else AIJobType.GENERATE_TREE
        return CommandBarIntent(intent, 0.80, scope, "worldbuilding_candidates", False, "La petición pide anillo/estrato causal/worldbuilding")

    # B41: detect milestone/hito intent — must come before relations/generation
    if _has_any(text, ["hito", "hitos", "cadena historica", "cadena histórica", "status quo", "acontecimiento", "origen para"]):
        return CommandBarIntent(AIJobType.PROPOSE_MILESTONES, 0.80, scope, "milestone_candidates", False, "La petición pide hitos causales/históricos")

    if _has_any(text, ["relacion", "relación", "relaciones", "vínculo", "vinculo"]):
        return CommandBarIntent(AIJobType.SUGGEST_RELATIONS, 0.82, scope, "relation_candidates", False, "La petición pide relaciones o vínculos")

    if _has_any(text, ["incoher", "coherencia", "contradic"]):
        return CommandBarIntent(AIJobType.ANALYZE_COHERENCE, 0.82, scope, "analysis_report", False, "La petición pide coherencia/contradicciones")

    if _has_any(text, ["revisa", "revisión", "revision", "mejoras", "analiza", "audita"]):
        return CommandBarIntent(AIJobType.REVIEW_GRAPH, 0.78, scope, "analysis_report", False, "La petición pide revisión o mejoras")

    if _has_any(text, ["explica", "justifica", "causas superiores", "desde causas"]):
        return CommandBarIntent(AIJobType.EXPLAIN_FROM_CAUSES, 0.75, scope, "explanation_report", False, "La petición pide explicación causal")

    if _has_any(text, ["metafís", "metafis", "worldbuilding", "capa", "causal", "agujero negro", "agujeros negros"]):
        intent = AIJobType.EXPAND_WORLDBUILDING if worldbuilding else AIJobType.GENERATE_TREE
        return CommandBarIntent(intent, 0.80, scope, "worldbuilding_candidates", False, "La petición pide sistema/worldbuilding")

    # B39: "rama" keyword and branch-type words → GENERATE_TREE (rama = tree internally)
    if _has_any(text, ["rama", "ramas", "facción", "faccion", "cultura", "religión", "religion", "institución", "institucion", "trama", "tramas", "organización", "organizacion", "país", "pais", "reino", "reinos", "sistema", "árbol", "arbol", "estructura"]):
        return CommandBarIntent(AIJobType.GENERATE_TREE, 0.72, scope, "tree_candidates", False, "La petición pide rama/sistema/árbol/estructura")

    # B39: "hoja" keyword → GENERATE_ENTITIES
    if _has_any(text, ["hoja", "hojas", "personaje", "personajes", "entidad", "entidades", "nodo", "nodos", "científico", "cientific", "herman"]):
        return CommandBarIntent(AIJobType.GENERATE_ENTITIES, 0.78, scope, "entity_candidates", False, "La petición pide hojas/personajes/entidades")

    if _has_any(text, ["plan", "idea", "organiza", "ayúdame", "ayudame"]):
        return CommandBarIntent(AIJobType.FREEFORM_PLANNING, 0.55, scope, "plan_report", False, "Petición abierta de planificación")

    return CommandBarIntent(AIJobType.UNKNOWN, 0.35, scope, "clarification_or_plan", True, "No hay intención clara")


def classify_ai_job_intent(prompt: str, *, worldbuilding_active: bool = False) -> AIJobType:
    """DEPRECATED wrapper around classify_intent. No production caller remains;
    the command bar/toolbar/menu all pass an explicit AIJobType now."""
    return classify_intent(prompt, {"worldbuilding_active": worldbuilding_active}).intent_type


def _creates_for_intent(intent_type: AIJobType) -> list[str]:
    if intent_type == AIJobType.GENERATE_ENTITIES:
        return ["candidatos de hoja"]
    if intent_type == AIJobType.GENERATE_TREE:
        return ["candidato de rama", "candidatos de nodos internos opcionales"]
    if intent_type == AIJobType.SUGGEST_RELATIONS:
        return ["candidatos de relación"]
    if intent_type in (AIJobType.ANALYZE_COHERENCE, AIJobType.REVIEW_GRAPH, AIJobType.EXPLAIN_FROM_CAUSES):
        return ["informe", "propuestas", "preguntas abiertas"]
    if intent_type == AIJobType.EXPAND_WORLDBUILDING:
        return ["candidatos de anillo/rama", "relaciones causales candidatas"]
    if intent_type == AIJobType.CREATE_RING_TEMPLATE:
        return ["plantilla de anillo (estructura causal de dominios)", "relaciones causales candidatas"]
    if intent_type == AIJobType.EDIT_ENTITIES:
        return ["candidatos de edición de cuerpo/campos de hojas o ramas existentes"]
    if intent_type == AIJobType.EDIT_RELATION:
        return ["candidatos de edición de relación existente"]
    if intent_type == AIJobType.EDIT_RING:
        return ["candidatos de edición de anillo (descripción y orden)"]
    if intent_type == AIJobType.EDIT_MILESTONE:
        return ["candidatos de edición de hito existente"]
    if intent_type == AIJobType.PROPOSE_MILESTONES:
        return ["candidatos de hito causal", "relaciones causales candidatas"]
    if intent_type in _TEXT_INTENTS:
        return ["texto sugerido (no canon hasta guardar)"]
    return ["plan revisable"]


def _expected_output_for_intent(intent_type: AIJobType) -> str:
    if intent_type == AIJobType.GENERATE_ENTITIES:
        return "entity_candidates"
    if intent_type == AIJobType.GENERATE_TREE:
        return "tree_candidates"
    if intent_type == AIJobType.SUGGEST_RELATIONS:
        return "relation_candidates"
    if intent_type == AIJobType.ANALYZE_COHERENCE:
        return "analysis_report"
    if intent_type == AIJobType.EXPAND_WORLDBUILDING:
        return "worldbuilding_candidates"
    if intent_type == AIJobType.CREATE_RING_TEMPLATE:
        return "worldbuilding_candidates"
    if intent_type == AIJobType.EXPLAIN_FROM_CAUSES:
        return "explanation_report"
    if intent_type == AIJobType.REVIEW_GRAPH:
        return "analysis_report"
    if intent_type == AIJobType.FREEFORM_PLANNING:
        return "plan_report"
    if intent_type in (AIJobType.EDIT_ENTITIES, AIJobType.EDIT_RELATION, AIJobType.EDIT_RING, AIJobType.EDIT_MILESTONE):
        return "edit_candidates"
    if intent_type == AIJobType.PROPOSE_MILESTONES:
        return "milestone_candidates"
    if intent_type in _TEXT_INTENTS:
        return "text"
    return "clarification_or_plan"


def build_job_plan(intent: CommandBarIntent, prompt: str, context: dict[str, Any] | None = None, *, job_id: str = "") -> AIJobPlan:
    context = dict(context or {})
    label = prompt.strip().replace("\n", " ")[:72] or "Tarea IA"
    steps = [
        "Construir contexto autorizado de proyecto/grafo",
        "Interpretar la petición completa del usuario",
        "Consultar IA con prompt exacto y contexto relevante",
        "Convertir salida en resultado revisable sin canonizar",
    ]
    return AIJobPlan(
        job_id=job_id,
        intent=intent,
        prompt=prompt.strip(),
        context=context,
        title=f"{intent.intent_type.value.replace('_', ' ')} — {label}",
        steps=steps,
        target_scope=intent.target_scope,
        expected_result=intent.expected_output_type,
        creates=_creates_for_intent(intent.intent_type),
    )


def _first_active_layer(context_scope: dict[str, Any]) -> str:
    layers = context_scope.get("active_layer_ids") or []
    if isinstance(layers, (list, tuple)) and layers:
        return str(layers[0])
    return ""


def _selected_entity_ids(context_scope: dict[str, Any]) -> list[str]:
    value = context_scope.get("selected_entity_ids") or []
    return [str(item) for item in value if str(item)] if isinstance(value, (list, tuple)) else []


def _selected_relation_ids(context_scope: dict[str, Any]) -> list[str]:
    value = context_scope.get("selected_relation_ids") or []
    return [str(item) for item in value if str(item)] if isinstance(value, (list, tuple)) else []


def _candidate(
    *,
    title: str,
    candidate_type: str,
    proposed_data: dict[str, Any],
    job: AIJob,
    justification: str,
    confidence: float = 0.62,
    expected_impact: str = "Revisión humana requerida antes de entrar al canon.",
) -> dict[str, Any]:
    return {
        "candidate_type": candidate_type,
        "state": "pendiente",
        "title": title,
        "proposed_data": proposed_data,
        "source": "ai_command_bar",
        "source_id": job.id,
        "confidence": confidence,
        "justification": justification,
        "expected_impact": expected_impact,
        "metadata": {
            "ai_job_id": job.id,
            "ai_job_type": job.type.value,
            "prompt": job.prompt,
            "context_scope": dict(job.context_scope),
            "canon_auto_mutation": False,
            "provider_backed": True,
        },
    }


def _strip_code_fences(raw: str) -> str:
    """Unwrap a ```json … ``` (or plain ```…```) markdown block if present."""
    match = re.search(r"```(?:json)?\s*(.+?)\s*```", raw, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else raw


def _first_balanced_json(raw: str) -> str | None:
    """Return the first balanced {...} object, ignoring braces inside strings."""
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    return None


def _extract_json(text: str) -> dict[str, Any]:
    """Coax a JSON object out of a model response (BETA1-AI01: hardened).

    Handles plain JSON, ```json fenced blocks, and a JSON object embedded in
    prose. Falls back to a {summary, report} so nothing is silently lost."""
    original = str(text or "")
    raw = _strip_code_fences(original.strip())
    if not raw:
        return {}
    # 1. Whole payload is JSON.
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"report": original}
    except Exception:
        pass
    # 2. First balanced object embedded in prose.
    candidate = _first_balanced_json(raw)
    if candidate:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    # 3. Last resort: greedy first-to-last brace.
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {"summary": "Respuesta no estructurada", "report": original}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stage_results(model_payload: dict[str, Any], job: AIJob) -> dict[str, Any]:
    """Convert model payload to reviewable candidates/report. Never mutates canon."""
    payload = dict(model_payload or {})
    layer_id = _first_active_layer(job.context_scope)
    selected_entity_ids = _selected_entity_ids(job.context_scope)
    selected_relation_ids = _selected_relation_ids(job.context_scope)
    candidates: list[dict[str, Any]] = []

    chronology = payload.get("project_chronology_suggestion") or payload.get("chronology_suggestion")
    if isinstance(chronology, dict):
        proposed = {"kind": "project_chronology_suggestion", **chronology}
        candidates.append(_candidate(
            title=str(proposed.get("title") or "Propuesta de calendario"),
            candidate_type="sugerencia_ia",
            proposed_data=proposed,
            job=job,
            justification=str(proposed.get("rationale") or "Propuesta de cronologia/calendario generada por IA."),
            confidence=0.58,
            expected_impact="Propone configurar la cronologia del proyecto; no se aplica sin aceptacion.",
        ))

    for milestone in _safe_list(payload.get("hitos") or payload.get("milestones")):
        if not isinstance(milestone, dict):
            continue
        title = str(milestone.get("title") or milestone.get("titulo") or "Hito sugerido").strip()
        if not title:
            continue
        summary = str(milestone.get("summary") or milestone.get("description") or milestone.get("resumen") or "").strip()
        body = str(milestone.get("body") or milestone.get("rationale") or milestone.get("justification") or "").strip()
        chronology_position = str(milestone.get("chronology_position") or milestone.get("chronology_key") or "").strip()
        try:
            sort_index = int(milestone.get("sort_index", 0) or 0)
        except (TypeError, ValueError):
            sort_index = 0
        primary = selected_entity_ids[0] if selected_entity_ids else ""
        hito_payload = {
            "title": title,
            "description": summary,
            "rationale": body,
            "status": "candidate",
            "affected_entity_ids": list(selected_entity_ids),
            "caused_relation_ids": list(selected_relation_ids),
            "layer_ids": [layer_id] if layer_id else [],
            "metadata": {
                "body": body,
                "chronology_key": chronology_position,
                "sort_index": sort_index,
                "primary_entity_id": primary,
                "ai_job_id": job.id,
                "origin_prompt": job.prompt,
            },
        }
        candidates.append(_candidate(
            title=f"Hito sugerido: {title}",
            candidate_type="sugerencia_ia",
            proposed_data={"kind": "causal_milestone", "milestone": hito_payload},
            job=job,
            justification=str(milestone.get("rationale") or milestone.get("justification") or "Hito sugerido desde una seleccion existente."),
            confidence=0.60,
            expected_impact="Propone un hito relacionado; al aceptar se crea por la ruta segura de hitos.",
        ))

    # Process hojas (B39) — also accept legacy "entities" key for backward compatibility
    for entity in _safe_list(payload.get("hojas") or payload.get("entities")):
        if not isinstance(entity, dict):
            continue
        name = str(entity.get("name") or "Hoja propuesta").strip()
        if not name:
            continue
        entity_type = str(entity.get("entity_type") or "personaje")
        display_type = str(entity.get("display_type") or "hoja")
        layer_ids = entity.get("layer_ids") if isinstance(entity.get("layer_ids"), list) else ([layer_id] if layer_id else [])
        proposed = {
            "name": name,
            "entity_type": entity_type,
            "brief_description": str(entity.get("brief_description") or entity.get("description") or "").strip(),
            "body": str(entity.get("body") or entity.get("extended_description") or "").strip(),
            "layer_ids": layer_ids,
            "display_type": display_type,
            "custom_metadata": {"origin_prompt": job.prompt, "ai_job_id": job.id},
        }
        candidates.append(_candidate(
            title=f"Hoja candidata: {name}",
            candidate_type="entidad",
            proposed_data=proposed,
            job=job,
            justification=str(entity.get("rationale") or "Propuesta generada desde el prompt exacto del usuario."),
        ))

    # Process ramas (B39) — also accept legacy "trees" key for backward compatibility
    for tree in _safe_list(payload.get("ramas") or payload.get("trees")):
        if not isinstance(tree, dict):
            continue
        name = str(tree.get("name") or "Rama propuesta").strip()
        entity_type = str(tree.get("entity_type") or "contenedor")
        display_type = "rama"
        layer_ids = tree.get("layer_ids") if isinstance(tree.get("layer_ids"), list) else ([layer_id] if layer_id else [])
        proposed = {
            "name": name,
            "entity_type": entity_type,
            "brief_description": str(tree.get("brief_description") or tree.get("description") or "").strip(),
            "layer_ids": layer_ids,
            "display_type": display_type,
            "custom_metadata": {"origin_prompt": job.prompt, "ai_job_id": job.id, "candidate_tree": True},
        }
        candidates.append(_candidate(
            title=f"Rama candidata: {name}",
            candidate_type="entidad",
            proposed_data=proposed,
            job=job,
            justification=str(tree.get("rationale") or "Rama propuesta para revisión."),
        ))

    # BUG 4 fix: stage entity edits as reviewable candidates (not new entities)
    for edit in _safe_list(payload.get("entity_edits")):
        if not isinstance(edit, dict):
            continue
        entity_name = str(edit.get("entity_name") or "").strip()
        if not entity_name:
            continue
        field = str(edit.get("field") or "body").strip()
        proposed_value = str(edit.get("proposed_value") or "").strip()
        if not proposed_value:
            continue
        candidates.append(_candidate(
            title=f"Editar {field} de {entity_name}",
            candidate_type="sugerencia_ia",
            proposed_data={
                "report": f"Propuesta de edición para '{entity_name}':\n\n{proposed_value}",
                "edit_target_name": entity_name,
                "edit_field": field,
                "edit_proposed_value": proposed_value,
                "issues": [],
                "proposals": [{"title": f"Editar {field} de {entity_name}", "description": proposed_value[:200]}],
                "open_questions": [],
                "prompt": job.prompt,
            },
            job=job,
            justification=str(edit.get("rationale") or f"Edición propuesta de {field} para hoja o rama existente."),
            confidence=0.65,
            expected_impact=f"Editar {field} de '{entity_name}' tras revisión humana.",
        ))

    # Structured edits for relations / rings / milestones (deterministic "Editar"
    # cells). Each becomes a reviewable sugerencia_ia candidate; never canon.
    for kind_key, label in (
        ("relation_edits", "relación"),
        ("ring_edits", "anillo"),
        ("milestone_edits", "hito"),
    ):
        for edit in _safe_list(payload.get(kind_key)):
            if not isinstance(edit, dict):
                continue
            target_name = str(
                edit.get("target_name") or edit.get("name") or edit.get("title") or ""
            ).strip()
            field = str(edit.get("field") or "description").strip()
            proposed_value = str(edit.get("proposed_value") or "").strip()
            if not (target_name and proposed_value):
                continue
            candidates.append(_candidate(
                title=f"Editar {field} de {label}: {target_name}",
                candidate_type="sugerencia_ia",
                proposed_data={
                    "report": f"Propuesta de edición de {label} '{target_name}':\n\n{proposed_value}",
                    "edit_kind": kind_key,
                    "edit_target_name": target_name,
                    "edit_field": field,
                    "edit_proposed_value": proposed_value,
                    "issues": [],
                    "proposals": [{"title": f"Editar {field} de {target_name}", "description": proposed_value[:200]}],
                    "open_questions": [],
                    "prompt": job.prompt,
                },
                job=job,
                justification=str(edit.get("rationale") or f"Edición propuesta de {field} para {label} existente."),
                confidence=0.65,
                expected_impact=f"Editar {field} de {label} '{target_name}' tras revisión humana.",
            ))

    # Ring template (CREATE_RING_TEMPLATE): initial rings as a causal domain
    # structure. Rings are world layers, not entities, so each stages as a
    # reviewable sugerencia_ia card describing the proposed ring.
    for ring in _safe_list(payload.get("rings") or payload.get("anillos")):
        if not isinstance(ring, dict):
            continue
        ring_name = str(ring.get("name") or ring.get("domain") or "").strip()
        if not ring_name:
            continue
        ring_desc = str(ring.get("description") or ring.get("brief_description") or "").strip()
        try:
            ring_order = int(ring.get("order", 0) or 0)
        except (TypeError, ValueError):
            ring_order = 0
        candidates.append(_candidate(
            title=f"Anillo propuesto: {ring_name}",
            candidate_type="sugerencia_ia",
            proposed_data={
                "kind": "ring_template",
                "ring_name": ring_name,
                "domain": str(ring.get("domain") or ring_name),
                "description": ring_desc,
                "order": ring_order,
                "derived_from": str(ring.get("derived_from") or ""),
                "report": f"Anillo '{ring_name}' (orden {ring_order}).\n\n{ring_desc}",
                "prompt": job.prompt,
            },
            job=job,
            justification=str(ring.get("rationale") or "Anillo propuesto como plantilla causal inicial."),
            confidence=0.58,
            expected_impact="Propone un anillo/estrato; al aceptar se crea por la ruta segura de anillos.",
        ))

    selected = set(str(x) for x in (job.context_scope.get("selected_entity_ids") or []))
    relevant = job.context_scope.get("relevant_entities") or []
    relevant_ids = {str(e.get("id")) for e in relevant if isinstance(e, dict) and e.get("id")}
    allowed_ids = selected | relevant_ids

    report = str(payload.get("report") or payload.get("summary") or "Resultado IA listo para revisión.")
    analytical = job.type in {AIJobType.ANALYZE_COHERENCE, AIJobType.REVIEW_GRAPH, AIJobType.EXPLAIN_FROM_CAUSES, AIJobType.FREEFORM_PLANNING, AIJobType.UNKNOWN, AIJobType.EDIT_ENTITIES, AIJobType.EDIT_RELATION, AIJobType.EDIT_RING, AIJobType.EDIT_MILESTONE}
    # BUG 1 fix: only add sugerencia_ia candidate for truly analytical jobs.
    # For generative jobs (entities/trees/relations), the structural candidates
    # are the real output; a synthetic "proposal" card is noise.
    has_structural_candidates = any(
        c.get("candidate_type") in ("entidad", "relacion") for c in candidates
    )
    if analytical and not has_structural_candidates:
        candidates.append(_candidate(
            title=str(payload.get("summary") or "Informe revisable de IA"),
            candidate_type="sugerencia_ia",
            proposed_data={
                "report": report,
                "issues": _safe_list(payload.get("issues")),
                "proposals": _safe_list(payload.get("proposals")),
                "open_questions": _safe_list(payload.get("open_questions")),
                "prompt": job.prompt,
                "scope": dict(job.context_scope),
            },
            job=job,
            justification="Informe/propuesta revisable; aceptar no aplica cambios estructurales al grafo.",
            confidence=0.55,
            expected_impact="Ayuda a decidir mejoras sin aplicar cambios automáticos.",
        ))

    # BUG 2 fix: for relations from the model that have names but lack real IDs,
    # create relacion candidates with source_name/target_name. On accept, the
    # service resolves names to entity IDs.
    # Ring templates have no relation entities: the causal structure lives in each
    # ring's order/derived_from, and the graph has no ring↔ring relations.
    relations_payload = [] if job.type == AIJobType.CREATE_RING_TEMPLATE else _safe_list(payload.get("relations"))
    for rel in relations_payload:
        if not isinstance(rel, dict):
            continue
        source_id = str(rel.get("source_id") or "")
        target_id = str(rel.get("target_id") or "")
        source_name = str(rel.get("source_name") or source_id or "")
        target_name = str(rel.get("target_name") or target_id or "")
        rel_type = str(rel.get("relation_type") or "esta_relacionado_con")
        desc = str(rel.get("description") or "Relación propuesta.")

        # Skip if both endpoints are already known real IDs and they pass the filter
        if source_id and target_id:
            if not allowed_ids or (source_id in allowed_ids and target_id in allowed_ids):
                candidates.append(_candidate(
                    title="Relación candidata",
                    candidate_type="relacion",
                    proposed_data={
                        "source_id": source_id,
                        "target_id": target_id,
                        "relation_type": rel_type,
                        "description": desc,
                    },
                    job=job,
                    justification=str(rel.get("rationale") or "Relación propuesta con endpoints del contexto."),
                ))
            continue

        # Relation has names but not IDs: create a relacion candidate with name-based lookup
        if not source_name and not target_name:
            continue
        candidates.append(_candidate(
            title=f"Relación: {source_name or '?'} → {target_name or '?'}",
            candidate_type="relacion",
            proposed_data={
                "source_name": source_name,
                "target_name": target_name,
                "relation_type": rel_type,
                "description": desc,
            },
            job=job,
            justification=f"Relación propuesta entre '{source_name}' y '{target_name}'. Se resolverá por nombre al aceptar.",
        ))

    kind = "analysis_report" if analytical else "candidate_batch"
    return {
        "kind": kind,
        "summary": str(payload.get("summary") or ("Informe listo" if analytical else "Candidatos listos para revisión")),
        "report": report,
        "candidates": candidates,
        "open_questions": _safe_list(payload.get("open_questions")),
        "model_payload": payload,
    }


def _context_for_prompt(context: dict[str, Any]) -> dict[str, Any]:
    # Keep only serializable, non-secret data. Context summaries should not expose JSON in normal UI.
    return dict(context or {})


def _b40_prompt_profile(context: dict[str, Any]) -> dict[str, Any]:
    """Derive model-facing behaviour instructions from B40 creative config."""
    ctx = dict(context or {})
    brief = ctx.get("creative_brief") or {}
    if not isinstance(brief, dict):
        brief = {}
    canon_raw = brief.get("canon")
    negative_raw = brief.get("negative_space")
    memory_raw = brief.get("taste_memory")
    ai_raw = brief.get("ai_preferences")
    canon = canon_raw if isinstance(canon_raw, dict) else {}
    negative = negative_raw if isinstance(negative_raw, dict) else {}
    memory = memory_raw if isinstance(memory_raw, dict) else {}
    ai = ai_raw if isinstance(ai_raw, dict) else {}
    return {
        "role": ai.get("default_role", "coauthor"),
        "strategy": ai.get("default_strategy", "profundizar"),
        "output_mode": ai.get("output_mode", "contrastive_options"),
        "default_num_options": ai.get("default_num_options", 3),
        "change_aggressiveness": ai.get("change_aggressiveness", 5),
        "uncertainty_policy": ai.get("uncertainty_policy", "conservative_proposal"),
        "context_depth": ai.get("context_depth", "balanced"),
        "hard_rules": canon.get("hard_rules", []),
        "soft_preferences": canon.get("soft_preferences", []),
        "continuity_strictness": canon.get("continuity_strictness", 5),
        "avoid": negative,
        "taste_memory": memory,
        "selected_effective_configs": ctx.get("creative_context", []),
        "selected_branch_overrides": ctx.get("branch_creative_context", []),
        "instructions": [
            "Respeta canon duro y continuidad configurada; si el usuario pide algo incompatible, proponlo como problema/reparación, no como canon.",
            "Evita tropos, soluciones, tonos y frases listados en negative_space.",
            "Usa taste_memory para aproximarte al gusto aceptado y evitar patrones rechazados.",
            "Si hay branch_creative_context, prioriza esos overrides locales sobre el perfil global.",
            "Toda salida estructural debe ser candidato revisable; nunca asumas canon automático.",
        ],
    }


# BETA1-AI01: the chronology/milestone output spec, attached ONLY to time-
# related jobs (before it rode along on every message — pure noise + tokens).
_CHRONOLOGY_OUTPUT_FORMATS: dict[str, Any] = {
    "project_chronology_suggestion": {
        "kind": "project_chronology_suggestion",
        "title": "string",
        "mode": "none | vague_periods | full_calendar",
        "summary": "string",
        "periods": ["Antiguedad", "Historia reciente", "Actualidad"],
        "eras": ["string"],
        "era_lengths": {"Era Antigua": "integer years"},
        "months": ["string"],
        "month_lengths": {"Enero": "integer days"},
        "weekdays": ["string"],
        "current_date": {"era": "string", "year": "integer", "month": "string", "day": "integer"},
        "units": ["string"],
        "display_format": "string",
        "supports_exact_dates": "boolean",
        "date_resolution": "string",
        "rationale": "string",
        "risks": ["string"],
        "questions_for_user": ["string"],
    },
    "milestones": [{
        "title": "string",
        "summary": "string",
        "body": "string",
        "chronology_position": "string",
        "sort_index": "integer",
        "rationale": "string",
        "confidence": "low | medium | high",
    }],
}

_CHRONOLOGY_HINT_TOKENS = ("hito", "cronolog", "calendar", "era", "milestone", "linea temporal", "línea temporal")


def _wants_chronology_formats(plan: AIJobPlan) -> bool:
    if getattr(plan.intent, "intent_type", None) == AIJobType.PROPOSE_MILESTONES:
        return True
    text = f"{getattr(plan.intent.intent_type, 'value', '')} {plan.prompt}".lower()
    return any(token in text for token in _CHRONOLOGY_HINT_TOKENS)


def _fase2_directives(context: dict[str, Any]) -> dict[str, Any] | None:
    """Surface the deterministic per-cell behaviours as explicit model directives.

    The host seeds these into context_scope via plan_command_jobs (suggestion
    count, @references, Explicar branching, ring template, relation fan-out pair)
    so the model honours them instead of guessing from prose."""
    ctx = dict(context or {})
    params: dict[str, Any] = {}
    instructions: list[str] = []

    count = ctx.get("suggestion_count")
    if count:
        params["numero_sugerencias"] = int(count)
        instructions.append(f"Devuelve exactamente {int(count)} sugerencia(s), ni más ni menos.")

    mentions = ctx.get("mentions") if isinstance(ctx.get("mentions"), dict) else {}
    refs = mentions.get("refs") or []
    if refs:
        params["referencias_at"] = refs
        names = ", ".join(str(r.get("name", "")) for r in refs if isinstance(r, dict))
        instructions.append(f"Usa como referencia SOLO las entidades/hitos mencionados con @: {names}.")

    explain_target = ctx.get("explain_target")
    if explain_target == "modify_refs":
        params["modo_explicar"] = "modificar_referencias"
        instructions.append(
            "Explicar con @referencias: modifica el TEXTO de las entidades/relaciones referenciadas "
            "para que expliquen la selección (claves 'entity_edits'/'relation_edits'); no crees entidades nuevas."
        )
    elif explain_target == "create_in_active_ring":
        params["modo_explicar"] = "crear_en_anillo_activo"
        ring = ctx.get("active_ring_id") or "el activo"
        instructions.append(
            f"Explicar sin referencias: crea hitos/entidades (máx {ctx.get('max_creations', 3)}) "
            f"en el anillo activo ({ring}) que expliquen la selección."
        )

    if ctx.get("ring_template"):
        params["plantilla_anillo"] = {"previous_ring_id": ctx.get("previous_ring_id") or ""}
        instructions.append(
            "Crear Anillo: genera UNA plantilla de anillos como estructura causal de dominios, derivando "
            "del anillo anterior y la configuración creativa. Clave 'rings' (name, domain, description, order, "
            "derived_from). Ignora cualquier selección."
        )

    pair = ctx.get("fanout_pair")
    if pair:
        params["par_relacion"] = list(pair)
        instructions.append("Propón UNA relación entre exactamente este par de entidades (clave 'relations').")

    if not params and not instructions:
        return None
    return {"parametros": params, "instrucciones": instructions}


def build_model_user_message(plan: AIJobPlan) -> str:
    # BETA1-AI01: leaner message. The context lived TWICE (full `plan` dump +
    # `contexto_autorizado`); now the plan carries only its shape and the
    # context appears once. Chronology spec attached on demand.
    message: dict[str, Any] = {
        "prompt_exacto_usuario": plan.prompt,
        "intent": plan.intent.to_dict(),
        "plan": {
            "title": plan.title,
            "steps": list(plan.steps),
            "target_scope": plan.target_scope,
            "expected_result": plan.expected_result,
            "creates": list(plan.creates),
        },
        "contexto_autorizado": _context_for_prompt(plan.context),
        "perfil_creativo_b40": _b40_prompt_profile(plan.context),
        "restricciones": {
            "no_canon_automatico": True,
            "solo_candidatos_revisables": True,
            "no_ids_inventados": True,
            "usar_prompt_exacto_como_instruccion_principal": True,
        },
    }
    directives = _fase2_directives(plan.context)
    if directives:
        message["directivas"] = directives
    # F3.2: causal-deductive ordering of the context (Anillos→Ramas→Hojas),
    # seeded by the host via order_context_by_causality.
    causal = plan.context.get("contexto_causal") if isinstance(plan.context, dict) else None
    if isinstance(causal, dict) and causal:
        message["contexto_causal"] = causal
    if _wants_chronology_formats(plan):
        message["formatos_h05"] = _CHRONOLOGY_OUTPUT_FORMATS
    return json.dumps(message, ensure_ascii=False, indent=2)


# Backward-compatible helper kept only for tests that inject explicit mock jobs.
def build_ai_job_result(job: AIJob, provider: AIProvider | None = None, *, allow_simulated: bool = False) -> dict[str, Any]:
    service = AIJobService(provider=provider or SimulatedAIProvider(), allow_simulated=allow_simulated)
    service._jobs[job.id] = job
    result = service.execute_job(job.id)
    if isinstance(result, Error):
        raise RuntimeError(result.error)
    return result.value.result


class AIJobService:
    """In-memory AI job registry and command-bar runner."""

    def __init__(
        self,
        provider: AIProvider | None = None,
        *,
        allow_simulated: bool = False,
        observability_log: AIObservabilityLog | None = None,
        timeout_seconds: int = DEFAULT_AI_TIMEOUT_SECONDS,
        rag_service: Any | None = None,
        project_provider: Callable[[], Any] | None = None,
        prompt_trace_store: Any | None = None,
        gateway: AIRequestGateway | None = None,
    ):
        self._jobs: dict[str, AIJob] = {}
        self._provider = provider if provider is not None else create_provider()
        # BETA1-AI02: single provider chokepoint. Every model call goes through
        # the gateway (sanitize → params → dispatch). Injectable for tests.
        self._gateway = gateway if gateway is not None else AIRequestGateway(provider=self._provider)
        self.allow_simulated = allow_simulated
        self.observability_log = observability_log or AIObservabilityLog()
        self.timeout_seconds = max(1, int(timeout_seconds or DEFAULT_AI_TIMEOUT_SECONDS))
        self._rag_service = rag_service
        self._project_provider = project_provider
        self._prompt_trace_store = prompt_trace_store

    @property
    def provider(self) -> AIProvider:
        """The backing AI provider (read-only). Lets callers that share this
        service reuse the exact same provider instance for their checks."""
        return self._provider

    def set_provider(self, provider: AIProvider) -> None:
        """Swap the backing provider (and its gateway) at runtime — e.g. after the
        user configures a real provider in Settings, so existing jobs/services
        that share this instance stop using the simulated fallback."""
        if provider is None:
            return
        self._provider = provider
        self._gateway = AIRequestGateway(provider=provider)

    def create_job(self, job_type: AIJobType | str, prompt: str, *, context_scope: dict[str, Any] | None = None, explicit: bool = False) -> Result:
        prompt = (prompt or "").strip()
        if not prompt:
            return Error("El prompt no puede estar vacío")
        context = dict(context_scope or {})
        try:
            resolved_type = job_type if isinstance(job_type, AIJobType) else AIJobType(str(job_type))
        except ValueError:
            resolved_type = AIJobType.REVIEW_GRAPH
        if explicit:
            # BETA1-AI02: focused job — the caller's intent is authoritative, so
            # skip prompt classification and run this exact task type.
            intent = CommandBarIntent(
                intent_type=resolved_type,
                confidence=1.0,
                target_scope=_scope_from_context(_norm(prompt), context),
                expected_output_type=_expected_output_for_intent(resolved_type),
                rationale="Acción enfocada (intent explícito).",
                planner_source="explicit",
            )
        else:
            intent = classify_intent(prompt, context)
            if resolved_type not in (AIJobType.UNKNOWN, intent.intent_type):
                # UI may pass a legacy heuristic type; keep explicit type but preserve classifier rationale.
                intent.intent_type = resolved_type
        job = AIJob(
            type=intent.intent_type,
            explicit_intent=resolved_type if explicit else None,
            prompt=prompt,
            context_scope=context,
            message="Job creado. Pendiente de ejecución.",
            progress=0.0,
            intent=intent.to_dict(),
        )
        plan = build_job_plan(intent, prompt, context, job_id=job.id)
        job.plan = plan.to_dict()
        self._jobs[job.id] = job
        return Ok(job)

    def run_focused_job(self, job_type: AIJobType | str, prompt: str, *, context_scope: dict[str, Any] | None = None, progress_callback=None) -> Result:
        """Create and execute a focused (explicit-intent) job in one call.

        Entry point for contextual callers (graph menu, detail panel) that
        already know the task type and seed their own context. Goes through the
        exact same execute_job pipeline as the command bar.
        """
        created = self.create_job(job_type, prompt, context_scope=context_scope, explicit=True)
        if isinstance(created, Error):
            return created
        return self.execute_job(created.value.id, progress_callback=progress_callback)

    def list_jobs(self) -> list[AIJob]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at)

    def get_job(self, job_id: str) -> Result:
        job = self._jobs.get(job_id)
        if job is None:
            return Error("Job IA no encontrado")
        return Ok(job)

    def update_status(
        self,
        job_id: str,
        status: AIJobStatus | str,
        *,
        message: str = "",
        progress: float | None = None,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> Result:
        job = self._jobs.get(job_id)
        if job is None:
            return Error("Job IA no encontrado")
        try:
            job.status = status if isinstance(status, AIJobStatus) else AIJobStatus(str(status))
        except ValueError:
            return Error("Estado de job IA no válido")
        if message:
            job.message = message
        if progress is not None:
            job.progress = max(0.0, min(1.0, float(progress)))
        if result is not None:
            job.result = dict(result)
        if error:
            job.error = _sanitize_error(error)
        job.updated_at = _now_iso()
        return Ok(job)

    def _record_observability(
        self,
        job: AIJob,
        *,
        status: str,
        error_type: str | None = None,
        duration_ms: float = 0.0,
        output_size: int = 0,
        model: str | None = None,
    ) -> None:
        params = ModelParams.from_intent(job.type.value if isinstance(job.type, AIJobType) else str(job.type))
        context_size = len(json.dumps(job.context_scope or {}, ensure_ascii=False, default=str))
        provider_name = str(getattr(self._provider, "provider_name", "ai"))
        self.observability_log.record(AIJobRecord(
            job_id=job.id,
            intent_type=job.type.value if isinstance(job.type, AIJobType) else str(job.type),
            model=model or str(getattr(self._provider, "model", provider_name)),
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            context_depth=len(job.context_scope or {}),
            input_size=len(job.prompt or "") + context_size,
            output_size=max(0, int(output_size or 0)),
            duration_ms=max(0.0, float(duration_ms or 0.0)),
            status=status,
            error_type=error_type,
            raw_prompt=job.prompt,
        ))

    def _build_execution_plan(self, job: AIJob) -> Result:
        if job.explicit_intent is not None:
            # BETA1-AI02: focused job — use the given intent verbatim, no classify.
            intent = CommandBarIntent(
                intent_type=job.explicit_intent,
                confidence=1.0,
                target_scope=_scope_from_context(_norm(job.prompt), job.context_scope),
                expected_output_type=_expected_output_for_intent(job.explicit_intent),
                rationale="Acción enfocada (intent explícito).",
                planner_source="explicit",
            )
            return Ok((intent, build_job_plan(intent, job.prompt, job.context_scope, job_id=job.id)))

        # DEPRECATED fallback: every UI surface now creates explicit-intent jobs
        # (deterministic command matrix / focused actions). This heuristic path is
        # only reachable from non-explicit create_job calls in legacy tests and is
        # scheduled for removal once those tests migrate to the matrix.
        intent = classify_intent(job.prompt, job.context_scope)
        return Ok((intent, build_job_plan(intent, job.prompt, job.context_scope, job_id=job.id)))

    def _with_rag_context(self, job: AIJob, plan: AIJobPlan) -> AIJobPlan:
        if self._rag_service is None:
            return plan

        from packages.application.rag_context import RAGContextBuilder

        context = dict(plan.context)
        project = None
        if self._project_provider is not None:
            try:
                project = self._project_provider()
            except Exception as exc:  # pragma: no cover - defensive UI boundary
                context["rag_context_pack"] = {
                    "schema": "context_pack/v1",
                    "warnings": [f"rag_project_provider_error: {_sanitize_error(str(exc))}"],
                    "items": [],
                    "truncated": False,
                }
                return build_job_plan(plan.intent, plan.prompt, context, job_id=job.id)

        built = RAGContextBuilder(self._rag_service).build_for_job_plan(project, plan)
        if isinstance(built, Error):
            context["rag_context_pack"] = {
                "schema": "context_pack/v1",
                "warnings": [f"rag_context_error: {_sanitize_error(built.error)}"],
                "items": [],
                "truncated": False,
            }
            return build_job_plan(plan.intent, plan.prompt, context, job_id=job.id)

        context["rag_context_pack"] = built.value.to_dict()
        return build_job_plan(plan.intent, plan.prompt, context, job_id=job.id)

    def _trace_prompt_request(
        self,
        *,
        job: AIJob,
        plan: AIJobPlan,
        provider_name: str,
        model_user_message: str,
        system_prompt: str,
    ) -> None:
        if self._prompt_trace_store is None:
            return
        try:
            self._prompt_trace_store.record_request(
                job_id=job.id,
                provider=provider_name,
                prompt=job.prompt,
                system_prompt=system_prompt,
                model_user_message=model_user_message,
                plan=plan.to_dict(),
            )
        except Exception:
            return

    def _trace_prompt_response(
        self,
        *,
        job_id: str,
        status: str,
        response_text: str = "",
        error: str = "",
        elapsed_ms: float = 0.0,
    ) -> None:
        if self._prompt_trace_store is None:
            return
        try:
            self._prompt_trace_store.record_response(
                job_id,
                status=status,
                response_text=response_text,
                error=error,
                elapsed_ms=elapsed_ms,
            )
        except Exception:
            return

    def _execute_job_pre_d03(self, job_id: str, progress_callback=None) -> Result:
        job = self._jobs.get(job_id)
        if job is None:
            return Error("Job IA no encontrado")
        if job.status == AIJobStatus.CANCELLED:
            return Error("Job IA cancelado")
        provider_name = str(getattr(self._provider, "provider_name", "ai"))
        if provider_name == "simulated" and not self.allow_simulated:
            msg = "Configura un proveedor IA real para la command bar; no se generará contenido simulado."
            self.update_status(job_id, AIJobStatus.FAILED, message="Provider IA no configurado", error=msg, progress=1.0)
            return Error(msg)

        self.update_status(job_id, AIJobStatus.BUILDING_CONTEXT, message="Construyendo contexto…", progress=0.20)
        if progress_callback:
            progress_callback(job)
        intent = classify_intent(job.prompt, job.context_scope)
        job.intent = intent.to_dict()
        self.update_status(job_id, AIJobStatus.PLANNING, message="Interpretando petición…", progress=0.35)
        if progress_callback:
            progress_callback(job)
        plan = build_job_plan(intent, job.prompt, job.context_scope, job_id=job.id)
        plan = self._with_rag_context(job, plan)
        job.type = intent.intent_type
        job.plan = plan.to_dict()
        self.update_status(job_id, AIJobStatus.WAITING_FOR_MODEL, message="Consultando IA…", progress=0.60)
        if progress_callback:
            progress_callback(job)
        model_user_message = build_model_user_message(plan)
        system_prompt = system_prompt_for_intent(plan.intent.intent_type.value)
        self._trace_prompt_request(
            job=job,
            plan=plan,
            provider_name=provider_name,
            model_user_message=model_user_message,
            system_prompt=system_prompt,
        )
        try:
            gw = self._gateway.execute(GatewayRequest(
                intent=plan.intent.intent_type.value,
                user_prompt=model_user_message,
                system_prompt_override=system_prompt,
                json_mode=True,
                validate=False,
            ))
            text, error = gw.text, gw.error
        except Exception as exc:
            text, error = None, str(exc)
        if error:
            safe = _sanitize_error(error)
            self._trace_prompt_response(job_id=job.id, status="error", error=safe)
            self.update_status(job_id, AIJobStatus.FAILED, message="Job fallido", error=safe, progress=1.0)
            return Error(safe)
        if not text:
            msg = "El proveedor IA no devolvió contenido."
            self._trace_prompt_response(job_id=job.id, status="error", error=msg)
            self.update_status(job_id, AIJobStatus.FAILED, message="Job fallido", error=msg, progress=1.0)
            return Error(msg)
        self.update_status(job_id, AIJobStatus.POSTPROCESSING, message="Preparando candidatos…", progress=0.80)
        if progress_callback:
            progress_callback(job)
        payload = _extract_json(text)
        result = stage_results(payload, job)
        self._trace_prompt_response(job_id=job.id, status="ok", response_text=text)
        result["provider"] = provider_name
        updated = self.update_status(
            job_id,
            AIJobStatus.READY_FOR_REVIEW,
            message=result.get("summary", "Listo para revisar"),
            progress=1.0,
            result=result,
        )
        if progress_callback and not isinstance(updated, Error):
            progress_callback(updated.value)
        return updated

    def execute_job(self, job_id: str, progress_callback=None) -> Result:
        """Execute a command-bar job with cooperative cancel and timeout.

        D03 keeps provider work outside the UI thread via `_AIJobWorker`; this
        service owns the job state machine and is safe to call from that worker.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return Error("Job IA no encontrado")
        if job.status == AIJobStatus.CANCELLED:
            return Error("Job IA cancelado")
        provider_name = str(getattr(self._provider, "provider_name", "ai"))
        if provider_name == "simulated" and not self.allow_simulated:
            msg = "Configura un proveedor IA real para la command bar; no se generara contenido simulado."
            self.update_status(job_id, AIJobStatus.FAILED, message="Provider IA no configurado", error=msg, progress=1.0)
            self._record_observability(job, status="error", error_type="provider_unconfigured")
            return Error(msg)

        def emit_current() -> None:
            if progress_callback:
                current = self._jobs.get(job_id)
                if current is not None:
                    progress_callback(current)

        def cancelled_error() -> Error | None:
            cancelled = self._ensure_not_cancelled(job_id)
            return cancelled if isinstance(cancelled, Error) else None

        self.update_status(job_id, AIJobStatus.BUILDING_CONTEXT, message="Construyendo contexto...", progress=0.20)
        emit_current()
        cancelled = cancelled_error()
        if cancelled:
            return cancelled

        self.update_status(job_id, AIJobStatus.PLANNING, message="Interpretando peticion...", progress=0.35)
        emit_current()
        cancelled = cancelled_error()
        if cancelled:
            return cancelled

        planned = self._build_execution_plan(job)
        if isinstance(planned, Error):
            self.update_status(job_id, AIJobStatus.FAILED, message="No se pudo interpretar la peticion", error=planned.error, progress=1.0)
            self._record_observability(job, status="error", error_type="planner_error")
            return planned
        intent, plan = planned.value
        plan = self._with_rag_context(job, plan)
        job.intent = intent.to_dict()
        job.type = intent.intent_type
        job.plan = plan.to_dict()
        self.update_status(job_id, AIJobStatus.WAITING_FOR_MODEL, message="Pensando...", progress=0.60)
        emit_current()
        cancelled = cancelled_error()
        if cancelled:
            return cancelled

        model_user_message = build_model_user_message(plan)
        # Per-function system prompt: each intent asks only for its own output.
        system_prompt = system_prompt_for_intent(plan.intent.intent_type.value)
        self._trace_prompt_request(
            job=job,
            plan=plan,
            provider_name=provider_name,
            model_user_message=model_user_message,
            system_prompt=system_prompt,
        )
        started = time.monotonic()
        is_text = _is_text_intent(plan.intent.intent_type)
        # F3: UI radial tuners may override the intent's recommended params.
        temp_override = _opt_float(job.context_scope.get("model_temperature"))
        tokens_override = _opt_int(job.context_scope.get("model_max_tokens"))
        try:
            gw = self._gateway.execute(GatewayRequest(
                intent=plan.intent.intent_type.value,
                user_prompt=model_user_message,
                system_prompt_override=system_prompt,
                timeout=self.timeout_seconds,
                json_mode=not is_text,
                validate=False,
                temperature=temp_override,
                max_tokens=tokens_override,
            ))
            text, error = gw.text, gw.error
        except Exception as exc:
            text, error = None, str(exc)
        elapsed = time.monotonic() - started

        cancelled = cancelled_error()
        if cancelled:
            return cancelled
        if elapsed > self.timeout_seconds:
            msg = f"Timeout IA: el job supero {self.timeout_seconds}s."
            self._trace_prompt_response(job_id=job.id, status="error", error=msg, elapsed_ms=elapsed * 1000)
            self.update_status(job_id, AIJobStatus.FAILED, message="Timeout IA", error=msg, progress=1.0)
            self._record_observability(job, status="error", error_type="timeout", duration_ms=elapsed * 1000)
            return Error(msg)
        if error:
            safe = _sanitize_error(error)
            self._trace_prompt_response(job_id=job.id, status="error", error=safe, elapsed_ms=elapsed * 1000)
            self.update_status(job_id, AIJobStatus.FAILED, message="Job fallido", error=safe, progress=1.0)
            self._record_observability(job, status="error", error_type="provider_error", duration_ms=elapsed * 1000)
            return Error(safe)
        if not text:
            msg = "El proveedor IA no devolvio contenido."
            self._trace_prompt_response(job_id=job.id, status="error", error=msg, elapsed_ms=elapsed * 1000)
            self.update_status(job_id, AIJobStatus.FAILED, message="Job fallido", error=msg, progress=1.0)
            self._record_observability(job, status="error", error_type="empty_response", duration_ms=elapsed * 1000)
            return Error(msg)

        self.update_status(job_id, AIJobStatus.POSTPROCESSING, message="Preparando candidatos...", progress=0.80)
        emit_current()
        cancelled = cancelled_error()
        if cancelled:
            return cancelled

        if is_text:
            result = _text_result(text)
        else:
            payload = _extract_json(text)
            result = stage_results(payload, job)
        self._trace_prompt_response(job_id=job.id, status="ok", response_text=text, elapsed_ms=elapsed * 1000)
        result["provider"] = provider_name
        result["timeout_seconds"] = self.timeout_seconds
        model_name = str(getattr(self._provider, "model", provider_name))
        for candidate in result.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            metadata = dict(candidate.get("metadata") or {})
            metadata.setdefault("provider", provider_name)
            metadata.setdefault("model", model_name)
            metadata.setdefault("trace_status", "ready_for_review")
            candidate["metadata"] = metadata
        updated = self.update_status(
            job_id,
            AIJobStatus.READY_FOR_REVIEW,
            message=result.get("summary", "Listo para revisar"),
            progress=1.0,
            result=result,
        )
        self._record_observability(
            job,
            status="ok",
            duration_ms=elapsed * 1000,
            output_size=len(text or ""),
            model=model_name,
        )
        if progress_callback and not isinstance(updated, Error):
            progress_callback(updated.value)
        return updated

    def _ensure_not_cancelled(self, job_id: str) -> Result | None:
        job = self._jobs.get(job_id)
        if job is None:
            return Error("Job IA no encontrado")
        if job.status == AIJobStatus.CANCELLED:
            job.message = "Job cancelado"
            job.updated_at = _now_iso()
            return Error("Job IA cancelado")
        return None

    def cancel_job(self, job_id: str) -> Result:
        job = self._jobs.get(job_id)
        if job is None:
            return Error("Job IA no encontrado")
        if not job.cancellable:
            return Error("Este job no se puede cancelar")
        job.status = AIJobStatus.CANCELLED
        job.message = "Job cancelado"
        job.progress = min(job.progress, 1.0)
        job.updated_at = _now_iso()
        return Ok(job)


def _sanitize_error(error: str) -> str:
    text = str(error or "Error IA")
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"sk-[A-Za-z0-9._\-]+", "[REDACTED]", text)
    return text[:500]
