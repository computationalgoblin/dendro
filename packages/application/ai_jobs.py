"""B38 AI command-bar jobs.

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
from typing import Any
import json
import re
import uuid

from packages.domain.result import Error, Ok, Result
from packages.infrastructure.ai_provider import AIProvider, SimulatedAIProvider, create_provider


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


COMMAND_BAR_SYSTEM_PROMPT_ES = """Eres el planificador y asistente central de creación de Dendro. Tu tarea es interpretar la petición del usuario y producir un plan o resultado útil sobre el grafo narrativo. Debes respetar el prompt exacto del usuario, el idioma del proyecto, el género, tono, realismo, estilo narrativo, worldbuilding activo, capas, árboles, relaciones y canon existente. No debes modificar canon directamente. Si generas nuevos elementos, deben ser candidatos revisables. Si analizas el grafo, devuelve un informe estructurado. Si la petición es ambigua, propón una interpretación y pide confirmación o crea un plan revisable. No devuelvas plantillas fijas. No ignores detalles del prompt.

Si el usuario pide EDITAR o RELLENAR el cuerpo/historia/motivaciones de entidades EXISTENTES, NO crees entidades nuevas. En vez de eso, devuelve un objeto "entity_edits" con propuestas de edición para cada entidad existente identificada. Formato:
"entity_edits": [{"entity_name": "nombre exacto de la entidad existente", "field": "body", "proposed_value": "texto propuesto para el cuerpo", "rationale": "por qué este cambio"}]

Devuelve SOLO JSON válido con esta forma:
{
  "summary": "resumen humano breve",
  "report": "informe o explicación visible para el usuario",
  "entities": [{"name": "...", "entity_type": "personaje|localizacion|objeto|evento|faccion|contenedor|ley|nota", "brief_description": "...", "body": "... opcional", "layer_ids": []}],
  "trees": [{"name": "...", "brief_description": "...", "layer_ids": []}],
  "relations": [{"source_name": "nombre de la entidad origen", "target_name": "nombre de la entidad destino", "source_id": "id real si se conoce", "target_id": "id real si se conoce", "relation_type": "esta_relacionado_con", "description": "..."}],
  "entity_edits": [{"entity_name": "...", "field": "body|brief_description", "proposed_value": "...", "rationale": "..."}],
  "issues": [{"title": "...", "description": "...", "severity": "baja|media|alta"}],
  "proposals": [{"title": "...", "description": "..."}],
  "open_questions": ["..."]
}
No incluyas IDs inventados. Si no conoces endpoints reales para relaciones, usa source_name/target_name sin IDs y escribe propuestas en 'proposals' u 'open_questions'. Para relaciones entre entidades generadas en la misma respuesta, usa source_name/target_name.
"""


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
    UNKNOWN = "unknown"


@dataclass
class CommandBarIntent:
    intent_type: AIJobType
    confidence: float
    target_scope: str
    expected_output_type: str
    needs_confirmation: bool = False
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
            "target_scope": self.target_scope,
            "expected_output_type": self.expected_output_type,
            "needs_confirmation": self.needs_confirmation,
            "rationale": self.rationale,
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
        return cls(
            id=data.get("id") or f"job_{uuid.uuid4().hex[:10]}",
            type=AIJobType(data.get("type") or AIJobType.REVIEW_GRAPH.value),
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
    """Classify command-bar intent without generating final content."""
    context = dict(context or {})
    text = _norm(prompt)
    worldbuilding = bool(context.get("worldbuilding_active", False))
    scope = _scope_from_context(text, context)

    if not text:
        return CommandBarIntent(AIJobType.UNKNOWN, 0.0, scope, "none", True, "Prompt vacío")

    # BUG 4 fix: detect edit/body fill intent before generation
    if _has_any(text, ["rellena", "rellenar", "completa", "completar", "cuerpo", "historia", "motivación", "motivaciones", "descripción", "desarrolla", "desarrollar", "expande", "expandir", "editar", "modifica", "modificar"]) and _has_any(text, ["entidad", "entidades", "existente", "existentes", "creada", "creadas", "nodo", "nodos", "personaje", "personajes"]):
        return CommandBarIntent(AIJobType.EDIT_ENTITIES, 0.80, scope, "edit_candidates", False, "La petición pide editar/rellenar entidades existentes, no crear nuevas")

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

    if _has_any(text, ["sistema", "árbol", "arbol", "estructura"]):
        return CommandBarIntent(AIJobType.GENERATE_TREE, 0.72, scope, "tree_candidates", False, "La petición pide sistema/árbol/estructura")

    if _has_any(text, ["personaje", "personajes", "entidad", "entidades", "nodo", "nodos", "científico", "cientific", "herman"]):
        return CommandBarIntent(AIJobType.GENERATE_ENTITIES, 0.78, scope, "entity_candidates", False, "La petición pide entidades/personajes")

    if _has_any(text, ["plan", "idea", "organiza", "ayúdame", "ayudame"]):
        return CommandBarIntent(AIJobType.FREEFORM_PLANNING, 0.55, scope, "plan_report", False, "Petición abierta de planificación")

    return CommandBarIntent(AIJobType.UNKNOWN, 0.35, scope, "clarification_or_plan", True, "No hay intención clara")


def classify_ai_job_intent(prompt: str, *, worldbuilding_active: bool = False) -> AIJobType:
    """Backward-compatible wrapper returning only the job type."""
    return classify_intent(prompt, {"worldbuilding_active": worldbuilding_active}).intent_type


def _creates_for_intent(intent_type: AIJobType) -> list[str]:
    if intent_type == AIJobType.GENERATE_ENTITIES:
        return ["candidatos de entidad"]
    if intent_type == AIJobType.GENERATE_TREE:
        return ["candidato de árbol", "candidatos de nodos internos opcionales"]
    if intent_type == AIJobType.SUGGEST_RELATIONS:
        return ["candidatos de relación"]
    if intent_type in (AIJobType.ANALYZE_COHERENCE, AIJobType.REVIEW_GRAPH, AIJobType.EXPLAIN_FROM_CAUSES):
        return ["informe", "propuestas", "preguntas abiertas"]
    if intent_type == AIJobType.EXPAND_WORLDBUILDING:
        return ["candidatos de nodo/árbol", "relaciones causales candidatas"]
    if intent_type == AIJobType.EDIT_ENTITIES:
        return ["candidatos de edición de cuerpo/campos de entidades existentes"]
    return ["plan revisable"]


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


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"report": raw}
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {"report": raw}
        except Exception:
            pass
    return {"summary": "Respuesta no estructurada", "report": raw}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stage_results(model_payload: dict[str, Any], job: AIJob) -> dict[str, Any]:
    """Convert model payload to reviewable candidates/report. Never mutates canon."""
    payload = dict(model_payload or {})
    layer_id = _first_active_layer(job.context_scope)
    candidates: list[dict[str, Any]] = []

    for entity in _safe_list(payload.get("entities")):
        if not isinstance(entity, dict):
            continue
        name = str(entity.get("name") or "Entidad propuesta").strip()
        if not name:
            continue
        layer_ids = entity.get("layer_ids") if isinstance(entity.get("layer_ids"), list) else ([layer_id] if layer_id else [])
        proposed = {
            "name": name,
            "entity_type": str(entity.get("entity_type") or "personaje"),
            "brief_description": str(entity.get("brief_description") or entity.get("description") or "").strip(),
            "body": str(entity.get("body") or "").strip(),
            "layer_ids": layer_ids,
            "custom_metadata": {"origin_prompt": job.prompt, "ai_job_id": job.id},
        }
        candidates.append(_candidate(
            title=f"Entidad candidata: {name}",
            candidate_type="entidad",
            proposed_data=proposed,
            job=job,
            justification=str(entity.get("rationale") or "Propuesta generada desde el prompt exacto del usuario."),
        ))

    for tree in _safe_list(payload.get("trees")):
        if not isinstance(tree, dict):
            continue
        name = str(tree.get("name") or "Árbol propuesto").strip()
        layer_ids = tree.get("layer_ids") if isinstance(tree.get("layer_ids"), list) else ([layer_id] if layer_id else [])
        proposed = {
            "name": name,
            "entity_type": "contenedor",
            "brief_description": str(tree.get("brief_description") or tree.get("description") or "").strip(),
            "layer_ids": layer_ids,
            "custom_metadata": {"origin_prompt": job.prompt, "ai_job_id": job.id, "candidate_tree": True},
        }
        candidates.append(_candidate(
            title=f"Árbol candidato: {name}",
            candidate_type="entidad",
            proposed_data=proposed,
            job=job,
            justification=str(tree.get("rationale") or "Árbol/contenedor propuesto para revisión."),
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
            justification=str(edit.get("rationale") or f"Edición propuesta de {field} para entidad existente."),
            confidence=0.65,
            expected_impact=f"Editar {field} de '{entity_name}' tras revisión humana.",
        ))

    selected = set(str(x) for x in (job.context_scope.get("selected_entity_ids") or []))
    relevant = job.context_scope.get("relevant_entities") or []
    relevant_ids = {str(e.get("id")) for e in relevant if isinstance(e, dict) and e.get("id")}
    allowed_ids = selected | relevant_ids
    for rel in _safe_list(payload.get("relations")):
        if not isinstance(rel, dict):
            continue
        source_id = str(rel.get("source_id") or "")
        target_id = str(rel.get("target_id") or "")
        if not source_id or not target_id:
            continue
        if allowed_ids and (source_id not in allowed_ids or target_id not in allowed_ids):
            continue
        candidates.append(_candidate(
            title="Relación candidata",
            candidate_type="relacion",
            proposed_data={
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": str(rel.get("relation_type") or "esta_relacionado_con"),
                "description": str(rel.get("description") or "Relación propuesta desde command bar."),
            },
            job=job,
            justification=str(rel.get("rationale") or "Relación propuesta con endpoints reales del contexto."),
        ))

    report = str(payload.get("report") or payload.get("summary") or "Resultado IA listo para revisión.")
    analytical = job.type in {AIJobType.ANALYZE_COHERENCE, AIJobType.REVIEW_GRAPH, AIJobType.EXPLAIN_FROM_CAUSES, AIJobType.FREEFORM_PLANNING, AIJobType.UNKNOWN, AIJobType.EDIT_ENTITIES}
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

    # BUG 2 fix: for generative jobs with relations from the model that lack
    # real IDs, convert them to proposals instead of silently dropping them.
    # The model may return proposed relation *names* that need manual wiring.
    for rel in _safe_list(payload.get("relations")):
        if not isinstance(rel, dict):
            continue
        source_id = str(rel.get("source_id") or "")
        target_id = str(rel.get("target_id") or "")
        if not source_id or not target_id:
            # Convert to a human-readable proposal
            desc = str(rel.get("description") or "Relación propuesta.")
            source_name = str(rel.get("source_name") or source_id or "?")
            target_name = str(rel.get("target_name") or target_id or "?")
            rel_type = str(rel.get("relation_type") or "esta_relacionado_con")
            candidates.append(_candidate(
                title=f"Relación propuesta: {source_name} → {target_name}",
                candidate_type="sugerencia_ia",
                proposed_data={
                    "report": f"Relación propuesta: {source_name} ({rel_type}) → {target_name}. {desc}",
                    "issues": [],
                    "proposals": [{"title": f"{source_name} → {target_name}", "description": desc, "relation_type": rel_type}],
                    "open_questions": [f"¿Existen {source_name} y {target_name} como entidades reales para crear esta relación?"],
                    "prompt": job.prompt,
                },
                job=job,
                justification="La IA propuso una relación pero no tiene IDs reales de endpoints. Revisión manual necesaria.",
                confidence=0.40,
                expected_impact="Propuesta de relación para conexión manual.",
            ))
            continue
        if allowed_ids and (source_id not in allowed_ids or target_id not in allowed_ids):
            # Already handled above; don't double-process
            continue

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


def build_model_user_message(plan: AIJobPlan) -> str:
    return json.dumps({
        "prompt_exacto_usuario": plan.prompt,
        "intent": plan.intent.to_dict(),
        "plan": plan.to_dict(),
        "contexto_autorizado": _context_for_prompt(plan.context),
        "restricciones": {
            "no_canon_automatico": True,
            "solo_candidatos_revisables": True,
            "no_ids_inventados": True,
            "usar_prompt_exacto_como_instruccion_principal": True,
        },
    }, ensure_ascii=False, indent=2)


# Backward-compatible helper kept only for tests that inject explicit mock jobs.
def build_ai_job_result(job: AIJob, provider: AIProvider | None = None, *, allow_simulated: bool = True) -> dict[str, Any]:
    service = AIJobService(provider=provider or SimulatedAIProvider(), allow_simulated=allow_simulated)
    service._jobs[job.id] = job
    result = service.execute_job(job.id)
    if isinstance(result, Error):
        raise RuntimeError(result.error)
    return result.value.result


class AIJobService:
    """In-memory AI job registry and command-bar runner."""

    def __init__(self, provider: AIProvider | None = None, *, allow_simulated: bool = False):
        self._jobs: dict[str, AIJob] = {}
        self._provider = provider if provider is not None else create_provider()
        self.allow_simulated = allow_simulated

    def create_job(self, job_type: AIJobType | str, prompt: str, *, context_scope: dict[str, Any] | None = None) -> Result:
        prompt = (prompt or "").strip()
        if not prompt:
            return Error("El prompt no puede estar vacío")
        context = dict(context_scope or {})
        try:
            resolved_type = job_type if isinstance(job_type, AIJobType) else AIJobType(str(job_type))
        except ValueError:
            resolved_type = AIJobType.REVIEW_GRAPH
        intent = classify_intent(prompt, context)
        if resolved_type not in (AIJobType.UNKNOWN, intent.intent_type):
            # UI may pass a legacy heuristic type; keep explicit type but preserve classifier rationale.
            intent.intent_type = resolved_type
        job = AIJob(
            type=intent.intent_type,
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

    def execute_job(self, job_id: str, progress_callback=None) -> Result:
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
        job.type = intent.intent_type
        job.plan = plan.to_dict()
        self.update_status(job_id, AIJobStatus.WAITING_FOR_MODEL, message="Consultando IA…", progress=0.60)
        if progress_callback:
            progress_callback(job)
        try:
            text, error = self._provider.chat(COMMAND_BAR_SYSTEM_PROMPT_ES, build_model_user_message(plan))
        except Exception as exc:
            text, error = None, str(exc)
        if error:
            safe = _sanitize_error(error)
            self.update_status(job_id, AIJobStatus.FAILED, message="Job fallido", error=safe, progress=1.0)
            return Error(safe)
        if not text:
            msg = "El proveedor IA no devolvió contenido."
            self.update_status(job_id, AIJobStatus.FAILED, message="Job fallido", error=msg, progress=1.0)
            return Error(msg)
        self.update_status(job_id, AIJobStatus.POSTPROCESSING, message="Preparando candidatos…", progress=0.80)
        if progress_callback:
            progress_callback(job)
        payload = _extract_json(text)
        result = stage_results(payload, job)
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
