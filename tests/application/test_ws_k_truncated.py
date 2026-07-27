"""BETA-CIERRE WS-K: salida truncada por longitud → mensaje honesto.

Antes, una respuesta cortada por max_tokens producía JSON malformado → cero
candidatos → el job quedaba READY_FOR_REVIEW con "Listo para revisar" y cero
semillas, sin explicar que se pagó una llamada de IA para nada. Ahora el motivo
de fin ("length") viaja por un canal lateral del proveedor → GatewayResponse.
truncated → el job lo dice claramente.
"""

from __future__ import annotations

from packages.application.ai_jobs import AIJobService, AIJobType
from packages.domain.result import Ok
from packages.infrastructure.ai_provider import AIProvider


class _TruncatedProvider(AIProvider):
    provider_name = "trunc"
    last_finish_reason = "length"  # el proveedor cortó por max_tokens

    def chat(self, system_prompt, user_message, timeout=None):
        return '{"candidates": [', None  # JSON cortado → no parsea

    def invoke(self, operation):  # pragma: no cover
        raise AssertionError("los jobs usan chat")


class _CompleteProvider(AIProvider):
    provider_name = "ok"
    last_finish_reason = "stop"

    def chat(self, system_prompt, user_message, timeout=None):
        return '{"summary": "Hecho", "report": "todo bien"}', None

    def invoke(self, operation):  # pragma: no cover
        raise AssertionError("los jobs usan chat")


def test_truncated_zero_output_reports_cutoff():
    service = AIJobService(provider=_TruncatedProvider())
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value
    result = service.execute_job(job.id)
    assert isinstance(result, Ok)
    res = result.value.result
    assert res.get("truncated") is True
    # El "Listo para revisar" engañoso se sustituye por el aviso de corte.
    assert "se cortó" in res.get("summary", "")


def test_complete_response_has_no_truncation_note():
    service = AIJobService(provider=_CompleteProvider())
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value
    result = service.execute_job(job.id)
    assert isinstance(result, Ok)
    res = result.value.result
    assert not res.get("truncated")
    assert "se cortó" not in res.get("summary", "")
