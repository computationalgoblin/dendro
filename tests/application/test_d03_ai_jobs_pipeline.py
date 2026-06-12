"""D03: non-blocking AI job pipeline contract."""
from __future__ import annotations

import json

from packages.application.ai_jobs import AIJobService, AIJobStatus, AIJobType
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


class D03Provider(AIProvider):
    provider_name = "d03_provider"

    def __init__(self):
        self.calls: list[tuple[str, str, object]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message, timeout))
        return json.dumps({"summary": "Listo", "report": "Resultado revisable"}), None

    def invoke(self, operation):  # pragma: no cover
        raise AssertionError("D03 command jobs use chat")


def test_d03_jobs_pass_configured_timeout_to_provider():
    provider = D03Provider()
    service = AIJobService(provider=provider, timeout_seconds=7)
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value

    result = service.execute_job(job.id)

    assert isinstance(result, Ok)
    assert provider.calls[0][2] == 7
    assert result.value.result["timeout_seconds"] == 7


def test_d03_jobs_default_timeout_is_300_seconds():
    provider = D03Provider()
    service = AIJobService(provider=provider)
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value

    result = service.execute_job(job.id)

    assert isinstance(result, Ok)
    assert provider.calls[0][2] == 300
    assert result.value.result["timeout_seconds"] == 300


def test_d03_jobs_show_thinking_phase_before_provider_call():
    provider = D03Provider()
    service = AIJobService(provider=provider)
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value
    seen: list[tuple[AIJobStatus, str]] = []

    service.execute_job(job.id, progress_callback=lambda j: seen.append((j.status, j.message)))

    assert (AIJobStatus.WAITING_FOR_MODEL, "Pensando...") in seen


def test_d03_cancel_during_progress_stops_before_provider_call():
    provider = D03Provider()
    service = AIJobService(provider=provider)
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value

    def cancel_on_building(current):
        if current.status is AIJobStatus.BUILDING_CONTEXT:
            service.cancel_job(current.id)

    result = service.execute_job(job.id, progress_callback=cancel_on_building)

    assert isinstance(result, Error)
    assert "cancelado" in result.error.lower()
    assert provider.calls == []
    assert service.get_job(job.id).value.status is AIJobStatus.CANCELLED


def test_d03_timeout_marks_job_failed(monkeypatch):
    provider = D03Provider()
    service = AIJobService(provider=provider, timeout_seconds=5)
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value
    ticks = iter([100.0, 106.0])
    monkeypatch.setattr("packages.application.ai_jobs.time.monotonic", lambda: next(ticks))

    result = service.execute_job(job.id)

    assert isinstance(result, Error)
    failed = service.get_job(job.id).value
    assert failed.status is AIJobStatus.FAILED
    assert "Timeout IA" in failed.error
