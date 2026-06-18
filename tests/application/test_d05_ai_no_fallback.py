from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from packages.application.ai_context_actions import AIContextActionService
from packages.application.ai_jobs import AIJobService, AIJobStatus, AIJobType
from packages.application.ai_observability import AIObservabilityLog
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider, SimulatedAIProvider


class D05Provider(AIProvider):
    provider_name = "d05_provider"
    model = "d05-model"

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        return json.dumps({
            "summary": "Candidato trazable listo",
            "entities": [
                {
                    "name": "Hoja D05",
                    "entity_type": "personaje",
                    "brief_description": "Propuesta para verificar trazabilidad.",
                }
            ],
        }, ensure_ascii=False), None


@pytest.mark.application
def test_d05_default_ai_job_has_no_simulated_fallback() -> None:
    log = AIObservabilityLog()
    service = AIJobService(observability_log=log)
    job = service.create_job(AIJobType.GENERATE_ENTITIES, "Crea una hoja").value

    result = service.execute_job(job.id)

    assert isinstance(result, Error)
    failed = service.get_job(job.id).value
    assert failed.status is AIJobStatus.FAILED
    assert failed.result == {}
    assert "contenido simulado" in failed.error
    assert log.latest is not None
    assert log.latest.status == "error"
    assert log.latest.error_type == "provider_unconfigured"


@pytest.mark.application
def test_d05_ai_job_candidates_include_trace_metadata() -> None:
    log = AIObservabilityLog()
    service = AIJobService(provider=D05Provider(), observability_log=log)
    job = service.create_job(AIJobType.GENERATE_ENTITIES, "Crea una hoja").value

    result = service.execute_job(job.id)

    assert isinstance(result, Ok)
    candidate = result.value.result["candidates"][0]
    metadata = candidate["metadata"]
    assert candidate["source"] == "ai_command_bar"
    assert candidate["source_id"] == job.id
    assert metadata["provider"] == "d05_provider"
    assert metadata["model"] == "d05-model"
    assert metadata["prompt"] == "Crea una hoja"
    assert metadata["trace_status"] == "ready_for_review"
    assert log.latest is not None
    assert log.latest.status == "ok"
    assert log.latest.model == "d05-model"
    assert log.latest.output_size > 0


@pytest.mark.application
def test_d05_context_actions_do_not_use_simulated_provider_by_default() -> None:
    service = AIContextActionService(
        project_service=SimpleNamespace(active_project=None),
        candidate_service=SimpleNamespace(),
        provider=SimulatedAIProvider(),
    )

    result = service.run_node_text_suggestion("node-1", prompt_hint="Mejorar")

    assert isinstance(result, Error)
    assert "IA no configurada" in result.error
