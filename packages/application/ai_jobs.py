"""B38 AI job contract and in-memory service.

AI jobs are the command-bar unit of work.  They never mutate canon directly;
results are meant to become reviewable candidates/suggestions in later tickets.

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
