from __future__ import annotations

from packages.application.corpus_indexer import CorpusIndexer, IndexingOptions
from packages.application.narrative_rag_contract import CorpusItemKind, RetrievalPlan
from packages.application.rag_context import RAGContextBuilder
from packages.application.rag_service import RAGService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.import_models import DocumentSegment, ImportBasket, ImportCandidate, ImportReviewState
from packages.domain.project import Project


def _source_ref(segment_id: str, quote: str) -> dict:
    return {
        "source_id": "source-import",
        "source_name": "lore.md",
        "segment_id": segment_id,
        "chunk_id": f"chunk-{segment_id}",
        "section_path": "Capitulo importado",
        "quote_excerpt": quote,
    }


def _candidate(cid: str, segment_id: str, state: ImportReviewState, *, name: str, kind: str = "entity") -> ImportCandidate:
    return ImportCandidate(
        id=cid,
        segment_id=segment_id,
        candidate_type="entidad",
        proposed_data={
            "kind": kind,
            "name": name,
            "summary": f"Resumen de {name}",
            "source_references": [_source_ref(segment_id, f"Fuente de {name}")],
        },
        review_state=state,
    )


def _project_with_imports() -> Project:
    project = Project(id="proj-i06", name="I06")
    project.entities = [
        NarrativeEntity(
            id="canon-entity",
            name="Ciudad Canon",
            entity_type=EntityType.LOCALIZACION,
            brief_description="Canon ya aceptado",
        )
    ]
    accepted_segment = DocumentSegment(
        id="seg-accepted",
        source_id="source-import",
        section="Canon",
        raw_text="Texto aceptado sobre la Ciudad Canon.",
        metadata={"chunk_id": "chunk-seg-accepted", "section_path": "Canon"},
    )
    raw_segment = DocumentSegment(
        id="seg-raw",
        source_id="source-import",
        section="Borrador",
        raw_text="Texto bruto sobre el Santuario Umbral.",
        metadata={"chunk_id": "chunk-seg-raw", "section_path": "Borrador"},
    )
    project.import_baskets = [
        ImportBasket(
            id="basket-accepted",
            source_id="source-import",
            segments=[accepted_segment],
            import_candidates=[
                _candidate("imp-accepted", "seg-accepted", ImportReviewState.ACEPTADO, name="Ciudad Importada"),
                _candidate("imp-reviewed", "seg-accepted", ImportReviewState.EDITADO, name="Barrio Revisado"),
                _candidate("imp-rejected", "seg-accepted", ImportReviewState.RECHAZADO, name="Error Rechazado"),
            ],
            review_state="aceptado",
        ),
        ImportBasket(
            id="basket-raw",
            source_id="source-import",
            segments=[raw_segment],
            import_candidates=[
                _candidate("imp-raw", "seg-raw", ImportReviewState.PENDIENTE, name="Santuario Umbral"),
            ],
            review_state="pendiente",
        ),
    ]
    return project


def test_i06_import_index_separates_raw_reviewed_and_accepted_sources():
    project = _project_with_imports()

    index = CorpusIndexer().index_project(project)

    accepted_doc = index.get(CorpusItemKind.IMPORT_DOCUMENT, "imp-accepted")
    reviewed_doc = index.get(CorpusItemKind.IMPORT_DOCUMENT, "imp-reviewed")
    accepted_as_canon = index.get(CorpusItemKind.ENTITY, "import_candidate:imp-accepted")

    assert accepted_doc is not None
    assert accepted_doc.metadata["source_type"] == "accepted"
    assert reviewed_doc is not None
    assert reviewed_doc.metadata["source_type"] == "reviewed"
    assert accepted_as_canon is not None
    assert accepted_as_canon.metadata["source_type"] == "canon"
    assert accepted_as_canon.metadata["import_rag_state"] == "accepted"
    assert index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-raw:seg-raw") is None
    assert index.get(CorpusItemKind.IMPORT_DOCUMENT, "imp-raw") is None
    assert index.get(CorpusItemKind.IMPORT_DOCUMENT, "imp-rejected") is None

    debug_index = CorpusIndexer().index_project(
        project,
        options=IndexingOptions(include_unaccepted_imports=True),
    )
    raw_segment = debug_index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-raw:seg-raw")
    raw_candidate = debug_index.get(CorpusItemKind.IMPORT_DOCUMENT, "imp-raw")

    assert raw_segment is not None
    assert raw_segment.metadata["source_type"] == "raw_import"
    assert raw_segment.metadata["namespace"] == "raw_import"
    assert raw_candidate is not None
    assert raw_candidate.metadata["source_type"] == "raw_import"
    assert debug_index.get(CorpusItemKind.IMPORT_DOCUMENT, "imp-rejected") is None

    rejected_debug = CorpusIndexer().index_project(
        project,
        options=IndexingOptions(include_unaccepted_imports=True, include_rejected_candidates=True),
    )
    rejected = rejected_debug.get(CorpusItemKind.IMPORT_DOCUMENT, "imp-rejected")
    assert rejected is not None
    assert rejected.metadata["source_type"] == "rejected"


def test_i06_context_pack_exposes_source_type_for_canon_and_raw_imports():
    project = _project_with_imports()
    plan = RetrievalPlan(
        intent_type="review_import",
        query="Santuario Umbral Ciudad Canon",
        include_kinds=[CorpusItemKind.IMPORT_DOCUMENT, CorpusItemKind.ENTITY],
        include_unaccepted_imports=True,
        token_budget=1200,
    )

    pack = RAGContextBuilder(RAGService()).build_context_pack(project, plan).value
    by_ref = {item.ref_id: item for item in pack.items}

    assert by_ref["canon-entity"].metadata["source_type"] == "canon"
    assert by_ref["basket-raw:seg-raw"].metadata["source_type"] == "raw_import"
    assert by_ref["basket-raw:seg-raw"].metadata["import_rag_state"] == "raw_import"
    assert by_ref["imp-raw"].metadata["source_type"] == "raw_import"
