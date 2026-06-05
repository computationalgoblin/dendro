"""B38 AI job contract and in-memory service.

AI jobs are the command-bar unit of work.  They never mutate canon directly;
results become reviewable candidates/suggestions; they never mutate canon directly.

MVP persistence decision: in-memory only.  This avoids schema churn for B38-T04
and keeps job runtime state out of project canon.  Durable job persistence can be
added later if long-running/background jobs need to survive app restarts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from packages.domain.result import Error, Ok, Result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AIJobStatus(str, Enum):
    QUEUED = "queued"
    BUILDING_CONTEXT = "building_context"
    RUNNING = "running"
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
        },
    }


def build_ai_job_result(job: AIJob) -> dict[str, Any]:
    """Build deterministic MVP output for a job without calling an external model.

    B38-T08 intentionally starts with useful offline candidates/reports.  Later
    blocks can replace this with provider-backed structured output behind the
    same job/result contract.
    """
    prompt = job.prompt.strip()
    layer_id = _first_active_layer(job.context_scope)
    base_meta = {"origin_prompt": prompt, "layer_ids": [layer_id] if layer_id else []}

    if job.type == AIJobType.GENERATE_ENTITIES:
        candidates = [
            _candidate(
                title="Mara, cartógrafa exiliada",
                candidate_type="entidad",
                proposed_data={
                    "name": "Mara",
                    "entity_type": "personaje",
                    "brief_description": "Cartógrafa exiliada que conoce rutas prohibidas y conserva mapas incompletos.",
                    "layer_ids": [layer_id] if layer_id else [],
                    "custom_metadata": {**base_meta, "role": "personaje_inicial"},
                },
                job=job,
                justification="Personaje inicial con movilidad narrativa y secretos explorables.",
            ),
            _candidate(
                title="Iren, heredero de una casa menor",
                candidate_type="entidad",
                proposed_data={
                    "name": "Iren",
                    "entity_type": "personaje",
                    "brief_description": "Heredero de una casa menor que busca legitimidad sin poder suficiente para imponerla.",
                    "layer_ids": [layer_id] if layer_id else [],
                    "custom_metadata": {**base_meta, "role": "tension_social"},
                },
                job=job,
                justification="Introduce conflicto de estatus y alianzas frágiles.",
            ),
            _candidate(
                title="Vosco, sacerdote de la caída",
                candidate_type="entidad",
                proposed_data={
                    "name": "Vosco",
                    "entity_type": "personaje",
                    "brief_description": "Sacerdote que interpreta cada derrumbe como una señal de equilibrio divino.",
                    "layer_ids": [layer_id] if layer_id else [],
                    "custom_metadata": {**base_meta, "role": "voz_ideologica"},
                },
                job=job,
                justification="Conecta personaje con mito, culto y consecuencias culturales.",
            ),
        ]
        return {
            "kind": "candidate_batch",
            "summary": "3 candidatos de personaje listos para revisión.",
            "candidates": candidates,
            "report": "Se proponen tres personajes complementarios. Ninguno se crea hasta aceptar su candidato.",
        }

    if job.type in (AIJobType.GENERATE_TREE, AIJobType.EXPAND_WORLDBUILDING):
        title = "Sistema metafísico: conflicto gravitacional"
        candidates = [
            _candidate(
                title=title,
                candidate_type="entidad",
                proposed_data={
                    "name": "Sistema metafísico del conflicto gravitacional",
                    "entity_type": "contenedor",
                    "brief_description": "Árbol candidato para organizar causas primeras, leyes y consecuencias del mundo.",
                    "layer_ids": [layer_id] if layer_id else [],
                    "custom_metadata": {**base_meta, "tree_type": "sistema_metafisico", "candidate_tree": True},
                },
                job=job,
                justification="Crea un contenedor revisable para ordenar causalmente el worldbuilding.",
                expected_impact="Al aceptar, se crea solo el contenedor; nodos internos futuros siguen siendo candidatos separados.",
            ),
            _candidate(
                title="Ley candidata: toda gravedad expresa conflicto",
                candidate_type="entidad",
                proposed_data={
                    "name": "Toda gravedad expresa conflicto",
                    "entity_type": "ley",
                    "brief_description": "La atracción entre cuerpos no es neutra: manifiesta tensiones entre fuerzas superiores.",
                    "layer_ids": [layer_id] if layer_id else [],
                    "custom_metadata": {**base_meta, "causal_candidate": True},
                },
                job=job,
                justification="Da una regla concreta desde la que derivar naturaleza, cultura y conflicto.",
            ),
        ]
        return {
            "kind": "candidate_batch",
            "summary": "Sistema/árbol candidato y ley inicial listos para revisión.",
            "candidates": candidates,
            "report": "El sistema se entrega como candidatos revisables; no se crean árboles/nodos automáticamente.",
        }

    if job.type in (AIJobType.ANALYZE_COHERENCE, AIJobType.REVIEW_GRAPH):
        selected = job.context_scope.get("selected_entity_ids") or []
        scope = "selección actual" if selected else "grafo visible/proyecto"
        report = (
            f"Revisión MVP sobre {scope}:\n"
            "1. Buscar elementos sin causa superior clara si Worldbuilding está activo.\n"
            "2. Revisar relaciones contradictorias o sin justificación visible.\n"
            "3. Convertir propuestas de reparación en candidatos antes de canonizar."
        )
        candidates = [
            _candidate(
                title="Informe revisable de coherencia",
                candidate_type="sugerencia_ia",
                proposed_data={
                    "report": report,
                    "prompt": prompt,
                    "scope": dict(job.context_scope),
                },
                job=job,
                justification="Informe analítico generado por job; aceptar solo registra la sugerencia, no modifica el grafo.",
                confidence=0.55,
                expected_impact="Ayuda a decidir mejoras sin aplicar cambios automáticos.",
            )
        ]
        return {
            "kind": "analysis_report",
            "summary": "Informe de revisión listo.",
            "report": report,
            "candidates": candidates,
        }

    if job.type == AIJobType.SUGGEST_RELATIONS:
        selected = list(job.context_scope.get("selected_entity_ids") or [])
        report = "Selecciona al menos dos nodos para convertir sugerencias de relación en candidatos con endpoints reales."
        candidates: list[dict[str, Any]] = []
        if len(selected) >= 2:
            candidates.append(_candidate(
                title="Relación candidata entre elementos seleccionados",
                candidate_type="relacion",
                proposed_data={
                    "source_id": selected[0],
                    "target_id": selected[1],
                    "relation_type": "esta_relacionado_con",
                    "description": "Relación propuesta desde command bar; revisar tipo y dirección antes de aceptar.",
                },
                job=job,
                justification="Usa la selección actual como endpoints explícitos para evitar relaciones fantasma.",
            ))
            report = "Relación candidata creada sobre endpoints seleccionados."
        return {"kind": "candidate_batch", "summary": report, "report": report, "candidates": candidates}

    return {
        "kind": "analysis_report",
        "summary": "Job interpretado como ayuda libre/revisión.",
        "report": "No se ha producido ningún cambio. Reformula o revisa el contexto antes de crear candidatos.",
        "candidates": [],
    }


class AIJobService:
    """In-memory AI job registry for B38 command bar MVP."""

    def __init__(self):
        self._jobs: dict[str, AIJob] = {}

    def create_job(self, job_type: AIJobType | str, prompt: str, *, context_scope: dict[str, Any] | None = None) -> Result:
        prompt = (prompt or "").strip()
        if not prompt:
            return Error("El prompt no puede estar vacío")
        try:
            resolved_type = job_type if isinstance(job_type, AIJobType) else AIJobType(str(job_type))
        except ValueError:
            resolved_type = AIJobType.REVIEW_GRAPH
        job = AIJob(
            type=resolved_type,
            prompt=prompt,
            context_scope=dict(context_scope or {}),
            message="Job creado. Pendiente de ejecución.",
            progress=0.0,
        )
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
            job.error = error
        job.updated_at = _now_iso()
        return Ok(job)

    def execute_job(self, job_id: str) -> Result:
        """Run the deterministic MVP job pipeline synchronously.

        PySide calls this from a QThread, keeping the UI thread responsive.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return Error("Job IA no encontrado")
        if job.status == AIJobStatus.CANCELLED:
            return Error("Job IA cancelado")
        self.update_status(job_id, AIJobStatus.BUILDING_CONTEXT, message="Construyendo contexto", progress=0.15)
        self.update_status(job_id, AIJobStatus.RUNNING, message="Generando propuesta revisable", progress=0.55)
        try:
            result = build_ai_job_result(job)
        except Exception as exc:  # defensive: errors become inline failures
            self.update_status(job_id, AIJobStatus.FAILED, message="Job fallido", error=str(exc), progress=1.0)
            return Error("No se pudo ejecutar el job IA")
        self.update_status(job_id, AIJobStatus.POSTPROCESSING, message="Preparando revisión", progress=0.85)
        return self.update_status(
            job_id,
            AIJobStatus.READY_FOR_REVIEW,
            message=result.get("summary", "Resultado listo para revisión"),
            progress=1.0,
            result=result,
        )

    def cancel_job(self, job_id: str) -> Result:
        job = self._jobs.get(job_id)
        if job is None:
            return Error("Job IA no encontrado")
        if not job.cancellable:
            return Error("Este job no se puede cancelar")
        job.status = AIJobStatus.CANCELLED
        job.message = "Job cancelado"
        job.updated_at = _now_iso()
        return Ok(job)


def classify_ai_job_intent(prompt: str, *, worldbuilding_active: bool = False) -> AIJobType:
    """Heuristic MVP classifier for command-bar prompts.

    The classifier is intentionally conservative and deterministic for tests.
    Later tickets can add model-assisted classification, but this first contract
    keeps UI behavior predictable and offline-capable.
    """
    text = (prompt or "").lower()
    if any(word in text for word in ["coherencia", "incoher", "revisa", "mejoras", "analiza"]):
        return AIJobType.ANALYZE_COHERENCE if "coher" in text else AIJobType.REVIEW_GRAPH
    if "relacion" in text or "relación" in text or "relaciones" in text:
        return AIJobType.SUGGEST_RELATIONS
    if any(word in text for word in ["metafís", "metafis", "worldbuilding", "sistema", "árbol", "arbol"]):
        return AIJobType.EXPAND_WORLDBUILDING if worldbuilding_active else AIJobType.GENERATE_TREE
    if any(word in text for word in ["personaje", "personajes", "entidad", "entidades", "nodos", "nodo"]):
        return AIJobType.GENERATE_ENTITIES
    return AIJobType.REVIEW_GRAPH
