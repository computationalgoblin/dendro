"""E03: narrative corpus indexer."""
from __future__ import annotations

from packages.application.corpus_indexer import CorpusIndexer, IndexingOptions
from packages.application.narrative_rag_contract import CorpusItemKind
from packages.application.rag_service import RAGService
from packages.domain.candidate_issue import (
    Candidate,
    CandidateState,
    CandidateType,
    StructuredIssue,
    StructuredIssueSeverity,
    StructuredIssueState,
    StructuredIssueType,
)
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus
from packages.domain.entity import CanonState, EntityType, NarrativeEntity
from packages.domain.import_models import DocumentSegment, ImportBasket, ImportCandidate, ImportReviewState
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok
from packages.domain.world_layer import WorldLayer


def _entity(entity_id: str, name: str, entity_type: EntityType, *, layer_ids: list[str] | None = None) -> NarrativeEntity:
    return NarrativeEntity(
        id=entity_id,
        name=name,
        entity_type=entity_type,
        brief_description=f"Resumen de {name}",
        extended_description=f"Cuerpo narrativo de {name}",
        exportable_notes=f"Nota publica de {name}",
        private_notes=f"Nota privada de {name}",
        layer_ids=layer_ids or [],
    )


def _make_project() -> Project:
    project = Project(id="proj-e03", name="Proyecto E03", description="Mundo para RAG")
    layer = WorldLayer(id="ring-root", name="Anillo raiz", description="Causas primeras", order=1)
    branch = _entity("branch-1", "Hermandad del Acero", EntityType.CONTENEDOR, layer_ids=["ring-root"])
    branch.custom_metadata = {
        "tree_type": "faccion",
        "tree_internal_rules": ["Nadie abandona vivo"],
        "tree_open_questions": ["Quien financia la Hermandad?"],
    }
    leaf = _entity("leaf-1", "Devian", EntityType.PERSONAJE, layer_ids=["ring-root"])
    archived = _entity("archived-1", "Eco obsoleto", EntityType.NOTA, layer_ids=["ring-root"])
    archived.canon_state = CanonState.ARCHIVADO

    contains = NarrativeRelation(
        id="rel-contains",
        source_id=branch.id,
        target_id=leaf.id,
        relation_type=RelationType.CONTIENE,
        description="Devian pertenece a la Hermandad.",
        layer_ids=["ring-root"],
    )
    conflict = NarrativeRelation(
        id="rel-conflict",
        source_id=leaf.id,
        target_id=branch.id,
        relation_type=RelationType.ESTA_EN_CONFLICTO_CON,
        description="Devian desafia la doctrina interna.",
        causality="Ruptura doctrinal",
        layer_ids=["ring-root"],
    )

    accepted_candidate = Candidate(
        id="cand-accepted",
        candidate_type=CandidateType.ENTIDAD,
        state=CandidateState.ACEPTADO,
        title="Candidato aceptado",
        proposed_data={"name": "Canon aceptado", "description": "Ya revisado"},
        affected_entity_ids=[leaf.id],
    )
    pending_candidate = Candidate(
        id="cand-pending",
        candidate_type=CandidateType.ENTIDAD,
        state=CandidateState.PENDIENTE,
        title="Candidato pendiente",
        proposed_data={"name": "Pendiente"},
    )
    rejected_candidate = Candidate(
        id="cand-rejected",
        candidate_type=CandidateType.ENTIDAD,
        state=CandidateState.RECHAZADO,
        title="Candidato rechazado",
        proposed_data={"name": "Rechazado"},
    )

    issue = StructuredIssue(
        id="issue-1",
        type=StructuredIssueType.BROKEN_RELATION,
        severity=StructuredIssueSeverity.MEDIA,
        state=StructuredIssueState.ABIERTA,
        affected_entity_ids=[leaf.id],
        affected_relation_ids=[conflict.id],
        description="La motivacion de Devian no explica el conflicto.",
        evidence="Falta hito causal.",
    )
    milestone = CausalMilestone(
        id="hito-1",
        title="Juramento Roto",
        description="La Hermandad traiciona a Devian.",
        status=CausalMilestoneStatus.CANON,
        affected_entity_ids=[leaf.id],
        affected_branch_ids=[branch.id],
        caused_relation_ids=[conflict.id],
        layer_ids=["ring-root"],
    )
    project.project_chronology.calendar_name = "Calendario de Hierro"
    project.project_chronology.description = "Calendario usado por la Hermandad."
    project.project_chronology.milestone_ids = [milestone.id]
    project.creative_config.core_premise = "Toda lealtad tiene coste"
    project.creative_config.canon = {"hard_rules": ["No hay resurrecciones gratis"]}

    accepted_segment = DocumentSegment(id="seg-1", source_id="source-1", section="Capitulo", raw_text="Texto aceptado")
    pending_segment = DocumentSegment(id="seg-2", source_id="source-2", section="Borrador", raw_text="Texto no aceptado")
    accepted_import_candidate = ImportCandidate(
        id="imp-cand-1",
        segment_id="seg-1",
        candidate_type="entidad",
        proposed_data={"name": "Fragmento aceptado"},
        review_state=ImportReviewState.ACEPTADO,
    )
    project.import_baskets = [
        ImportBasket(
            id="basket-accepted",
            source_id="source-1",
            segments=[accepted_segment],
            import_candidates=[accepted_import_candidate],
            review_state="aceptado",
        ),
        ImportBasket(
            id="basket-pending",
            source_id="source-2",
            segments=[pending_segment],
            review_state="pendiente",
        ),
    ]

    project.world_layers = [layer]
    project.entities = [branch, leaf, archived]
    project.relations = [contains, conflict]
    project.candidates = [accepted_candidate, pending_candidate, rejected_candidate]
    project.issues = [issue]
    project.causal_milestones = [milestone]
    return project


def test_e03_indexes_domain_corpus_without_canvas_or_parallel_branch_model():
    project = _make_project()

    index = CorpusIndexer().index_project(project)

    branch = index.get(CorpusItemKind.BRANCH, "branch-1")
    leaf = index.get(CorpusItemKind.ENTITY, "leaf-1")
    contains = index.get(CorpusItemKind.RELATION, "rel-contains")
    archived = index.get(CorpusItemKind.ENTITY, "archived-1")

    assert branch is not None
    assert leaf is not None
    assert contains is not None
    assert archived is None
    assert branch.metadata["display_kind"] == "branch"
    assert branch.metadata["child_entity_ids"] == ["leaf-1"]
    assert "Members: Devian" in branch.rendered_text
    assert "Nota privada" not in branch.rendered_text
    assert contains.metadata["structural"] is True
    assert index.counts_by_kind()["world_layer"] == 1
    assert index.counts_by_kind()["milestone"] == 1
    assert index.counts_by_kind()["chronology"] == 1
    assert index.counts_by_kind()["issue"] == 1
    assert index.counts_by_kind()["creative_config"] == 1


def test_e03_candidate_and_import_visibility_defaults_are_conservative():
    project = _make_project()

    index = CorpusIndexer().index_project(project)

    assert index.get(CorpusItemKind.CANDIDATE, "cand-accepted") is not None
    assert index.get(CorpusItemKind.CANDIDATE, "cand-pending") is None
    assert index.get(CorpusItemKind.CANDIDATE, "cand-rejected") is None
    assert index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-accepted:seg-1") is not None
    assert index.get(CorpusItemKind.IMPORT_DOCUMENT, "imp-cand-1") is not None
    assert index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-pending:seg-2") is None

    debug_index = CorpusIndexer().index_project(
        project,
        options=IndexingOptions(
            include_pending_candidates=True,
            include_rejected_candidates=True,
            include_unaccepted_imports=True,
        ),
    )

    assert debug_index.get(CorpusItemKind.CANDIDATE, "cand-pending") is not None
    assert debug_index.get(CorpusItemKind.CANDIDATE, "cand-rejected") is not None
    assert debug_index.get(CorpusItemKind.IMPORT_DOCUMENT, "basket-pending:seg-2") is not None


def test_e03_incremental_reindex_marks_unchanged_updated_and_removed_items():
    project = _make_project()
    indexer = CorpusIndexer()
    first = indexer.index_project(project)

    second = indexer.index_project(project, previous_index=first)
    assert second.stats.unchanged == first.stats.total
    assert second.stats.created == 0
    assert second.stats.updated == 0
    assert second.stats.removed == 0

    leaf = next(entity for entity in project.entities if entity.id == "leaf-1")
    leaf.brief_description = "Devian ahora tiene una motivacion nueva"
    third = indexer.index_project(project, previous_index=second)
    assert third.stats.updated == 1
    assert third.get(CorpusItemKind.ENTITY, "leaf-1").content_hash != second.get(CorpusItemKind.ENTITY, "leaf-1").content_hash

    project.entities = [entity for entity in project.entities if entity.id != "leaf-1"]
    fourth = indexer.index_project(project, previous_index=third)
    assert fourth.get(CorpusItemKind.ENTITY, "leaf-1") is None
    assert fourth.stats.removed >= 1


def test_e03_rag_service_stores_status_and_clears_index():
    project = _make_project()
    service = RAGService()

    result = service.index_project(project)

    assert isinstance(result, Ok)
    status = service.index_status(project.id)
    assert status["indexed"] is True
    assert status["total"] == len(result.value)
    assert status["by_kind"]["branch"] == 1
    assert isinstance(service.get_index(project.id), Ok)

    service.clear_index(project.id)
    assert isinstance(service.get_index(project.id), Error)
