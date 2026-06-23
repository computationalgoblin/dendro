"""I10 — RAG: material de referencia permanente (modo contexto).

Las cestas en modo contexto se indexan como material de referencia
(source_type="referencia"), consultable siempre y nunca canon. El resumen IA
(si existe en metadata) se indexa como registro extra. El prompt_assembler las
encamina a una sección propia 'material_referencia'.
"""

from __future__ import annotations

import pytest

import json
from pathlib import Path

from packages.application.corpus_indexer import CorpusIndexer, IndexingOptions
from packages.application.import_service import ImportService
from packages.application.narrative_rag_contract import CorpusItemKind, RetrievalPlan
from packages.application.prompt_assembler import _rag_authority_sections
from packages.application.rag_context import RAGContextBuilder
from packages.application.rag_service import RAGService
from packages.domain.import_models import DocumentSegment, ImportBasket, ImportMode
from packages.domain.project import Project
from packages.domain.result import is_error, is_ok, unwrap
from packages.infrastructure.ai_provider import AIProvider


def _context_project(*, with_summary=False) -> Project:
    project = Project(id="proj-i10", name="I10")
    seg = DocumentSegment(
        id="seg-ref",
        source_id="source-ctx",
        section="Lore",
        raw_text="El Bosque Umbral susurra en las noches sin luna.",
        metadata={"chunk_id": "chunk-ref", "section_path": "Lore"},
    )
    metadata = {"file_path": "/tmp/lore.md", "import_mode": "contexto"}
    if with_summary:
        metadata["context_summary"] = {
            "summary": "Resumen del bosque umbral.",
            "topic_cards": [{"title": "Bosque Umbral", "text": "Lugar liminal."}],
        }
    project.import_baskets = [
        ImportBasket(
            id="basket-ctx",
            source_id="source-ctx",
            segments=[seg],
            import_candidates=[],
            review_state="pendiente",
            import_mode="contexto",
            metadata=metadata,
        )
    ]
    return project


@pytest.mark.application
def test_context_segment_indexed_as_reference_by_default():
    # Sin flags especiales: la referencia se indexa (a diferencia de raw_import).
    index = CorpusIndexer().index_project(_context_project())
    rec = index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-ctx:seg-ref")
    assert rec is not None
    assert rec.metadata["source_type"] == "referencia"
    assert rec.metadata["import_rag_state"] == "referencia"
    assert rec.metadata["namespace"] == "referencia"


@pytest.mark.application
def test_reference_can_be_disabled():
    index = CorpusIndexer().index_project(
        _context_project(), options=IndexingOptions(include_reference_material=False)
    )
    assert index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-ctx:seg-ref") is None


@pytest.mark.application
def test_context_summary_indexed_when_present():
    index = CorpusIndexer().index_project(_context_project(with_summary=True))
    rec = index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-ctx:context_summary")
    assert rec is not None
    assert rec.metadata["source_type"] == "referencia"
    assert rec.metadata["context_summary"] is True
    assert "Resumen del bosque umbral" in rec.rendered_text


@pytest.mark.application
def test_no_summary_record_without_summary():
    index = CorpusIndexer().index_project(_context_project(with_summary=False))
    assert index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-ctx:context_summary") is None


@pytest.mark.application
def test_context_reference_never_becomes_canon():
    # Un basket en modo contexto no tiene candidatos → no hay registro "as_canon".
    index = CorpusIndexer().index_project(_context_project(with_summary=True))
    # No debe existir ningún registro ENTITY derivado de esta cesta.
    assert index.get(CorpusItemKind.ENTITY, "import_candidate:seg-ref") is None


@pytest.mark.application
def test_context_pack_auto_includes_reference_material():
    project = _context_project()
    # Plan que NO pide imports explícitamente: la referencia debe colarse igual.
    plan = RetrievalPlan(
        intent_type="write",
        query="Bosque Umbral noche",
        include_kinds=[CorpusItemKind.ENTITY],
        token_budget=1200,
    )
    pack = RAGContextBuilder(RAGService()).build_context_pack(project, plan).value
    by_ref = {item.ref_id: item for item in pack.items}
    assert "basket-ctx:seg-ref" in by_ref
    assert by_ref["basket-ctx:seg-ref"].metadata["source_type"] == "referencia"


# ── I12: generación del resumen IA (modo contexto) ──────────────────────


class _SummaryProvider(AIProvider):
    provider_name = "i12_fake"

    def __init__(self, payload: dict):
        self._payload = payload
        self.calls: list[tuple[str, str, object]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message, timeout))
        return json.dumps(self._payload, ensure_ascii=False), None


class _FakeProjectService:
    def __init__(self, project, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i12.json")


@pytest.mark.application
def test_summary_generation_stores_in_metadata_not_canon():
    project = _context_project()
    svc = ImportService(project_service=_FakeProjectService(project))
    provider = _SummaryProvider({
        "summary": "Documento sobre el Bosque Umbral.",
        "topic_cards": [{"title": "Bosque Umbral", "text": "Lugar liminal."}],
    })
    result = svc.summarize_context_basket("basket-ctx", provider=provider)
    assert is_ok(result)
    summary = unwrap(result)
    assert summary["summary"].startswith("Documento sobre")
    # Guardado en metadata de la cesta, no como canon ni candidato.
    basket = project.import_baskets[0]
    assert basket.metadata["context_summary"]["topic_cards"][0]["title"] == "Bosque Umbral"
    assert basket.import_candidates == []
    assert project.entities == []


@pytest.mark.application
def test_summary_rejected_for_canon_mode_basket():
    project = _context_project()
    project.import_baskets[0].import_mode = ImportMode.CANON.value
    svc = ImportService(project_service=_FakeProjectService(project))
    provider = _SummaryProvider({"summary": "x", "topic_cards": []})
    result = svc.summarize_context_basket("basket-ctx", provider=provider)
    assert is_error(result)


@pytest.mark.application
def test_summary_then_indexed_as_reference():
    project = _context_project()
    svc = ImportService(project_service=_FakeProjectService(project))
    provider = _SummaryProvider({
        "summary": "Resumen indexable.",
        "topic_cards": [{"title": "T", "text": "txt"}],
    })
    svc.summarize_context_basket("basket-ctx", provider=provider)
    # El resumen generado se indexa como material de referencia.
    index = CorpusIndexer().index_project(project)
    rec = index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-ctx:context_summary")
    assert rec is not None
    assert rec.metadata["source_type"] == "referencia"
    assert "Resumen indexable" in rec.rendered_text


@pytest.mark.application
def test_prompt_assembler_routes_reference_to_own_section():
    context = {
        "rag_context_pack": {
            "items": [
                {
                    "kind": "import_document",
                    "ref_id": "basket-ctx:seg-ref",
                    "rendered_text": "Bosque Umbral",
                    "metadata": {"source_type": "referencia"},
                },
                {
                    "kind": "import_document",
                    "ref_id": "otra:seg",
                    "rendered_text": "import sin revisar",
                    "metadata": {"source_type": "raw_import"},
                },
            ]
        }
    }
    sections = _rag_authority_sections(context)
    assert "material_referencia" in sections
    ref_ids = {it["ref_id"] for it in sections["material_referencia"]["items"]}
    assert ref_ids == {"basket-ctx:seg-ref"}
    # La referencia NO se mezcla con importaciones sin revisar.
    assert "importaciones_sin_revisar" in sections
    imp_ids = {it["ref_id"] for it in sections["importaciones_sin_revisar"]["items"]}
    assert imp_ids == {"otra:seg"}
