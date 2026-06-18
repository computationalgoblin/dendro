"""E04: contextual retrieval for AI jobs."""
from __future__ import annotations

import json

from packages.application.ai_jobs import AIJobService, AIJobType, build_job_plan, CommandBarIntent
from packages.application.narrative_rag_contract import ContextPriority, CorpusItemKind, RetrievalPlan
from packages.application.rag_context import RAGContextBuilder
from packages.application.rag_service import RAGService
from packages.domain.result import Ok
from packages.infrastructure.ai_provider import AIProvider
from tests.application.test_e03_corpus_indexer import _make_project


class E04Provider(AIProvider):
    provider_name = "e04_provider"

    def __init__(self):
        self.calls: list[tuple[str, str, object]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message, timeout))
        return json.dumps({"summary": "Listo", "report": "Informe revisable"}), None

    def invoke(self, operation):  # pragma: no cover
        raise AssertionError("Command-bar jobs use chat")


_AUTHORITY_SECTIONS = (
    "canon_confirmado",
    "candidates_pendientes",
    "importaciones_sin_revisar",
    "rag_auxiliar",
)


def _authority_refs(sent: dict) -> set[tuple[str, str]]:
    """Recolecta (kind, ref_id) de todas las secciones de autoridad del mensaje."""
    refs: set[tuple[str, str]] = set()
    for key in _AUTHORITY_SECTIONS:
        section = sent.get(key)
        if isinstance(section, dict):
            for item in section.get("items", []):
                if isinstance(item, dict):
                    refs.add((item.get("kind"), item.get("ref_id")))
    return refs


def _coherence_plan():
    intent = CommandBarIntent(
        AIJobType.ANALYZE_COHERENCE,
        0.92,
        "selection",
        "analysis_report",
        retrieval_needs=["selection", "relations", "milestones", "issues", "creative_config"],
    )
    return build_job_plan(
        intent,
        "Analiza la coherencia de Devian y la Hermandad",
        {
            "selected_entity_ids": ["leaf-1"],
            "selected_relation_ids": ["rel-conflict"],
            "active_layer_ids": ["ring-root"],
            "focus_label": "Anillo raiz",
        },
        job_id="job-e04",
    )


def test_e04_excludes_accepted_candidates_from_context():
    # An accepted candidate duplicates the canon it created; if that canon is
    # later deleted, the candidate must not resurface in RAG (it was making the
    # model regenerate previously-deleted rings).
    from packages.domain.candidate_issue import Candidate, CandidateState
    project = _make_project()
    project.candidates.append(Candidate(
        title="Anillo propuesto: El Eón Infinito",
        state=CandidateState.ACEPTADO,
        proposed_data={"kind": "ring_template", "ring_name": "El Eón Infinito"},
    ))
    pack = RAGContextBuilder(RAGService()).build_for_job_plan(project, _coherence_plan()).value
    assert all(item.kind.value != "candidate" for item in pack.items)


def test_e04_context_pack_prioritizes_selection_and_related_context():
    project = _make_project()
    pack = RAGContextBuilder(RAGService()).build_for_job_plan(project, _coherence_plan()).value
    items = {(item.kind.value, item.ref_id): item for item in pack.items}

    assert ("entity", "leaf-1") in items
    assert ("relation", "rel-conflict") in items
    assert ("milestone", "hito-1") in items
    assert ("issue", "issue-1") in items
    # PA02: creative_config ya NO se recupera por RAG (viaja determinista en el
    # prompt vía cerco_canon/parametros_permanentes), aunque se pida como need.
    assert ("creative_config", "creative_config") not in items
    assert items[("entity", "leaf-1")].priority is ContextPriority.REQUIRED
    assert items[("relation", "rel-conflict")].priority is ContextPriority.REQUIRED
    assert "Nota privada" not in json.dumps(pack.to_dict(), ensure_ascii=False)
    assert pack.tokens_estimated <= pack.tokens_budget


def test_e04_context_pack_respects_budget_and_marks_truncation():
    project = _make_project()
    service = RAGService()
    index = service.index_project(project).value
    plan = RetrievalPlan(
        intent_type="review_graph",
        query="Devian Hermandad conflicto calendario causas lealtad",
        include_kinds=[
            CorpusItemKind.ENTITY,
            CorpusItemKind.BRANCH,
            CorpusItemKind.RELATION,
            CorpusItemKind.MILESTONE,
            CorpusItemKind.ISSUE,
            CorpusItemKind.CREATIVE_CONFIG,
        ],
        token_budget=80,
    )

    pack = RAGContextBuilder(service).retrieve(index, plan)

    assert pack.truncated is True
    assert "rag_context_truncated_to_budget" in pack.warnings
    assert pack.tokens_estimated <= 80


def test_e04_ai_job_service_sends_context_pack_to_provider():
    project = _make_project()
    provider = E04Provider()
    service = AIJobService(
        provider=provider,
        rag_service=RAGService(),
        project_provider=lambda: project,
    )
    job = service.create_job(
        AIJobType.ANALYZE_COHERENCE,
        "Analiza la coherencia de Devian",
        context_scope={"selected_entity_ids": ["leaf-1"], "active_layer_ids": ["ring-root"]},
    ).value

    result = service.execute_job(job.id)

    assert isinstance(result, Ok)
    sent = json.loads(provider.calls[0][1])
    # El pack RAG ya no viaja crudo en contexto_autorizado: se reparte en
    # secciones etiquetadas por autoridad (canon / candidates / imports / RAG).
    assert "rag_context_pack" not in json.dumps(sent.get("contexto_autorizado", {}))
    refs = _authority_refs(sent)
    assert ("entity", "leaf-1") in refs
    assert ("relation", "rel-conflict") in refs
    # Entidades/relaciones del corpus son canon confirmado, con etiqueta visible.
    assert "CANON CONFIRMADO" in sent["canon_confirmado"]["autoridad"]
    # El pack crudo sigue disponible en el plan (para traza/observabilidad).
    assert result.value.plan["context"]["rag_context_pack"]["schema"] == "context_pack/v1"


def test_e04_missing_project_degrades_with_structured_warning_only():
    provider = E04Provider()
    service = AIJobService(
        provider=provider,
        rag_service=RAGService(),
        project_provider=lambda: None,
    )
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value

    result = service.execute_job(job.id)

    assert isinstance(result, Ok)
    sent = json.loads(provider.calls[0][1])
    # Sin proyecto: pack vacío con warning estructurado → surface en rag_auxiliar.
    assert _authority_refs(sent) == set()
    assert sent["rag_auxiliar"]["warnings"] == ["rag_project_unavailable"]
    assert "canon_confirmado" not in sent
    assert result.value.plan["context"]["rag_context_pack"]["warnings"] == ["rag_project_unavailable"]
