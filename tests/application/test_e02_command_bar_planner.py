"""E02: AI-backed command-bar planner."""
from __future__ import annotations

import json

from packages.application.ai_jobs import AIJobService, AIJobStatus, AIJobType
from packages.application.command_bar_planner import (
    COMMAND_BAR_PLANNER_SYSTEM_PROMPT_ES,
    CommandBarPlannerService,
    parse_command_bar_plan,
)
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


class PlannerAwareProvider(AIProvider):
    provider_name = "planner_aware"
    model = "planner-model"
    supports_command_bar_planner = True

    def __init__(self, *, planner_text: str | None = None, planner_error: str | None = None):
        self.planner_text = planner_text
        self.planner_error = planner_error
        self.calls: list[tuple[str, str, object]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message, timeout))
        if system_prompt == COMMAND_BAR_PLANNER_SYSTEM_PROMPT_ES:
            if self.planner_error:
                return None, self.planner_error
            return self.planner_text or json.dumps({
                "intent_type": "propose_milestones",
                "confidence": 0.91,
                "target_scope": "selection",
                "expected_output_type": "milestone_candidates",
                "needs_confirmation": True,
                "rationale": "El usuario pide una razon historica y validar coherencia.",
                "actions": [
                    {
                        "type": "suggest_milestones",
                        "output_type": "milestone_candidates",
                        "target_refs": ["selection"],
                        "rationale": "Crear origen historico revisable.",
                    },
                    {
                        "type": "suggest_relations",
                        "output_type": "relation_candidates",
                        "target_refs": ["selection"],
                        "rationale": "Vincular faccion y linaje como candidato.",
                    },
                    {
                        "type": "analyze_coherence",
                        "output_type": "analysis_report",
                        "target_refs": ["chronology"],
                        "rationale": "Evitar contradicciones de cronologia.",
                    },
                ],
                "retrieval_needs": ["selection", "relations", "chronology", "milestones"],
                "clarifying_question": None,
            }), None

        data = json.loads(user_message)
        assert data["intent"]["planner_source"] == "ai"
        assert data["contexto_autorizado"]["command_bar_plan"]["retrieval_needs"] == [
            "selection",
            "relations",
            "chronology",
            "milestones",
        ]
        return json.dumps({
            "summary": "Origen historico propuesto",
            "report": "El conflicto queda como propuesta revisable.",
            "milestones": [
                {
                    "title": "El Juramento Roto",
                    "summary": "Una alianza fallida origina el odio entre faccion y linaje.",
                    "rationale": "Explica la enemistad sin canonizarla.",
                }
            ],
            "relations": [
                {
                    "source_name": "Faccion seleccionada",
                    "target_name": "Linaje seleccionado",
                    "relation_type": "odia_a",
                    "description": "Odio historico propuesto por IA.",
                }
            ],
        }), None

    def invoke(self, operation):  # pragma: no cover
        raise AssertionError("Command-bar planner must use chat")


def test_e02_parser_accepts_multi_action_plan():
    result = parse_command_bar_plan(json.dumps({
        "intent_type": "suggest_relations",
        "confidence": 0.84,
        "target_scope": "selection",
        "expected_output_type": "relation_candidates",
        "needs_confirmation": False,
        "actions": [
            {"type": "suggest_relations", "output_type": "relation_candidates", "target_refs": ["selection"]},
            {"type": "analyze_coherence", "output_type": "analysis_report", "target_refs": ["selection"]},
        ],
        "retrieval_needs": ["selection", "relations"],
    }))

    assert isinstance(result, Ok)
    plan = result.value
    assert plan.intent_type == "suggest_relations"
    assert plan.needs_confirmation is True
    assert [a.type for a in plan.actions] == ["suggest_relations", "analyze_coherence"]


def test_e02_parser_rejects_direct_canon_mutation_actions():
    result = parse_command_bar_plan(json.dumps({
        "intent_type": "generate_entities",
        "actions": [{"type": "create_entity"}],
    }))

    assert isinstance(result, Error)
    assert "accion directa no permitida" in result.error


def test_e02_planner_service_sanitizes_context_before_provider_call():
    provider = PlannerAwareProvider()
    service = CommandBarPlannerService(provider)

    result = service.plan("Relaciona esta seleccion", {"api_key": "sk-secret", "selected_entity_ids": ["e1"]}, timeout_seconds=12)

    assert isinstance(result, Ok)
    assert provider.calls[0][2] == 12
    sent = provider.calls[0][1]
    assert "sk-secret" not in sent
    assert "selected_entity_ids" in sent


def test_e02_ai_job_service_uses_planner_before_final_generation():
    provider = PlannerAwareProvider()
    service = AIJobService(provider=provider, timeout_seconds=300)
    job = service.create_job(
        AIJobType.UNKNOWN,
        "Haz que esta faccion tenga una razon historica para odiar a este linaje, pero no contradigas la cronologia.",
        context_scope={"selected_entity_ids": ["faccion", "linaje"]},
    ).value

    result = service.execute_job(job.id)

    assert isinstance(result, Ok)
    ready = result.value
    assert ready.status is AIJobStatus.READY_FOR_REVIEW
    assert ready.type is AIJobType.PROPOSE_MILESTONES
    assert ready.intent["planner_source"] == "ai"
    assert ready.intent["retrieval_needs"] == ["selection", "relations", "chronology", "milestones"]
    assert len(provider.calls) == 2
    assert provider.calls[0][0] == COMMAND_BAR_PLANNER_SYSTEM_PROMPT_ES
    assert ready.result["candidates"][0]["proposed_data"]["kind"] == "causal_milestone"
    assert ready.result["candidates"][1]["candidate_type"] == "relacion"


def test_e02_ai_job_service_fails_if_active_planner_cannot_plan():
    provider = PlannerAwareProvider(planner_text="Esto no es JSON")
    service = AIJobService(provider=provider)
    job = service.create_job(AIJobType.UNKNOWN, "Crea una hoja").value

    result = service.execute_job(job.id)

    assert isinstance(result, Error)
    failed = service.get_job(job.id).value
    assert failed.status is AIJobStatus.FAILED
    assert "No se pudo interpretar" in failed.error
    assert len(provider.calls) == 1
