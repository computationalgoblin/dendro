"""H05: project chronology/calendar and AI milestone candidates."""

from __future__ import annotations

import json
from types import SimpleNamespace

from packages.application.ai_jobs import AIJob, AIJobService, AIJobStatus, AIJobType, stage_results
from packages.application.candidate_service import CandidateService
from packages.application.project_chronology_service import ProjectChronologyService
from packages.domain.candidate_issue import CandidateState, CandidateType
from packages.domain.project import Project
from packages.domain.result import Error
from packages.infrastructure.ai_provider import SimulatedAIProvider


class FakeProjectService:
    def __init__(self, project=None):
        self.active_project = project or Project(name="H05")


def test_project_chronology_service_updates_manual_calendar_without_ai():
    ps = FakeProjectService()
    service = ProjectChronologyService(ps)

    result = service.update({
        "calendar_name": "Calendario de Ceniza",
        "description": "Cuenta desde la Caida.",
        "calendar_system": "full_calendar",
        "mode": "full_calendar",
        "eras": "Antes\nDespues",
        "months": "Luna\nSol",
        "weekdays": "Uno\nDos",
        "days_per_month": 28,
        "current_year": 42,
    })

    assert not isinstance(result, Error)
    chronology = result.value
    assert chronology.calendar_name == "Calendario de Ceniza"
    assert chronology.calendar_system == "full_calendar"
    assert chronology.metadata["mode"] == "full_calendar"
    assert chronology.metadata["eras"] == ["Antes", "Despues"]
    assert chronology.metadata["months"] == ["Luna", "Sol"]
    assert chronology.metadata["weekdays"] == ["Uno", "Dos"]
    assert chronology.metadata["days_per_month"] == 28
    assert chronology.metadata["current_year"] == 42
    assert chronology.metadata["supports_exact_dates"] is True


def test_project_chronology_service_vague_mode_has_default_periods():
    ps = FakeProjectService()
    service = ProjectChronologyService(ps)

    result = service.update({"mode": "vague_periods", "calendar_system": "vague_periods"})

    assert not isinstance(result, Error)
    assert result.value.metadata["periods"] == ["Antiguedad", "Historia reciente", "Actualidad"]
    assert result.value.metadata["supports_exact_dates"] is False
    assert result.value.metadata["date_resolution"] == "periodo"


def test_stage_results_turns_chronology_and_milestones_into_reviewable_candidates():
    job = AIJob(
        type=AIJobType.PROPOSE_MILESTONES,
        prompt="Sugiere hitos y calendario",
        context_scope={
            "selected_entity_ids": ["real-entity"],
            "selected_relation_ids": ["real-relation"],
            "active_layer_ids": ["layer-1"],
        },
    )
    payload = {
        "project_chronology_suggestion": {
            "title": "Calendario Lunar",
            "mode": "relative",
            "eras": ["Exilio"],
            "rationale": "Encaja con el tono.",
        },
        "milestones": [{
            "id": "invented-by-model",
            "title": "El pacto",
            "summary": "Se funda la alianza.",
            "chronology_key": "Exilio 2",
            "sort_index": 2,
        }],
    }

    result = stage_results(payload, job)

    assert result["candidates"][0]["proposed_data"]["kind"] == "project_chronology_suggestion"
    hito = result["candidates"][1]["proposed_data"]["milestone"]
    assert hito["title"] == "El pacto"
    assert hito["affected_entity_ids"] == ["real-entity"]
    assert hito["caused_relation_ids"] == ["real-relation"]
    assert hito["layer_ids"] == ["layer-1"]
    assert hito["metadata"]["chronology_key"] == "Exilio 2"
    assert hito.get("id") != "invented-by-model"


def test_accepting_h05_candidates_mutates_only_after_review_acceptance():
    ps = FakeProjectService()
    candidate_service = CandidateService(ps)
    hito_candidate = candidate_service.create_candidate({
        "title": "Hito candidato",
        "candidate_type": CandidateType.SUGERENCIA_IA.value,
        "state": CandidateState.PENDIENTE.value,
        "proposed_data": {
            "kind": "causal_milestone",
            "milestone": {
                "id": "hito-1",
                "title": "Fundacion",
                "affected_entity_ids": ["ent-1"],
            },
        },
    }).value
    chronology_candidate = candidate_service.create_candidate({
        "title": "Calendario candidato",
        "candidate_type": CandidateType.SUGERENCIA_IA.value,
        "state": CandidateState.PENDIENTE.value,
        "proposed_data": {
            "kind": "project_chronology_suggestion",
            "title": "Calendario relativo",
            "mode": "relative",
            "eras": ["Inicio"],
        },
    }).value

    assert ps.active_project.causal_milestones == []

    accepted_hito = candidate_service.accept_candidate(hito_candidate.id)
    accepted_chronology = candidate_service.accept_candidate(chronology_candidate.id)

    assert not isinstance(accepted_hito, Error)
    assert not isinstance(accepted_chronology, Error)
    assert ps.active_project.causal_milestones[0].title == "Fundacion"
    assert ps.active_project.project_chronology.milestone_ids == ["hito-1"]
    assert ps.active_project.project_chronology.calendar_name == "Calendario relativo"
    assert ps.active_project.project_chronology.metadata["accepted_from_candidate"] is True


def test_ai_jobs_do_not_use_simulated_provider_unless_explicitly_allowed():
    service = AIJobService(provider=SimulatedAIProvider(), allow_simulated=False)
    job = service.create_job(AIJobType.PROPOSE_MILESTONES, "Sugiere un hito").value

    result = service.execute_job(job.id)

    assert isinstance(result, Error)
    assert service.get_job(job.id).value.status == AIJobStatus.FAILED


class H05Provider:
    provider_name = "test-provider"
    model = "test-model"

    def chat(self, system_prompt, user_message, timeout=None):
        assert timeout == 300
        assert "formatos_h05" in user_message
        return json.dumps({
            "summary": "ok",
            "milestones": [{"title": "Descubrimiento", "summary": "Aparece una pista."}],
        }), ""


def test_ai_job_provider_uses_h05_schema_and_300s_timeout():
    service = AIJobService(provider=H05Provider())
    job = service.create_job(
        AIJobType.PROPOSE_MILESTONES,
        "Sugiere un hito",
        context_scope={"selected_entity_ids": ["ent-1"]},
    ).value

    result = service.execute_job(job.id)

    assert not isinstance(result, Error)
    candidate = result.value.result["candidates"][0]
    assert candidate["proposed_data"]["kind"] == "causal_milestone"
    assert result.value.result["timeout_seconds"] == 300
