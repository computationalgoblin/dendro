"""Promoción de un hito a canon — punto ÚNICO (BETA-MULTIAGENT2-FIX-03, G2-03).

Aceptar un hito lo PROMUEVE: deja de ser candidato, queda datado de forma
honesta (o explícitamente «por datar», nunca con un año inventado), sella sus
tiempos y recuerda de qué semilla vino.

Había TRES rutas de aceptación y solo una lo hacía
(``CausalMilestoneService.approve_hito``); las otras dos —la de la UI de
semillas (``CandidateService.accept_candidate``) y la de la reparación de
coherencia (``coherence_repair.apply_resolved_change``)— appendeaban el hito
con los defaults del dominio: ``status=candidate``, ``created_at=""`` y sin
``candidate_id``. El toast decía «Semilla integrada al canon» y el registro
decía otra cosa. Aquí vive la promoción y las tres la llaman: nada de
duplicarla (regla «no modelos paralelos» de AGENTS.md).
"""

from __future__ import annotations

from datetime import datetime, timezone

from packages.application.temporal_dating import normalize_milestone_dating
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus


def now_iso() -> str:
    """Sello temporal de sistema (ISO-8601, UTC). No es tiempo diegético."""
    return datetime.now(timezone.utc).isoformat()


def promote_milestone(
    hito: CausalMilestone, *, candidate_id: str | None = None
) -> CausalMilestone:
    """Promueve ``hito`` a canon y lo sella. Muta y devuelve el mismo objeto.

    - ``status`` → CANON (el payload de ``ai_jobs`` trae literalmente
      ``"status": "candidate"``: la promoción tiene que ser explícita, cambiar
      el default del dominio no arreglaría nada).
    - datación normalizada: un hito sin año queda marcado «por datar»
      (``PENDING_NOTE`` en su ``temporality``), jamás con un año inventado.
    - ``created_at`` (solo si venía vacío) y ``updated_at``.
    - ``candidate_id``: trazabilidad hito↔semilla, de primera clase en
      AGENTS.md. Solo se escribe si se pasa y el hito no lo traía ya.
    """
    hito.status = CausalMilestoneStatus.CANON
    normalize_milestone_dating(hito)
    if candidate_id and not hito.candidate_id:
        hito.candidate_id = str(candidate_id)
    stamp = now_iso()
    if not hito.created_at:
        hito.created_at = stamp
    hito.updated_at = stamp
    return hito


__all__ = ["now_iso", "promote_milestone"]
