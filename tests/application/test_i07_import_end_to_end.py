from __future__ import annotations

import json

from packages.application.entity_service import EntityService
from packages.application.graph_service import GraphService
from packages.application.history_service import HistoryService
from packages.application.import_service import ImportService
from packages.application.project_service import ProjectService
from packages.application.query_service import QueryService
from packages.application.rag_service import RAGService
from packages.application.relation_service import RelationService
from packages.application.source_service import SourceService
from packages.domain.ai_models import AIResponse
from packages.domain.import_models import ImportFormat, ImportReviewState
from packages.domain.result import Error, Ok
from packages.application.narrative_rag_contract import CorpusItemKind
from packages.infrastructure.ai_provider import AIProvider
from packages.persistence.store import ProjectStore


class I07Provider(AIProvider):
    provider_name = "i07_fake_provider"

    def __init__(self):
        self.calls: list[tuple[str, str, int | None]] = []
        self._emitted: set[str] = set()

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message, timeout))
        payload = json.loads(user_message)
        text = str(payload["chunk"]["text"]).lower()
        candidates = []

        def emit_once(key: str, data: dict):
            if key not in self._emitted:
                self._emitted.add(key)
                candidates.append(data)

        if "eldrin" in text:
            emit_once("eldrin", {
                "kind": "entity",
                "name": "Eldrin",
                "entity_type": "personaje",
                "aliases": ["El Mago del Norte"],
                "brief_description": "Custodio de la Torre de Marfil.",
                "confidence": 0.9,
            })
        if "mago del norte" in text:
            emit_once("mago_alias", {
                "kind": "entity",
                "name": "El Mago del Norte",
                "entity_type": "personaje",
                "aliases": ["Eldrin"],
                "summary": "Alias usado por cronistas del norte.",
                "confidence": 0.86,
            })
        if "torre de marfil" in text:
            emit_once("torre", {
                "kind": "entity",
                "name": "Torre de Marfil",
                "entity_type": "localizacion",
                "brief_description": "Fortaleza donde se guarda el archivo astral.",
                "confidence": 0.88,
            })
        if "orden del umbral" in text:
            emit_once("orden", {
                "kind": "branch",
                "name": "Orden del Umbral",
                "branch_type": "faccion",
                "summary": "Rama/faccion que custodia portales.",
                "confidence": 0.82,
            })
        if "protege" in text:
            emit_once("relacion", {
                "kind": "relation",
                "source_name": "Eldrin",
                "target_name": "Torre de Marfil",
                "relation_type": "protege",
                "evidence": "Eldrin protege la Torre de Marfil.",
                "confidence": 0.84,
            })
        if "batalla del rio gris" in text:
            emit_once("hito", {
                "kind": "milestone",
                "title": "Batalla del Rio Gris",
                "description": "La batalla obliga a Eldrin a jurar defensa sobre la torre.",
                "milestone_type": "guerra",
                "date_label": "Ano 42 de la Era Presente",
                "structured_date": {"year": 42},
                "confidence": 0.87,
            })
        if "rumor falso" in text:
            emit_once("rumor", {
                "kind": "entity",
                "name": "Rumor Falso",
                "entity_type": "nota",
                "summary": "Material que debe descartarse en review.",
                "confidence": 0.4,
            })
        return json.dumps({"candidates": candidates}, ensure_ascii=False), None

    def invoke(self, operation):  # pragma: no cover - I07 must use chat
        return AIResponse(id="i07", operation=operation, raw_text="", provider=self.provider_name)


def _candidate_by_name(basket, name: str):
    for candidate in basket.import_candidates:
        if (candidate.proposed_data or {}).get("name") == name:
            return candidate
    raise AssertionError(f"candidate not found: {name}")


def _candidate_by_kind(basket, kind: str):
    for candidate in basket.import_candidates:
        if (candidate.proposed_data or {}).get("kind") == kind:
            return candidate
    raise AssertionError(f"candidate kind not found: {kind}")


def _service_graph(project_service: ProjectService, store: ProjectStore) -> GraphService:
    entity_service = EntityService(project_service=project_service, store=store)
    relation_service = RelationService(project_service=project_service, store=store)
    source_service = SourceService(project_service=project_service, store=store)
    history_service = HistoryService(project_service=project_service)
    query_service = QueryService(
        entity_service=entity_service,
        relation_service=relation_service,
        source_service=source_service,
        history_service=history_service,
    )
    return GraphService(
        query_service=query_service,
        relation_service=relation_service,
        entity_service=entity_service,
    )


def test_i07_import_document_to_review_to_canon_graph_rag_and_reload(tmp_path):
    store = ProjectStore()
    project_service = ProjectService(store=store)
    created = project_service.create(name="I07 End To End")
    assert isinstance(created, Ok)
    document = tmp_path / "i07_lore.md"
    document.write_text(
        "\n\n".join([
            "# Personajes\nEldrin protege la Torre de Marfil.",
            "# Alias\nLos cronistas llaman a Eldrin El Mago del Norte.",
            "# Lugares\nLa Torre de Marfil guarda el archivo astral.",
            "# Ramas\nLa Orden del Umbral custodia portales.",
            "# Hitos\nLa Batalla del Rio Gris marco el ano 42.",
            "# Descartes\nRumor Falso debe descartarse.",
        ]),
        encoding="utf-8",
    )

    import_service = ImportService(project_service=project_service)
    imported = import_service.import_document(document, ImportFormat.MARKDOWN)
    assert isinstance(imported, Ok)
    basket = imported.value
    assert len(basket.segments) >= 1
    assert project_service.active_project.entities == []
    assert project_service.active_project.relations == []
    assert project_service.active_project.causal_milestones == []

    provider = I07Provider()
    extracted = import_service.extract_ai_candidates(
        basket.id,
        provider=provider,
        replace_existing=True,
    )
    assert isinstance(extracted, Ok)
    assert {call[2] for call in provider.calls} == {300}
    assert project_service.active_project.entities == []

    analysis = import_service.analyze_import_duplicates(basket.id)
    assert isinstance(analysis, Ok)
    suggestion = _candidate_by_kind(basket, "merge_suggestion")
    merged = import_service.accept_import_merge_suggestion(basket.id, suggestion.id)
    assert isinstance(merged, Ok)
    merged_entity_candidate = merged.value
    assert merged_entity_candidate.proposed_data["merged_from"]

    rumor = _candidate_by_name(basket, "Rumor Falso")
    rejected = import_service.reject_import_candidate(basket.id, rumor.id)
    assert isinstance(rejected, Ok)

    eldrin = import_service.apply_import_candidate_to_canon(basket.id, merged_entity_candidate.id)
    tower = import_service.apply_import_candidate_to_canon(basket.id, _candidate_by_name(basket, "Torre de Marfil").id)
    branch = import_service.apply_import_candidate_to_canon(basket.id, _candidate_by_name(basket, "Orden del Umbral").id)
    assert isinstance(eldrin, Ok)
    assert isinstance(tower, Ok)
    assert isinstance(branch, Ok)

    relation_candidate = _candidate_by_kind(basket, "relation")
    relation = import_service.apply_import_candidate_to_canon(basket.id, relation_candidate.id)
    assert isinstance(relation, Ok)

    milestone_candidate = _candidate_by_kind(basket, "milestone")
    edited = import_service.edit_import_candidate(
        basket.id,
        milestone_candidate.id,
        {
            "linked_entity_ids": [eldrin.value.id, tower.value.id],
            "linked_relation_ids": [relation.value.id],
            "structured_date": {"year": 42},
        },
    )
    assert isinstance(edited, Ok)
    milestone = import_service.apply_import_candidate_to_canon(basket.id, milestone_candidate.id)
    assert isinstance(milestone, Ok)

    project = project_service.active_project
    assert {entity.name for entity in project.entities} >= {"Eldrin", "Torre de Marfil", "Orden del Umbral"}
    assert "Rumor Falso" not in {entity.name for entity in project.entities}
    assert project.relations[0].relation_type.value == "protege"
    assert project.causal_milestones[0].title == "Batalla del Rio Gris"
    assert project.project_chronology.includes_milestone(project.causal_milestones[0].id)
    assert rumor.review_state is ImportReviewState.RECHAZADO
    assert relation_candidate.review_state is ImportReviewState.ACEPTADO
    assert eldrin.value.custom_metadata["source_references"]
    assert relation.value.custom_metadata["source_references"]
    assert milestone.value.metadata["source_references"]

    project_path = tmp_path / "i07_project.json"
    saved = project_service.save(project_path)
    assert isinstance(saved, Ok)
    reopened_service = ProjectService(store=ProjectStore())
    reopened = reopened_service.open(project_path)
    assert isinstance(reopened, Ok)
    loaded = reopened.value
    assert {entity.name for entity in loaded.entities} >= {"Eldrin", "Torre de Marfil", "Orden del Umbral"}
    assert "Rumor Falso" not in {entity.name for entity in loaded.entities}
    assert loaded.project_chronology.includes_milestone(loaded.causal_milestones[0].id)

    graph = _service_graph(reopened_service, reopened_service.store).build_graph()
    assert isinstance(graph, Ok)
    assert {node.label for node in graph.value.nodes} >= {"Eldrin", "Torre de Marfil", "Orden del Umbral"}
    assert graph.value.stats.visible_edges >= 1

    rag_index = RAGService().index_project(loaded)
    assert isinstance(rag_index, Ok)
    assert any(record.metadata.get("source_type") == "canon" for record in rag_index.value.items(CorpusItemKind.ENTITY))
    assert any(record.metadata.get("source_type") == "accepted" for record in rag_index.value.items(CorpusItemKind.IMPORT_DOCUMENT))
    assert any(record.ref_id == loaded.causal_milestones[0].id for record in rag_index.value.items(CorpusItemKind.MILESTONE))
    assert rag_index.value.get(CorpusItemKind.IMPORT_DOCUMENT, rumor.id) is None
