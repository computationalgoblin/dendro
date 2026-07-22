"""BETA2-SHIP-07: re-plegar el MISMO hito en Play no duplica el estado persistido.

Bug (auditoría de datos): con la IA lenta, el watchdog muestra «Reintentar»; el
worker viejo sigue vivo y, al terminar, pliega el hito — y el 2º worker lo pliega
otra vez. El token de UI solo suprime la reacción visual, no el _fold_step ya
ejecutado en el hilo. Resultado persistido: open_problems duplicados (h:0, h:1),
línea de resumen repetida y observaciones de historial x2. Además el resumen
duplicado viajaba al prompt del paso siguiente.
"""

from __future__ import annotations

from packages.application.chronology_walk_service import ChronologyWalkService
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.project import Project


class _FakeProjectService:
    def __init__(self, project):
        self.active_project = project


class _RecordingHistory:
    def __init__(self):
        self.records: list[dict] = []

    def record(self, event_type=None, description=None, affected_entity_ids=None, **kwargs):
        self.records.append({"milestone": dict(kwargs.get("metadata", {})).get("milestone_id")})


def _svc_session_hito():
    project = Project(id="p", name="P")
    project.causal_milestones.append(
        CausalMilestone(id="h1", title="Origen", year=100, affected_entity_ids=["e1"])
    )
    history = _RecordingHistory()
    svc = ChronologyWalkService(
        project_service=_FakeProjectService(project),
        ai_job_service=None,
        history_service=history,
    )
    session = svc.start_walk("h1").value
    return svc, session, project, project.causal_milestones[0], history


def _payload():
    return {
        "model_payload": {
            "summary": "La casa cae.",
            "issues": [
                {"title": "Duda", "description": "¿?", "severity": "media", "kind": "causal_gap"},
            ],
        }
    }


def test_double_fold_same_milestone_is_idempotent():
    svc, session, project, hito, history = _svc_session_hito()

    svc._fold_step(session, project, hito, _payload())
    problems_after_first = [p for p in session.open_problems if p["milestone_id"] == "h1"]
    summary_after_first = session.accumulated_summary

    # Segundo pliegue del MISMO hito (la carrera worker-viejo + Reintentar).
    svc._fold_step(session, project, hito, _payload())

    problems_after_second = [p for p in session.open_problems if p["milestone_id"] == "h1"]
    assert len(problems_after_second) == len(problems_after_first) == 1, "open_problems duplicado"
    # El resumen no repite la línea del hito.
    assert session.accumulated_summary.count("La casa cae.") == 1
    assert session.accumulated_summary == summary_after_first
    # El historial no registra la observación dos veces.
    assert len([r for r in history.records if r["milestone"] == "h1"]) == 1


def test_fresh_analysis_on_refold_replaces_problems():
    """Un re-análisis con problemas distintos SUSTITUYE (no acumula)."""
    svc, session, project, hito, _ = _svc_session_hito()
    svc._fold_step(session, project, hito, _payload())

    nuevo = {
        "model_payload": {
            "summary": "Revisado.",
            "issues": [
                {"title": "Otro", "description": "z", "severity": "alta", "kind": "contradiction"}
            ],
        }
    }
    svc._fold_step(session, project, hito, nuevo)
    problems = [p for p in session.open_problems if p["milestone_id"] == "h1"]
    assert len(problems) == 1
    assert problems[0]["title"] == "Otro"  # el fresco sustituye al viejo
