"""CRON — servicio de recorrido cronológico.

Usa un AIJobService falso (payloads canónicos) para verificar la orquestación
sin proveedor real: arranque, orden por dirección, parada ante problema duro,
decisión, reanudación e informe final.
"""

from __future__ import annotations

import pytest

from packages.application.chronology_walk_service import ChronologyWalkService
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.chronology_walk import (
    WalkAggressiveness,
    WalkDepth,
    WalkDirection,
    WalkMode,
    WalkStatus,
)
from packages.domain.era import Era
from packages.domain.project import Project
from packages.domain.result import Error, Ok


class _FakeProjectService:
    def __init__(self, project):
        self.active_project = project


class _FakeJob:
    def __init__(self, result):
        self.id = "job_fake"
        self.result = result


class _FakeAIJobService:
    """Devuelve, por orden, los payloads programados (envueltos como stage_results)."""

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

    def run_focused_job(self, job_type, prompt, *, context_scope=None, progress_callback=None):
        self.calls.append({"job_type": job_type, "prompt": prompt, "context": context_scope})
        payload = self._payloads.pop(0) if self._payloads else {}
        result = {
            "kind": "analysis",
            "summary": payload.get("summary", ""),
            "report": payload.get("report", ""),
            "candidates": [],
            "open_questions": [],
            "model_payload": payload,
        }
        return Ok(_FakeJob(result))


def _project_with_three_milestones():
    project = Project(id="p-cron", name="CRON")
    project.causal_milestones.extend(
        [
            CausalMilestone(id="h1", title="Origen", year=100, affected_entity_ids=["e1"]),
            CausalMilestone(id="h2", title="Purga", year=200, affected_entity_ids=["e2"]),
            CausalMilestone(id="h3", title="Caída", year=300, affected_entity_ids=["e3"]),
        ]
    )
    return project


def _service(project, payloads=None, history_service=None):
    return ChronologyWalkService(
        project_service=_FakeProjectService(project),
        ai_job_service=_FakeAIJobService(payloads or []),
        history_service=history_service,
    )


class _RecordingHistory:
    """Historial de prueba: captura las llamadas a record()."""

    def __init__(self):
        self.records: list[dict] = []

    def record(self, event_type=None, description=None, affected_entity_ids=None, **kwargs):
        self.records.append(
            {
                "event_type": event_type,
                "description": description,
                "affected_entity_ids": list(affected_entity_ids or []),
                "change_origin": kwargs.get("change_origin", ""),
                "metadata": dict(kwargs.get("metadata", {}) or {}),
            }
        )


@pytest.mark.application
def test_fold_step_records_observation_per_affected_entity():
    """PLAY-18: cada paso deja una observación en el historial de las entidades."""
    project = _project_with_three_milestones()
    project.causal_milestones[1].affected_entity_ids = ["e2", "e5"]
    history = _RecordingHistory()
    payloads = [
        {
            "summary": "La Purga golpea a la casa.",
            "issues": [
                {"title": "Duda", "description": "¿Quién ordenó?", "severity": "media",
                 "kind": "causal_gap"}
            ],
        }
    ]
    svc = _service(project, payloads, history_service=history)
    session = svc.start_walk("h2").value

    svc.analyze_step(session.id)

    assert len(history.records) == 2  # una por entidad afectada
    rec = history.records[0]
    assert rec["change_origin"] == "recorrido_cronologico"
    assert rec["metadata"]["milestone_id"] == "h2"
    assert "La Purga golpea" in rec["description"]
    assert "Duda" in rec["description"]  # las observaciones sin edición viajan
    from packages.domain.source_history import HistoryEventType

    assert rec["event_type"] is HistoryEventType.OBSERVACION_RECORRIDO


@pytest.mark.application
def test_fold_step_without_history_service_records_nothing():
    """PLAY-18: sin history_service inyectado, no se registra nada (compat)."""
    project = _project_with_three_milestones()
    svc = _service(project, [{"summary": "ok"}])  # sin history_service
    session = svc.start_walk("h1").value

    res = svc.analyze_step(session.id)  # no debe explotar

    assert isinstance(res, Ok)


@pytest.mark.application
def test_start_walk_creates_active_session():
    project = _project_with_three_milestones()
    svc = _service(project)

    res = svc.start_walk("h1", direction=WalkDirection.FUTURE, mode=WalkMode.MIXTO)

    assert isinstance(res, Ok)
    session = res.value
    assert session.status is WalkStatus.ACTIVE
    assert session.current_milestone_id == "h1"
    assert project.chronology_walk_sessions == [session]


@pytest.mark.application
def test_start_walk_rejects_unknown_milestone():
    svc = _service(_project_with_three_milestones())
    assert isinstance(svc.start_walk("nope"), Error)


@pytest.mark.application
def test_start_walk_returns_existing_active_session():
    project = _project_with_three_milestones()
    svc = _service(project)
    first = svc.start_walk("h1").value

    again = svc.start_walk("h3")

    assert isinstance(again, Ok)
    assert again.value.id == first.id
    assert len(project.chronology_walk_sessions) == 1


@pytest.mark.application
def test_advance_future_goes_to_higher_year():
    project = _project_with_three_milestones()
    svc = _service(project)
    session = svc.start_walk("h1", direction=WalkDirection.FUTURE).value

    assert isinstance(svc.advance(session.id), Ok)
    assert session.current_milestone_id == "h2"
    svc.advance(session.id)
    assert session.current_milestone_id == "h3"


@pytest.mark.application
def test_advance_past_goes_to_lower_year():
    project = _project_with_three_milestones()
    svc = _service(project)
    session = svc.start_walk("h3", direction=WalkDirection.PAST).value

    assert isinstance(svc.advance(session.id), Ok)
    assert session.current_milestone_id == "h2"


@pytest.mark.application
def test_advance_past_end_completes_and_writes_report():
    project = _project_with_three_milestones()
    svc = _service(project)
    session = svc.start_walk("h3", direction=WalkDirection.FUTURE).value  # h3 es el último

    res = svc.advance(session.id)

    assert isinstance(res, Ok)
    assert session.status is WalkStatus.COMPLETED
    assert len(project.chronology_walk_reports) == 1
    report = project.chronology_walk_reports[0]
    assert report.session_id == session.id
    assert report.timeline_reviewed_up_to_milestone_id == "h3"


@pytest.mark.application
def test_analyze_step_updates_memory_and_stops_on_hard_problem():
    project = _project_with_three_milestones()
    payloads = [
        {
            "summary": "Punto de inflexión para Devian",
            "issues": [
                {
                    "title": "Servidumbre no motivada",
                    "description": "Falta justificar la obediencia.",
                    "severity": "alta",
                    "kind": "motivation_incompatibility",
                }
            ],
            "narrative_state": {"tension": "deuda vs persecución"},
            "stop_required": True,
            "stop_reason": "Motivación incompatible",
        }
    ]
    svc = _service(project, payloads)
    session = svc.start_walk("h2", direction=WalkDirection.FUTURE).value

    res = svc.analyze_step(session.id)

    assert isinstance(res, Ok)
    assert res.value["walk"]["stopped"] is True
    assert session.status is WalkStatus.PAUSED
    assert "h2" in session.visited_milestone_ids
    assert session.accumulated_summary  # prosa acumulada
    assert session.last_narrative_state == {"tension": "deuda vs persecución"}
    assert len(session.open_problems) == 1
    # Con un problema duro sin resolver, no se puede avanzar.
    assert isinstance(svc.advance(session.id), Error)


@pytest.mark.application
def test_record_decision_resolves_problem_and_reenables_advance():
    project = _project_with_three_milestones()
    payloads = [
        {
            "summary": "Diagnóstico duro",
            "issues": [{"title": "X", "severity": "alta", "kind": "contradiction"}],
            "stop_required": True,
        }
    ]
    svc = _service(project, payloads)
    session = svc.start_walk("h1", direction=WalkDirection.FUTURE).value
    svc.analyze_step(session.id)
    assert session.status is WalkStatus.PAUSED

    dec = svc.record_decision(session.id, "pospuesto", note="lo resuelvo luego")

    assert isinstance(dec, Ok)
    assert session.status is WalkStatus.ACTIVE
    assert all(p["resolved"] for p in session.open_problems)
    assert isinstance(svc.advance(session.id), Ok)
    assert session.current_milestone_id == "h2"


@pytest.mark.application
def test_analyze_step_minor_opportunity_does_not_stop():
    project = _project_with_three_milestones()
    payloads = [
        {
            "summary": "Lectura tranquila",
            "issues": [{"title": "Oportunidad", "severity": "baja", "kind": "opportunity"}],
            "stop_required": False,
        }
    ]
    svc = _service(project, payloads)
    session = svc.start_walk("h1").value

    res = svc.analyze_step(session.id)

    assert res.value["walk"]["stopped"] is False
    assert session.status is WalkStatus.ACTIVE
    assert session.open_problems == []  # oportunidad menor no es problema


@pytest.mark.application
def test_resume_flips_paused_to_active():
    project = _project_with_three_milestones()
    svc = _service(project)
    session = svc.start_walk("h1").value
    session.status = WalkStatus.PAUSED

    res = svc.resume(session.id)

    assert isinstance(res, Ok)
    assert session.status is WalkStatus.ACTIVE


@pytest.mark.application
def test_stop_writes_partial_report_and_marks_stopped():
    project = _project_with_three_milestones()
    svc = _service(project)
    session = svc.start_walk("h1").value

    res = svc.stop(session.id)

    assert isinstance(res, Ok)
    assert session.status is WalkStatus.STOPPED
    assert len(project.chronology_walk_reports) == 1


@pytest.mark.application
def test_attach_generated_candidates_dedups():
    project = _project_with_three_milestones()
    svc = _service(project)
    session = svc.start_walk("h1").value

    svc.attach_generated_candidates(session.id, ["c1", "c2", "c1"])
    svc.attach_generated_candidates(session.id, ["c2", "c3"])

    assert session.generated_candidate_ids == ["c1", "c2", "c3"]


@pytest.mark.application
def test_analyze_step_at_does_not_touch_session_memory():
    """PLAY-01: el análisis de prefetch/desvío NO muta la sesión."""
    project = _project_with_three_milestones()
    payloads = [
        {
            "summary": "Análisis anticipado",
            "issues": [{"title": "X", "severity": "alta", "kind": "contradiction"}],
            "stop_required": True,
        }
    ]
    svc = _service(project, payloads)
    session = svc.start_walk("h1", direction=WalkDirection.FUTURE).value

    res = svc.analyze_step_at(session.id, "h2")

    assert isinstance(res, Ok)
    assert "model_payload" in res.value
    assert "walk" not in res.value  # sin memoria plegada
    assert session.visited_milestone_ids == []
    assert session.open_problems == []
    assert session.accumulated_summary == ""
    assert session.status is WalkStatus.ACTIVE


@pytest.mark.application
def test_commit_step_folds_prefetched_analysis_on_arrival():
    """PLAY-01: al llegar a la escena, commit_step pliega el análisis cacheado."""
    project = _project_with_three_milestones()
    payloads = [
        {
            "summary": "Purga anticipada",
            "issues": [{"title": "Duro", "severity": "alta", "kind": "contradiction"}],
            "stop_required": True,
        }
    ]
    svc = _service(project, payloads)
    session = svc.start_walk("h1", direction=WalkDirection.FUTURE).value
    prefetched = svc.analyze_step_at(session.id, "h2").value

    # Aún en h1: plegarlo sería mentir sobre el orden del recorrido.
    assert isinstance(svc.commit_step(session.id, "h2", prefetched), Error)

    svc.advance(session.id)  # ahora current = h2
    res = svc.commit_step(session.id, "h2", prefetched)

    assert isinstance(res, Ok)
    walk = res.value["walk"]
    assert walk["milestone_id"] == "h2"
    assert walk["stopped"] is True
    assert walk["position"] == 2
    assert walk["total"] == 3
    assert "h2" in session.visited_milestone_ids
    assert session.status is WalkStatus.PAUSED
    assert session.accumulated_summary  # el resumen creció al plegar, no al prefetch


@pytest.mark.application
def test_analyze_step_reports_position_and_total():
    project = _project_with_three_milestones()
    svc = _service(project, [{"summary": "ok"}])
    session = svc.start_walk("h2").value

    walk = svc.analyze_step(session.id).value["walk"]

    assert walk["position"] == 2
    assert walk["total"] == 3
    assert walk["milestone_title"] == "Purga"
    assert walk["milestone_year"] == 200


@pytest.mark.application
def test_step_scene_is_deterministic_and_causal():
    """PLAY-01: escena sin IA — posición, era, causas/consecuencias, visita."""
    project = _project_with_three_milestones()
    project.causal_milestones[1].causal_parent_hito_ids = ["h1"]
    # BETA2-FIX-09: la consecuencia se declara por el lado PADRE (fuente
    # de verdad); antes este test se escribía a mano el espejo
    # (`causal_child_hito_ids`), que en la app real no llenaba nadie. El espejo
    # sucio se deja puesto a propósito: la escena lo ignora y no cuela ids rotos.
    project.causal_milestones[2].causal_parent_hito_ids = ["h2"]
    project.causal_milestones[1].causal_child_hito_ids = ["h3", "desconocido"]
    project.project_chronology.eras.append(
        Era(name="Edad de Plata", start_year=0, end_year=None, order=0)
    )
    svc = _service(project)
    session = svc.start_walk("h2", direction=WalkDirection.FUTURE).value

    res = svc.step_scene(session.id)

    assert isinstance(res, Ok)
    scene = res.value
    assert scene["hito"]["id"] == "h2"
    assert scene["position"] == 2
    assert scene["total"] == 3
    assert scene["next_milestone_id"] == "h3"
    assert [c["id"] for c in scene["causes"]] == ["h1"]
    assert [c["id"] for c in scene["consequences"]] == ["h3"]  # el roto se omite
    assert scene["is_current"] is True
    assert scene["era_name"] == "Edad de Plata"
    # Desvío: describe otro hito sin tocar la sesión.
    visit = svc.step_scene(session.id, "h1").value
    assert visit["hito"]["id"] == "h1"
    assert visit["is_current"] is False
    assert session.current_milestone_id == "h2"


@pytest.mark.application
def test_defer_problems_unblocks_advance_without_resolving():
    """PLAY-02: aplazar desbloquea el avance sin fingir resolución."""
    project = _project_with_three_milestones()
    payloads = [
        {
            "summary": "Diagnóstico duro",
            "issues": [{"title": "X", "severity": "alta", "kind": "contradiction"}],
            "stop_required": True,
        }
    ]
    svc = _service(project, payloads)
    session = svc.start_walk("h1", direction=WalkDirection.FUTURE).value
    svc.analyze_step(session.id)
    assert isinstance(svc.advance(session.id), Error)  # duro sin tratar → bloquea

    res = svc.defer_problems(session.id, note="lo miro al final")

    assert isinstance(res, Ok)
    assert session.status is WalkStatus.ACTIVE
    problem = session.open_problems[0]
    assert problem["deferred"] is True
    assert not problem.get("resolved")  # sigue vivo, no se finge resolución
    assert session.decisions[-1]["decision"] == "aplazado"
    assert session.decisions[-1]["note"] == "lo miro al final"
    assert isinstance(svc.advance(session.id), Ok)
    assert session.current_milestone_id == "h2"


@pytest.mark.application
def test_defer_problems_requires_open_problems():
    project = _project_with_three_milestones()
    svc = _service(project)
    session = svc.start_walk("h1").value

    assert isinstance(svc.defer_problems(session.id), Error)


@pytest.mark.application
def test_deferred_problems_surface_in_final_report():
    """PLAY-02: lo aplazado reaparece en el informe (metadata + veredicto no limpio)."""
    project = _project_with_three_milestones()
    payloads = [
        {
            "summary": "Duro",
            "issues": [{"title": "Hueco", "severity": "alta", "kind": "causal_gap"}],
            "stop_required": True,
        }
    ]
    svc = _service(project, payloads)
    session = svc.start_walk("h1").value
    svc.analyze_step(session.id)
    svc.defer_problems(session.id, note="pendiente")

    svc.stop(session.id)

    report = project.chronology_walk_reports[0]
    assert report.verdict != "Coherente hasta el hito revisado"
    deferred = report.metadata["deferred_problems"]
    assert len(deferred) == 1
    assert deferred[0]["title"] == "Hueco"
    assert any(g["title"] == "Hueco" for g in report.critical_gaps)


@pytest.mark.application
def test_deferred_session_round_trips_persistence():
    """PLAY-02: el aplazado sobrevive to_dict/from_dict sin migración."""
    from packages.domain.chronology_walk import ChronologyWalkSession

    project = _project_with_three_milestones()
    payloads = [
        {
            "summary": "Duro",
            "issues": [{"title": "X", "severity": "alta", "kind": "contradiction"}],
            "stop_required": True,
        }
    ]
    svc = _service(project, payloads)
    session = svc.start_walk("h1").value
    svc.analyze_step(session.id)
    svc.defer_problems(session.id)

    revived = ChronologyWalkSession.from_dict(session.to_dict())

    assert revived.open_problems[0]["deferred"] is True
    assert revived.decisions[-1]["decision"] == "aplazado"


@pytest.mark.application
def test_context_passes_mode_temperature_and_aggressiveness():
    project = _project_with_three_milestones()
    fake = _FakeAIJobService([{"summary": "ok"}])
    svc = ChronologyWalkService(project_service=_FakeProjectService(project), ai_job_service=fake)
    session = svc.start_walk(
        "h2",
        mode=WalkMode.CONSISTENCIA,
        depth=WalkDepth.PROFUNDA,
        aggressiveness=WalkAggressiveness.SENALAR,
    ).value

    svc.analyze_step(session.id)

    ctx = fake.calls[0]["context"]
    assert ctx["model_temperature"] == 0.15  # Consistencia → frío
    assert ctx["directivas"]["parametros"]["agresividad"] == "solo_senalar"
    assert ctx["directivas"]["parametros"]["numero_sugerencias"] == 5  # Profunda
    assert ctx["selected_entity_ids"] == ["e2"]
    assert ctx["chrono_walk"]["current"]["id"] == "h2"
