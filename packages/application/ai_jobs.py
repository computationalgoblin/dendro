"""B39 AI command-bar jobs.

AI jobs are the command-bar unit of work. They never mutate canon directly:
results are staged as reviewable candidates, reports, suggestions or open
questions. The command-bar pipeline is intentionally split into:

1. explicit intent (toda la superficie viva crea jobs con tipo explícito)
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
import threading
import time
import uuid

from packages.domain.result import Error, Ok, Result
from packages.application.ai_observability import AIJobRecord, AIObservabilityLog
from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest, ModelParams
from packages.application.ai_provider_port import (
    AIProvider,
    provider_chat,
    resolve_provider,
)
from packages.application.context_budget import ContextBudgetManager
from packages.application.prompt_assembler import (
    PromptAssembler,
    build_context_preview,
    build_model_user_message_with_warnings,
)


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
from packages.application.candidate_service import (
    AI_EDITABLE_ENTITY_FIELDS,
    AI_EDITABLE_MILESTONE_FIELDS,
    AI_ENTITY_FIELD_ALIASES,
    AI_MILESTONE_FIELD_ALIASES,
)

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
    # UX8: repara incoherencias del informe en cambios CONCRETOS sobre canon
    # (no sugerencias literales). El usuario los revisa en un panel antes/después.
    REPAIR_COHERENCE = "repair_coherence"
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
    # CRON: paso del recorrido cronológico. Lectura editorial + diagnóstico +
    # candidatos/diffs por el MISMO pipeline que analyze_coherence (no muta canon).
    CHRONOLOGY_WALK_STEP = "chronology_walk_step"
    # BETA1-AI02: text-only intents. Free text, no JSON staging — the suggestion
    # stays inline (e.g. the entity detail panel) until the user saves.
    IMPROVE_TEXT = "improve_text"
    GENERATE_TEXT = "generate_text"
    # BETA2-FOCO: riego — diagnóstico IA puro de una entidad (jamás candidatos,
    # jamás canon). El resultado se persiste como WateringDiagnostic.
    WATER_ENTITY = "water_entity"
    # BETA2-MEM-05: actualización IA de la Memoria editorial (derivada, no canon).
    # Produce resumen/estado/contradicciones/huecos anclados por id; nunca canon.
    UPDATE_MEMORY = "update_memory"
    # BETA2-WIKI-13: generación COMPUESTA de una Sugerencia (arraigo/iluminada). Tras un
    # análisis de intención (SuggestionIntentService), un solo job produce el MIX que el
    # plan pide: hojas/ramas/relaciones/hitos/ediciones. stage_results ya es agnóstico y
    # los estadía todos como Semillas revisables. NUNCA canoniza.
    SUGGEST_COMPOSITE = "suggest_composite"
    UNKNOWN = "unknown"


# BETA1-AI02: intents that return free text instead of staged candidates.
_TEXT_INTENTS: frozenset[AIJobType] = frozenset({AIJobType.IMPROVE_TEXT, AIJobType.GENERATE_TEXT})

# BETA2-WIKI-11 / limpieza post-épica (2026-07-21): tipos de job SIN superficie.
# Se conservan en el enum SOLO como centinelas de compatibilidad (AIJob.from_dict
# lanza ValueError con tipos desconocidos y REVIEW_GRAPH es el default persistido);
# toda su maquinaria (clasificador, matriz Acción×Ámbito, acciones contextuales,
# planner) se borró. Los VIVOS internos (usados por servicios sobrevivientes)
# NO están aquí: WATER_ENTITY, UPDATE_MEMORY, SUGGEST_RELATIONS, EDIT_ENTITIES,
# GENERATE_ENTITIES (estos tres los reusan las Sugerencias) y CHRONOLOGY_WALK_STEP.
_DEPRECATED_JOB_TYPES: frozenset[AIJobType] = frozenset(
    {
        AIJobType.GENERATE_TREE,
        AIJobType.ANALYZE_COHERENCE,
        AIJobType.REPAIR_COHERENCE,
        AIJobType.EXPAND_WORLDBUILDING,
        AIJobType.EXPLAIN_FROM_CAUSES,
        AIJobType.REVIEW_GRAPH,
        AIJobType.FREEFORM_PLANNING,
        AIJobType.PROPOSE_MILESTONES,
        AIJobType.CREATE_RING_TEMPLATE,
        AIJobType.EDIT_RELATION,
        AIJobType.EDIT_RING,
        AIJobType.EDIT_MILESTONE,
        AIJobType.IMPROVE_TEXT,
        AIJobType.GENERATE_TEXT,
    }
)


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
    if intent_type == AIJobType.CHRONOLOGY_WALK_STEP:
        return ["informe editorial", "candidatos", "propuestas de cambio", "preguntas abiertas"]
    if intent_type == AIJobType.WATER_ENTITY:
        return ["diagnóstico de riego persistente (sin candidatos ni cambios de canon)"]
    if intent_type == AIJobType.UPDATE_MEMORY:
        return ["Memoria editorial derivada (resumen, contradicciones, huecos; no canon)"]
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
    if intent_type == AIJobType.WATER_ENTITY:
        return "watering_diagnostic"
    if intent_type == AIJobType.UPDATE_MEMORY:
        return "memory_update"
    if intent_type == AIJobType.CHRONOLOGY_WALK_STEP:
        return "chronology_walk_step"
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
    # UX5b: una entidad/rama nueva nace en el anillo SELECCIONADO/enfocado si lo hay
    # (antes caía en `active_layer_ids`, el filtro visual, a menudo vacío → la entidad
    # quedaba sin anillo, «fuera de los definidos»).
    focused = context_scope.get("active_ring_id") or context_scope.get("focused_ring_id")
    if focused:
        return str(focused)
    layers = context_scope.get("active_layer_ids") or []
    if isinstance(layers, (list, tuple)) and layers:
        return str(layers[0])
    return ""


def _relation_body_meta(rel: dict[str, Any]) -> dict[str, Any]:
    """UX5g: el CUERPO de una relación se guarda en `custom_metadata["_body"]`
    (la clave que el panel de relación lee/escribe). Devuelve el fragmento de
    proposed_data con ese cuerpo, o vacío si el modelo no lo proporcionó.
    """
    if not isinstance(rel, dict):
        return {}
    body = str(rel.get("body") or rel.get("extended_description") or "").strip()
    return {"custom_metadata": {"_body": body}} if body else {}


def _selected_entity_ids(context_scope: dict[str, Any]) -> list[str]:
    value = context_scope.get("selected_entity_ids") or []
    return [str(item) for item in value if str(item)] if isinstance(value, (list, tuple)) else []


def _selected_relation_ids(context_scope: dict[str, Any]) -> list[str]:
    value = context_scope.get("selected_relation_ids") or []
    return [str(item) for item in value if str(item)] if isinstance(value, (list, tuple)) else []


def _active_ring_brief(project: Any, context_scope: dict[str, Any]) -> dict[str, Any]:
    """Resumen determinista del anillo activo/enfocado: nombre + descripción + dominio.

    UX5c: para que el modelo cree/edite entidades COHERENTES con el anillo seleccionado
    (p. ej. un anillo cosmológico ⇒ entidades cosmológicas, no mundanas). Antes solo
    viajaba el ID y el nombre del anillo, así que el modelo no sabía qué representa.
    """
    ring_id = str(
        context_scope.get("active_ring_id") or context_scope.get("focused_ring_id") or ""
    ).strip()
    if not ring_id or project is None:
        return {}
    layers = getattr(project, "world_layers", None) or []
    layer = next((wl for wl in layers if str(getattr(wl, "id", "")) == ring_id), None)
    if layer is None:
        return {}
    out: dict[str, Any] = {"id": ring_id, "name": str(getattr(layer, "name", "") or "")}
    desc = str(getattr(layer, "description", "") or "").strip()
    if desc:
        out["description"] = desc
    meta = getattr(layer, "metadata", {}) or {}
    domain = str(meta.get("domain") or "").strip() if isinstance(meta, dict) else ""
    if domain:
        out["domain"] = domain
    return out


def _selected_milestones_brief(
    project: Any, context_scope: dict[str, Any]
) -> list[dict[str, Any]]:
    """DC-UX4-HITO: datos vigentes de los hitos seleccionados (id+título+año+texto).

    La cronología vive FUERA de RAG, así que el hito objetivo no llega al modelo por
    recuperación. Sin sus datos actuales (sobre todo el `year`), el modelo no puede
    EDITAR el hito (p. ej. "adelanta un siglo" = year+100) y rechaza la edición.
    """
    ids = [str(x).strip() for x in (context_scope.get("selected_milestone_ids") or []) if str(x).strip()]
    if not ids or project is None:
        return []
    by_id = {str(getattr(m, "id", "")): m for m in (getattr(project, "causal_milestones", None) or [])}
    out: list[dict[str, Any]] = []
    for mid in ids:
        hito = by_id.get(mid)
        if hito is None:
            continue
        brief: dict[str, Any] = {"id": mid, "title": str(getattr(hito, "title", "") or "")}
        year = getattr(hito, "year", None)
        if year is not None:
            brief["year"] = year
        desc = str(getattr(hito, "description", "") or "").strip()
        if desc:
            brief["description"] = desc
        rationale = str(getattr(hito, "rationale", "") or "").strip()
        if rationale:
            brief["rationale"] = rationale
        out.append(brief)
    return out


def _compact_chronology(project: Any) -> dict[str, Any]:
    """Resumen compacto y determinista del calendario del proyecto (PA03).

    El calendario es config de proyecto: viaja determinista en el prompt, NO por
    RAG. Se incluye solo lo útil (nombre, descripción, era y fecha presente) sin
    el volcado masivo de meses/semanas/longitudes de era que era puro ruido.
    """
    chrono = getattr(project, "project_chronology", None) if project is not None else None
    if chrono is None:
        return {}
    out: dict[str, Any] = {}
    name = str(getattr(chrono, "calendar_name", "") or "").strip()
    if name:
        out["nombre"] = name
    desc = str(getattr(chrono, "description", "") or "").strip()
    if desc:
        out["descripcion"] = desc
    present_year = getattr(chrono, "present_year", 0) or 0
    try:
        era = chrono.era_for_year(present_year) if present_year else None
        if era is None and getattr(chrono, "eras", None):
            era = chrono.sorted_eras()[-1]
    except Exception:  # pragma: no cover - defensive
        era = None
    era_name = str(getattr(era, "name", "") or "").strip() if era is not None else ""
    if era_name:
        out["era_actual"] = era_name
    if present_year:
        out["anyo_presente"] = int(present_year)
    meta = getattr(chrono, "metadata", {}) or {}
    if isinstance(meta, dict):
        resolution = meta.get("date_resolution")
        if resolution:
            out["resolucion"] = resolution
        current = meta.get("current_date")
        if isinstance(current, dict) and current:
            out["fecha_actual"] = current
    return out


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


def _opt_year(value: Any) -> int | None:
    """BETA1-J05: año diegético entero (negativos válidos) o None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_VALID_NATURES = frozenset({"mortal", "inmortal", "eterno", "atemporal", "ciclico"})


def _opt_nature(value: Any) -> str:
    """BETA1-J07: naturaleza temporal saneada (default 'mortal')."""
    if isinstance(value, str) and value.strip().lower() in _VALID_NATURES:
        return value.strip().lower()
    return "mortal"


def _normalized_edit_fields(
    edit: dict[str, Any],
    whitelist: frozenset[str],
    aliases: dict[str, str],
    *,
    default_field: str = "",
) -> dict[str, Any]:
    """PLAY-15: extrae el patch {campo: valor} de una edición del modelo.

    Acepta ``edit_fields`` (dict multi-campo, formato nuevo) o el par escalar
    viejo ``field``/``proposed_value`` (envuelto como patch de un campo). Los
    campos fuera de la lista blanca se DESCARTAN aquí: visibilidad, secretos y
    estado de canon jamás llegan a candidato.
    """
    raw = edit.get("edit_fields")
    if not isinstance(raw, dict) or not raw:
        field = str(edit.get("field") or default_field).strip()
        value = edit.get("proposed_value")
        raw = {field: value} if field and str(value or "").strip() else {}
    fields: dict[str, Any] = {}
    for raw_key, value in raw.items():
        lowered = str(raw_key).strip().lower()
        key = aliases.get(lowered, lowered)
        if key not in whitelist:
            continue
        if value is None or not str(value).strip():
            continue
        fields[key] = value
    return fields


def _edit_fields_summary(fields: dict[str, Any]) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in fields.items())


def stage_results(model_payload: dict[str, Any], job: AIJob) -> dict[str, Any]:
    """Convert model payload to reviewable candidates/report. Never mutates canon."""
    payload = dict(model_payload or {})

    # UX8: una reparación de coherencia NO produce semillas/candidatos: devuelve un
    # plan de cambios concretos que el host revisa en un panel antes/después y aplica
    # explícitamente (acción humana). Se aísla de la maquinaria de candidatos.
    if job.type == AIJobType.REPAIR_COHERENCE:
        from packages.application.coherence_repair import normalize_repair_changes
        changes = normalize_repair_changes(payload.get("repair_changes"))
        return {
            "kind": "repair_plan",
            "summary": str(payload.get("summary") or f"{len(changes)} cambio(s) de reparación"),
            "report": str(payload.get("report") or ""),
            "repair_changes": changes,
            "candidates": [],
        }

    # BETA2-FOCO: el riego produce SOLO un diagnóstico persistente. Se valida aquí
    # (import lazy, patrón repair) porque la ruta principal llama al gateway con
    # validate=False (DC-AUDIT-02): la validación autoritativa es nuestra.
    if job.type == AIJobType.WATER_ENTITY:
        from packages.application.watering_payload import normalize_watering_payload

        normalized = normalize_watering_payload(payload)
        if isinstance(normalized, Error):
            return {
                "kind": "watering_diagnostic",
                "summary": "",
                "watering": None,
                "watering_error": normalized.error,
                "candidates": [],
            }
        data = normalized.value
        return {
            "kind": "watering_diagnostic",
            "summary": str(data.get("summary", "")),
            "watering": data,
            "candidates": [],
        }

    # BETA2-MEM-05: actualización de Memoria — secciones editoriales derivadas, no
    # canon. Validación autoritativa propia (mismo motivo: gateway con validate=False).
    if job.type == AIJobType.UPDATE_MEMORY:
        from packages.application.memory_payload import normalize_memory_payload

        normalized = normalize_memory_payload(payload)
        if isinstance(normalized, Error):
            return {
                "kind": "memory_update",
                "summary": "",
                "memory": None,
                "memory_error": normalized.error,
                "candidates": [],
            }
        data = normalized.value
        return {
            "kind": "memory_update",
            "summary": data.get("resumen_editorial", ""),
            "memory": data,
            "candidates": [],
        }

    # CRON: la AGRESIVIDAD del recorrido se ENFORZA aquí (determinista), no solo en
    # el prompt. Sin esto, el modelo podía proponer un HITO NUEVO en otro año en lugar
    # de EDITAR el hito actual (el bug del «hito duplicado en el año 86»).
    #   solo_senalar         → sin cambios estructurales (solo informe);
    #   sugerir_reparaciones → SOLO ediciones (nada de hitos/hojas/relaciones nuevas);
    #   sugerir_nuevas_piezas → todo permitido.
    if job.type == AIJobType.CHRONOLOGY_WALK_STEP:
        _aggr = str(
            ((job.context_scope.get("directivas") or {}).get("parametros") or {}).get(
                "agresividad"
            )
            or ""
        )
        if _aggr != "sugerir_nuevas_piezas":
            for _k in ("hitos", "milestones", "hojas", "entities", "relations", "rings", "anillos"):
                payload.pop(_k, None)
        if _aggr == "solo_senalar":
            for _k in ("entity_edits", "milestone_edits", "ring_edits", "relation_edits"):
                payload.pop(_k, None)

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
            # BETA1-J05: año diegético propuesto por la IA (None si lo desconoce).
            "year": _opt_year(milestone.get("year")),
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
            # UX5b: el cuerpo debe ir en `extended_description` — es la única clave que
            # NarrativeEntity.from_dict lee. En `body` se perdía (la entidad nacía vacía).
            "extended_description": str(
                entity.get("extended_description") or entity.get("body") or ""
            ).strip(),
            "layer_ids": layer_ids,
            "display_type": display_type,
            # BETA1-J05: datación propuesta por la IA (coherente con calendario/vecinos).
            "birth_year": _opt_year(entity.get("birth_year")),
            "death_year": _opt_year(entity.get("death_year")),
            # BETA1-J07: naturaleza temporal (eterno/inmortal/…) propuesta por la IA.
            "temporal_nature": _opt_nature(entity.get("temporal_nature")),
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
        # UX4 (C1/C2): una rama ES un contenedor. Forzamos entity_type="contenedor"
        # —lo que el render reconoce como árbol— y guardamos el tipo semántico del
        # modelo (religion/institucion/…) y el marcador de rama en custom_metadata,
        # que SÍ sobrevive a NarrativeEntity.from_dict (display_type en la raíz no).
        semantic_type = str(tree.get("entity_type") or "").strip()
        layer_ids = tree.get("layer_ids") if isinstance(tree.get("layer_ids"), list) else ([layer_id] if layer_id else [])
        meta = {
            "origin_prompt": job.prompt,
            "ai_job_id": job.id,
            "candidate_tree": True,
            "display_type": "rama",
        }
        if semantic_type:
            meta["semantic_type"] = semantic_type
        # UX5d: si el usuario SELECCIONÓ entidades al crear la rama, esas entidades
        # EXISTENTES son sus miembros (se enlazan con `contiene` al aceptar) y NO se
        # regeneran como hojas nuevas — antes el modelo las recreaba y la rama nacía
        # con duplicados. Sin selección, la rama nace con las hojas que proponga el
        # modelo. Las @menciones son referencias externas (viajan en `mentions`),
        # nunca miembros: no entran aquí.
        contained_entity_ids = list(selected_entity_ids)
        child_leaves = (
            [] if contained_entity_ids else _safe_list(tree.get("hojas") or tree.get("children"))
        )
        proposed = {
            "name": name,
            "entity_type": "contenedor",
            "brief_description": str(tree.get("brief_description") or tree.get("description") or "").strip(),
            # UX5b: el cuerpo de la rama también va a `extended_description` (no se pierde).
            "extended_description": str(
                tree.get("extended_description") or tree.get("body") or ""
            ).strip(),
            "layer_ids": layer_ids,
            "custom_metadata": meta,
            # BETA1-J05: datación de la rama propuesta por la IA.
            "birth_year": _opt_year(tree.get("birth_year")),
            "death_year": _opt_year(tree.get("death_year")),
            # BETA1-J07: naturaleza temporal de la rama.
            "temporal_nature": _opt_nature(tree.get("temporal_nature")),
            # UX4 (C4): hojas hijas NUEVAS declaradas por el modelo (solo si no hay
            # selección), para materializar la contención (`contiene`) al aceptar.
            "child_leaves": child_leaves,
            # UX5d: entidades EXISTENTES seleccionadas → miembros de la rama.
            "contained_entity_ids": contained_entity_ids,
        }
        candidates.append(_candidate(
            title=f"Rama candidata: {name}",
            candidate_type="entidad",
            proposed_data=proposed,
            job=job,
            justification=str(tree.get("rationale") or "Rama propuesta para revisión."),
        ))

    # BUG 4 fix + PLAY-15: stage entity edits as reviewable candidates. Acepta
    # AMBOS formatos del modelo — `edit_fields` (patch multi-campo, nuevo) y el
    # escalar viejo `field`/`proposed_value` (se envuelve como patch de 1 campo).
    # Los campos fuera de la lista blanca se descartan AQUÍ: visibilidad,
    # secretos y estado de canon jamás llegan a candidato.
    for edit in _safe_list(payload.get("entity_edits")):
        if not isinstance(edit, dict):
            continue
        entity_name = str(edit.get("entity_name") or "").strip()
        if not entity_name:
            continue
        fields = _normalized_edit_fields(
            edit, AI_EDITABLE_ENTITY_FIELDS, AI_ENTITY_FIELD_ALIASES, default_field="body"
        )
        if not fields:
            continue
        resumen = _edit_fields_summary(fields)
        campos = ", ".join(fields)
        candidates.append(_candidate(
            title=f"Editar {entity_name}: {campos}",
            candidate_type="sugerencia_ia",
            proposed_data={
                "report": f"Propuesta de edición para '{entity_name}':\n\n{resumen}",
                "edit_kind": "entity_edits",
                "edit_target_name": entity_name,
                "edit_fields": dict(fields),
                "issues": [],
                "proposals": [{"title": f"Editar {entity_name}", "description": resumen[:200]}],
                "open_questions": [],
                "prompt": job.prompt,
            },
            job=job,
            justification=str(
                edit.get("rationale") or "Edición propuesta para hoja o rama existente."
            ),
            confidence=0.65,
            expected_impact=f"Editar {len(fields)} campo(s) de '{entity_name}' tras revisión humana.",
        ))

    # UX5e: edición de RELACIÓN → UNA sola semilla con AMBOS campos (tipo + contenido).
    # El modelo puede emitir una entrada combinada {relation_type, description} o,
    # por compatibilidad, entradas por-campo {field, proposed_value}; en cualquier
    # caso se AGRUPAN por relación para no producir dos semillas (una del tipo y otra
    # del contenido), que era el bug reportado.
    rel_groups: dict[str, dict[str, str]] = {}
    rel_order: list[str] = []
    for edit in _safe_list(payload.get("relation_edits")):
        if not isinstance(edit, dict):
            continue
        target_name = str(edit.get("target_name") or edit.get("name") or "").strip()
        new_type = str(edit.get("relation_type") or "").strip()
        new_desc = str(edit.get("description") or "").strip()
        field = str(edit.get("field") or "").strip().lower()
        proposed_value = str(edit.get("proposed_value") or "").strip()
        if field == "relation_type" and proposed_value:
            new_type = new_type or proposed_value
        elif proposed_value and not new_desc:  # field == "description" o sin field
            new_desc = proposed_value
        if not (new_type or new_desc):
            continue
        key = target_name or "__seleccion__"
        if key not in rel_groups:
            rel_groups[key] = {"target_name": target_name, "relation_type": "",
                               "description": "", "rationale": ""}
            rel_order.append(key)
        grp = rel_groups[key]
        if new_type:
            grp["relation_type"] = new_type
        if new_desc:
            grp["description"] = new_desc
        if not grp["rationale"]:
            grp["rationale"] = str(edit.get("rationale") or "")

    for key in rel_order:
        grp = rel_groups[key]
        label_target = grp["target_name"] or "relación seleccionada"
        parts = []
        if grp["relation_type"]:
            parts.append(f"Tipo → {grp['relation_type']}")
        if grp["description"]:
            parts.append(f"Descripción → {grp['description']}")
        report_body = "\n".join(parts)
        candidates.append(_candidate(
            title=f"Editar relación: {label_target}",
            candidate_type="sugerencia_ia",
            proposed_data={
                "report": f"Propuesta de edición de relación '{label_target}':\n\n{report_body}",
                "edit_kind": "relation_edits",
                "edit_target_name": grp["target_name"],
                "edit_field": "description",
                # contenido (caja grande del panel) + tipo (campo aparte) en UNA semilla
                "edit_proposed_value": grp["description"],
                "edit_relation_type": grp["relation_type"],
                "issues": [],
                "proposals": [{"title": f"Editar relación: {label_target}",
                               "description": report_body[:200]}],
                "open_questions": [],
                "prompt": job.prompt,
            },
            job=job,
            justification=str(grp["rationale"]
                              or "Edición propuesta de la relación seleccionada."),
            confidence=0.65,
            expected_impact=f"Editar la relación '{label_target}' "
                            "(tipo y/o descripción) tras revisión humana.",
        ))

    # Structured edits for rings (deterministic "Editar" cells; mono-campo — los
    # anillos quedan fuera del alcance de PLAY-15). Cada uno stagea como
    # sugerencia_ia revisable; nunca canon.
    for edit in _safe_list(payload.get("ring_edits")):
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
            title=f"Editar {field} de anillo: {target_name}",
            candidate_type="sugerencia_ia",
            proposed_data={
                "report": f"Propuesta de edición de anillo '{target_name}':\n\n{proposed_value}",
                "edit_kind": "ring_edits",
                "edit_target_name": target_name,
                "edit_target_id": str(edit.get("target_id") or "").strip(),
                "edit_field": field,
                "edit_proposed_value": proposed_value,
                "issues": [],
                "proposals": [{"title": f"Editar {field} de {target_name}", "description": proposed_value[:200]}],
                "open_questions": [],
                "prompt": job.prompt,
            },
            job=job,
            justification=str(edit.get("rationale") or f"Edición propuesta de {field} para anillo existente."),
            confidence=0.65,
            expected_impact=f"Editar {field} de anillo '{target_name}' tras revisión humana.",
        ))

    # PLAY-15: milestone edits como patch multi-campo (con compat escalar). El
    # id estable (target_id) sobrevive a renombrados; la lista blanca filtra
    # aquí lo que la IA no puede tocar.
    for edit in _safe_list(payload.get("milestone_edits")):
        if not isinstance(edit, dict):
            continue
        target_name = str(
            edit.get("target_name") or edit.get("name") or edit.get("title") or ""
        ).strip()
        target_id = str(edit.get("target_id") or "").strip()
        fields = _normalized_edit_fields(
            edit,
            AI_EDITABLE_MILESTONE_FIELDS,
            AI_MILESTONE_FIELD_ALIASES,
            default_field="description",
        )
        if not fields or not (target_name or target_id):
            continue
        resumen = _edit_fields_summary(fields)
        campos = ", ".join(fields)
        candidates.append(_candidate(
            title=f"Editar hito {target_name or target_id}: {campos}",
            candidate_type="sugerencia_ia",
            proposed_data={
                "report": f"Propuesta de edición de hito '{target_name}':\n\n{resumen}",
                "edit_kind": "milestone_edits",
                "edit_target_name": target_name,
                # CRON: id estable del objetivo (renombrados no rompen ediciones).
                "edit_target_id": target_id,
                "edit_fields": dict(fields),
                "issues": [],
                "proposals": [{"title": f"Editar hito {target_name}", "description": resumen[:200]}],
                "open_questions": [],
                "prompt": job.prompt,
            },
            job=job,
            justification=str(edit.get("rationale") or "Edición propuesta para hito existente."),
            confidence=0.65,
            expected_impact=(
                f"Editar {len(fields)} campo(s) del hito '{target_name}' tras revisión humana."
            ),
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
    analytical = job.type in {AIJobType.ANALYZE_COHERENCE, AIJobType.REVIEW_GRAPH, AIJobType.EXPLAIN_FROM_CAUSES, AIJobType.FREEFORM_PLANNING, AIJobType.UNKNOWN, AIJobType.EDIT_ENTITIES, AIJobType.EDIT_RELATION, AIJobType.EDIT_RING, AIJobType.EDIT_MILESTONE, AIJobType.CHRONOLOGY_WALK_STEP}
    # BUG 1 fix: only add sugerencia_ia candidate for truly analytical jobs.
    # For generative jobs (entities/trees/relations), the structural candidates
    # are the real output; a synthetic "proposal" card is noise.
    def _is_actionable(cand: dict) -> bool:
        if cand.get("candidate_type") in ("entidad", "relacion"):
            return True
        pd = cand.get("proposed_data") or {}
        # UX4 (C5): ediciones y creaciones por ruta-segura también son accionables;
        # con ellas presentes NO añadimos el informe genérico (era ruido "nada").
        return bool(pd.get("edit_proposed_value")) or pd.get("kind") in (
            "ring_template", "causal_milestone", "project_chronology_suggestion",
        )

    has_structural_candidates = any(_is_actionable(c) for c in candidates)
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
    # UX4 (C6): en Crear Relación el plan ya fija el par exacto (fanout_pair). Usamos
    # esos ids reales en vez de fiarnos de los nombres que invente el modelo (que no
    # casaban con la selección → la aceptación fallaba). Una relación por par.
    fanout_pair = job.context_scope.get("fanout_pair")
    forced_pair = (
        [str(fanout_pair[0]), str(fanout_pair[1])]
        if isinstance(fanout_pair, (list, tuple)) and len(fanout_pair) == 2
        and str(fanout_pair[0]) and str(fanout_pair[1])
        else None
    )
    if forced_pair:
        first = next((r for r in relations_payload if isinstance(r, dict)), {})
        candidates.append(_candidate(
            title="Relación candidata",
            candidate_type="relacion",
            proposed_data={
                "source_id": forced_pair[0],
                "target_id": forced_pair[1],
                "relation_type": str(first.get("relation_type") or "esta_relacionado_con"),
                "description": str(first.get("description") or "Relación propuesta."),
                # UX5g: el CUERPO de la relación vive en custom_metadata["_body"] (la UI lo
                # lee/escribe ahí). Antes solo se rellenaba la descripción breve.
                **_relation_body_meta(first),
            },
            job=job,
            justification=str(first.get("rationale") or "Relación entre el par seleccionado."),
        ))
        relations_payload = []  # el par forzado ya cubre Crear Relación
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
                        **_relation_body_meta(rel),
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
                # BETA1-J05: datación del vínculo propuesta por la IA.
                "birth_year": _opt_year(rel.get("birth_year")),
                "death_year": _opt_year(rel.get("death_year")),
                **_relation_body_meta(rel),
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


def _b40_prompt_profile(context: dict[str, Any]) -> dict[str, Any]:
    """Instrucciones de comportamiento para el modelo (PA04).

    El comportamiento del asistente (rol, nº de opciones, etc.) son constantes
    fijas (``ai_defaults``), ya no config de proyecto. Las reglas duras y el
    espacio negativo se leen de ``creative_brief.reglas`` (modelo canónico).
    """
    from packages.domain import ai_defaults as aidef

    brief = (context or {}).get("creative_brief") or {}
    if not isinstance(brief, dict):
        brief = {}
    reglas = brief.get("reglas") if isinstance(brief.get("reglas"), dict) else {}
    return {
        "role": aidef.DEFAULT_ROLE,
        "strategy": aidef.DEFAULT_STRATEGY,
        "output_mode": aidef.DEFAULT_OUTPUT_MODE,
        "default_num_options": aidef.DEFAULT_NUM_OPTIONS,
        "change_aggressiveness": aidef.DEFAULT_CHANGE_AGGRESSIVENESS,
        "uncertainty_policy": aidef.DEFAULT_UNCERTAINTY_POLICY,
        "context_depth": aidef.DEFAULT_CONTEXT_DEPTH,
        "reglas_canon": reglas.get("reglas_canon", []),
        "evitar": reglas.get("evitar", []),
        "instructions": [
            "Respeta reglas.reglas_canon (canon duro); si el usuario pide algo incompatible, "
            "proponlo como problema/reparación, no como canon.",
            "Evita lo listado en reglas.evitar (tropos, soluciones, tonos, frases, tics).",
            "Toda salida estructural debe ser candidato revisable; nunca asumas canon automático.",
        ],
    }


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
        # El worker (execute_job) y el hilo UI (cancel_job/update_status) mutan
        # los mismos AIJob: todas las transiciones de estado pasan por este lock.
        self._state_lock = threading.RLock()
        self._provider = provider if provider is not None else resolve_provider()
        # BETA1-AI02: single provider chokepoint. Every model call goes through
        # the gateway (sanitize → params → dispatch). Injectable for tests.
        self._gateway = gateway if gateway is not None else AIRequestGateway(provider=self._provider)
        self.allow_simulated = allow_simulated
        self.observability_log = observability_log or AIObservabilityLog()
        self.timeout_seconds = max(1, int(timeout_seconds or DEFAULT_AI_TIMEOUT_SECONDS))
        self._rag_service = rag_service
        self._project_provider = project_provider
        self._prompt_trace_store = prompt_trace_store
        # Presupuesto de contexto por tier (entrada/salida) según el intent.
        self._budget = ContextBudgetManager()

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

    def _resolve_intent(
        self,
        resolved_type: AIJobType,
        prompt: str,
        context: dict[str, Any],
        *,
        explicit: bool,
    ) -> "CommandBarIntent":
        """Resuelve el intent de un job (explícito = autoritativo; si no, clasifica).

        Única fuente compartida por ``create_job`` y ``preview_context`` para que
        la vista previa use exactamente el mismo intent que el job real.
        """
        if explicit:
            # BETA1-AI02: focused job — the caller's intent is authoritative, so
            # skip prompt classification and run this exact task type.
            return CommandBarIntent(
                intent_type=resolved_type,
                confidence=1.0,
                target_scope=_scope_from_context(_norm(prompt), context),
                expected_output_type=_expected_output_for_intent(resolved_type),
                rationale="Acción enfocada (intent explícito).",
                planner_source="explicit",
            )
        # Sin intent explícito: el tipo resuelto manda tal cual (el clasificador
        # heurístico por keywords se retiró en la limpieza post-WIKI).
        return CommandBarIntent(
            intent_type=resolved_type,
            confidence=1.0,
            target_scope=_scope_from_context(_norm(prompt), context),
            expected_output_type=_expected_output_for_intent(resolved_type),
            rationale="Intent tomado del tipo del job (clasificador retirado).",
            planner_source="job_type",
        )

    def preview_context(
        self,
        job_type: AIJobType | str,
        prompt: str,
        *,
        context_scope: dict[str, Any] | None = None,
        explicit: bool = True,
    ) -> Result:
        """UX3: calcula el contexto que se enviaría SIN crear ni ejecutar un job.

        Reproduce el pipeline real (intent → plan → RAG → ensamblado) sobre un
        ``AIJob`` efímero que NO se guarda en ``self._jobs`` (no aparece en Tareas),
        y devuelve una estructura legible para la vista previa. Las exclusiones que
        el usuario marque viajan luego en ``context_scope['preview_exclusions']`` y
        las aplica el propio ``PromptAssembler`` tanto aquí como al ejecutar.
        """
        prompt = (prompt or "").strip()
        if not prompt:
            return Error("El prompt no puede estar vacío")
        context = dict(context_scope or {})
        try:
            resolved_type = job_type if isinstance(job_type, AIJobType) else AIJobType(str(job_type))
        except ValueError:
            resolved_type = AIJobType.REVIEW_GRAPH
        intent = self._resolve_intent(resolved_type, prompt, context, explicit=explicit)
        job = AIJob(
            type=intent.intent_type,
            explicit_intent=resolved_type if explicit else None,
            prompt=prompt,
            context_scope=context,
            intent=intent.to_dict(),
        )  # efímero: NO se registra en self._jobs
        plan = build_job_plan(intent, prompt, context, job_id=job.id)
        plan = self._with_rag_context(job, plan)
        raw = PromptAssembler(self._budget).preview(plan)
        return Ok(build_context_preview(raw))

    def create_job(self, job_type: AIJobType | str, prompt: str, *, context_scope: dict[str, Any] | None = None, explicit: bool = False) -> Result:
        prompt = (prompt or "").strip()
        if not prompt:
            return Error("El prompt no puede estar vacío")
        context = dict(context_scope or {})
        try:
            resolved_type = job_type if isinstance(job_type, AIJobType) else AIJobType(str(job_type))
        except ValueError:
            resolved_type = AIJobType.REVIEW_GRAPH
        intent = self._resolve_intent(resolved_type, prompt, context, explicit=explicit)
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
        with self._state_lock:
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

    def provider_unconfigured(self) -> bool:
        """True si no hay un proveedor IA real (solo el simulado, no permitido).
        La UI lo usa para mostrar instrucciones de configuración accionables."""
        provider_name = str(getattr(self._provider, "provider_name", "ai"))
        return provider_name == "simulated" and not self.allow_simulated

    def raw_json_completion(
        self, system_prompt: str, user_message: str
    ) -> tuple[str | None, str | None]:
        """Una llamada single-shot JSON al proveedor, devolviendo ``(texto, error)``.

        BETA2-WIKI: la mantiene el AIJobService (borde IA autorizado a tocar el proveedor)
        para que servicios de aplicación como ``WikiNavigator``/``WikiLintService`` NO
        importen infraestructura. Tolera firmas de ``chat`` más estrechas (provider_chat).
        """
        return provider_chat(
            self._provider, system_prompt, user_message, json_mode=True,
            timeout=self.timeout_seconds,
        )

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
        with self._state_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return Error("Job IA no encontrado")
            try:
                new_status = status if isinstance(status, AIJobStatus) else AIJobStatus(str(status))
            except ValueError:
                return Error("Estado de job IA no válido")
            # Cancelado gana: un worker que termina tarde no puede resucitar el
            # job pisando CANCELLED con FAILED/READY_FOR_REVIEW.
            if job.status == AIJobStatus.CANCELLED and new_status != AIJobStatus.CANCELLED:
                return Error("Job IA cancelado")
            job.status = new_status
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

        # Sin intent explícito: el job conserva su tipo tal cual. El clasificador
        # heurístico por keywords se retiró en la limpieza post-WIKI (toda la
        # superficie viva crea jobs con intent explícito).
        intent = CommandBarIntent(
            intent_type=job.type,
            confidence=1.0,
            target_scope=_scope_from_context(_norm(job.prompt), job.context_scope),
            expected_output_type=_expected_output_for_intent(job.type),
            rationale="Intent tomado del tipo del job (clasificador retirado).",
            planner_source="job_type",
        )
        return Ok((intent, build_job_plan(intent, job.prompt, job.context_scope, job_id=job.id)))

    def _with_rag_context(self, job: AIJob, plan: AIJobPlan) -> AIJobPlan:
        """Inyecta el contexto determinista del proyecto en el plan (BETA2-WIKI-05).

        Ya NO recupera por RAG léxico ni vuelca la Memoria fija: el contexto relevante
        lo decide la IA navegando la wiki (``WikiNavigator``), y el consumidor lo pasa
        en ``context_scope['contexto_wiki']`` (que el ensamblador renderiza). Aquí solo
        se añade lo determinista que no viaja por la wiki: cronología compacta, anillo
        activo y hito(s) seleccionado(s). Sin ``_project_provider`` es un no-op.
        """
        if self._project_provider is None:
            return plan
        try:
            project = self._project_provider()
        except Exception:  # pragma: no cover - defensive UI boundary
            return plan
        if project is None:
            return plan

        context = dict(plan.context)

        # Cronología compacta determinista (el calendario nunca viajó por recuperación).
        cronologia = _compact_chronology(project)
        if cronologia:
            context["cronologia"] = cronologia

        # UX5c: el anillo activo viaja con su descripción y dominio (no solo el id/nombre)
        # para que la creación/edición sea coherente con la naturaleza del anillo.
        ring_brief = _active_ring_brief(project, context)
        if ring_brief:
            context["active_ring"] = ring_brief

        # DC-UX4-HITO: el/los hito(s) seleccionado(s) viajan con sus datos vigentes
        # (título, año, texto) para que `editar:hito` pueda EDITARLOS de verdad.
        milestones_brief = _selected_milestones_brief(project, context)
        if milestones_brief:
            context["selected_milestones"] = milestones_brief

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
            msg = (
                "IA no configurada: añade un proveedor en Ajustes de IA (en la CLI: "
                "variables NARRATIVE_AI_PROVIDER, NARRATIVE_AI_BASE_URL, NARRATIVE_AI_API_KEY "
                "y NARRATIVE_AI_MODEL). No se genera contenido simulado."
            )
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

        model_user_message, budget_warnings = build_model_user_message_with_warnings(plan)
        # fila 34: si el presupuesto recortó secciones (canon/candidatos/imports…),
        # anexamos el aviso al rag_context_pack (mismo canal que ya muestra la UI; el
        # context es copia shallow en job.plan, así que comparte este dict).
        if budget_warnings and isinstance(plan.context.get("rag_context_pack"), dict):
            pack = plan.context["rag_context_pack"]
            pack["warnings"] = list(pack.get("warnings") or []) + budget_warnings
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
        # Output budget por tier del intent; el override del tuner de UI gana.
        max_tokens = tokens_override or self._budget.output_budget(plan.intent.intent_type)
        try:
            gw = self._gateway.execute(GatewayRequest(
                intent=plan.intent.intent_type.value,
                user_prompt=model_user_message,
                system_prompt_override=system_prompt,
                timeout=self.timeout_seconds,
                json_mode=not is_text,
                validate=False,
                temperature=temp_override,
                max_tokens=max_tokens,
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
        with self._state_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return Error("Job IA no encontrado")
            if job.status == AIJobStatus.CANCELLED:
                job.message = "Job cancelado"
                job.updated_at = _now_iso()
                return Error("Job IA cancelado")
            return None

    def cancel_job(self, job_id: str) -> Result:
        with self._state_lock:
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
    # Otros formatos de credencial que un endpoint puede reflejar en su cuerpo
    # de error (el detalle HTTP adjunta hasta 500 chars crudos): claves Google
    # (AIza...), GitHub (ghp_/gho_...), y pares api_key/token/secret=valor.
    text = re.sub(r"AIza[A-Za-z0-9._\-]{10,}", "[REDACTED]", text)
    text = re.sub(r"gh[pousr]_[A-Za-z0-9]{20,}", "[REDACTED]", text)
    text = re.sub(r"Basic\s+[A-Za-z0-9+/=._\-]+", "Basic [REDACTED]", text)
    text = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?token|secret|authorization|x-api-key)\b"
        r"(\W{0,4})[A-Za-z0-9+/=._\-]{4,}",
        r"\1\2[REDACTED]",
        text,
    )
    return text[:500]
