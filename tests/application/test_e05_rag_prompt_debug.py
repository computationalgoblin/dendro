"""E05: visible RAG state and temporary prompt debug traces."""
from __future__ import annotations

import json

from packages.application.ai_jobs import AIJobService, AIJobType
from packages.application.ai_prompt_debug import AIPromptDebugTraceStore
from packages.application.rag_service import RAGService
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider
from tests.application.test_e03_corpus_indexer import _make_project


class E05Provider(AIProvider):
    provider_name = "e05_provider"

    def __init__(self, *, error: str = ""):
        self.error = error

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        if self.error:
            return None, self.error
        return json.dumps({"summary": "Listo", "report": "Informe"}), None

    def invoke(self, operation):  # pragma: no cover
        raise AssertionError("Command-bar jobs use chat")


def test_e05_prompt_trace_store_writes_autorefreshing_html(tmp_path):
    path = tmp_path / "rag_prompt_debug.html"
    store = AIPromptDebugTraceStore(path)
    message = json.dumps(
        {
            "prompt_exacto_usuario": "Analiza Devian",
            "plan": {
                "intent": {
                    "rationale": "El usuario pide coherencia.",
                    "actions": [{"type": "analyze_coherence", "rationale": "Revisar contradicciones."}],
                }
            },
            "contexto_autorizado": {
                "rag_context_pack": {
                    "schema": "context_pack/v1",
                    "items": [
                        {
                            "kind": "entity",
                            "ref_id": "leaf-1",
                            "priority": "required",
                            "reason": "selected_item",
                        }
                    ],
                }
            },
        },
        ensure_ascii=False,
    )

    store.record_request(
        job_id="job-1",
        provider="test",
        prompt="Analiza Devian",
        system_prompt="Bearer sk-secret-token",
        model_user_message=message,
    )
    store.record_response("job-1", status="ok", response_text="Respuesta")

    html = path.read_text(encoding="utf-8")
    assert "http-equiv=\"refresh\"" in html
    assert "Analiza Devian" in html
    assert "context_pack/v1" in html
    assert "Planner rationale" in html
    assert "selected_item" in html
    assert "sk-secret-token" not in html
    assert "[REDACTED]" in html


def test_e05_ai_job_service_traces_prompt_without_rag_pack(tmp_path):
    # BETA2-WIKI-05: el pipeline dejó de recuperar por RAG. La traza del prompt sigue
    # existiendo (observabilidad), pero SIN context_pack ni secciones de autoridad.
    project = _make_project()
    store = AIPromptDebugTraceStore(tmp_path / "trace.html")
    service = AIJobService(
        provider=E05Provider(),
        rag_service=RAGService(),
        project_provider=lambda: project,
        prompt_trace_store=store,
    )
    job = service.create_job(
        AIJobType.ANALYZE_COHERENCE,
        "Analiza la coherencia de Devian",
        context_scope={"selected_entity_ids": ["leaf-1"], "active_layer_ids": ["ring-root"]},
    ).value

    result = service.execute_job(job.id)

    assert isinstance(result, Ok)
    assert len(store.entries) == 1
    entry = store.entries[0]
    assert entry.status == "ok"
    assert not entry.context_pack  # ya no hay pack RAG
    assert "canon_confirmado" not in entry.model_user_message


def test_e05_ai_job_service_traces_sanitized_provider_errors(tmp_path):
    store = AIPromptDebugTraceStore(tmp_path / "trace.html")
    service = AIJobService(
        provider=E05Provider(error="401 Bearer sk-secret-token"),
        prompt_trace_store=store,
    )
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value

    result = service.execute_job(job.id)

    assert isinstance(result, Error)
    assert store.entries[0].status == "error"
    assert "sk-secret-token" not in store.entries[0].error
    assert "[REDACTED]" in store.entries[0].error


def test_e05_rag_service_reports_pending_indexed_and_clear_states():
    service = RAGService()
    project = Project(id="proj-e05", name="Proyecto E05")

    pending = service.index_status(project.id)
    assert pending["indexed"] is False
    assert pending["state"] == "pending"

    indexed = service.index_project(project)
    assert isinstance(indexed, Ok)
    status = service.index_status(project.id)
    assert status["indexed"] is True
    assert status["state"] == "indexed"
    assert "total" in status

    service.clear_index(project.id)
    assert service.index_status(project.id)["state"] == "pending"
