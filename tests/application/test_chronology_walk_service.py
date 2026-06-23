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


def _service(project, payloads=None):
    return ChronologyWalkService(
        project_service=_FakeProjectService(project),
        ai_job_service=_FakeAIJobService(payloads or []),
    )


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
