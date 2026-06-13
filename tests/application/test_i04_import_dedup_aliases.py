from __future__ import annotations

from pathlib import Path

from packages.application.import_deduplication_service import ImportDeduplicationService
from packages.application.import_service import ImportService
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.import_models import ImportBasket, ImportCandidate, ImportReviewState
from packages.domain.project import Project
from packages.domain.result import is_ok, unwrap


class FakeProjectService:
    def __init__(self, project=None, current_path=None):
        self.active_project = project
        self._current_path = current_path or Path("/tmp/i04-project.json")


def _ref(chunk_id: str) -> dict:
    return {
        "source_id": "source-1",
        "source_name": "lore.md",
        "segment_id": f"seg-{chunk_id}",
        "chunk_id": chunk_id,
        "section_path": "Capitulo",
        "page_start": None,
        "page_end": None,
        "char_start": 0,
        "char_end": 10,
        "quote_excerpt": f"texto {chunk_id}",
        "extraction_method": "markdown",
    }


def _candidate(
    cid: str,
    name: str,
    *,
    aliases=None,
    entity_type: str = "personaje",
    kind: str = "entity",
    chunk_id: str | None = None,
) -> ImportCandidate:
    return ImportCandidate(
        id=cid,
        segment_id=f"seg-{chunk_id or cid}",
        candidate_type="entidad",
        proposed_data={
            "kind": kind,
            "name": name,
            "entity_type": entity_type,
            "aliases": list(aliases or []),
            "summary": f"Resumen de {name}",
            "source_references": [_ref(chunk_id or cid)],
        },
        confidence=0.7,
        review_state=ImportReviewState.PENDIENTE,
    )


def _basket(*candidates: ImportCandidate) -> ImportBasket:
    return ImportBasket(id="basket-1", source_id="source-1", import_candidates=list(candidates))


def _suggestions(basket: ImportBasket):
    return [
        candidate for candidate in basket.import_candidates
        if candidate.proposed_data.get("kind") == "merge_suggestion"
    ]


def test_i04_detects_obvious_alias_between_candidates():
    basket = _basket(
        _candidate("cand-a", "Eldrin", aliases=["El Mago del Norte"], chunk_id="a"),
        _candidate("cand-b", "El Mago del Norte", chunk_id="b"),
    )

    result = ImportDeduplicationService().analyze_basket(basket)

    assert is_ok(result)
    suggestion = _suggestions(basket)[0]
    assert suggestion.proposed_data["reason"] == "alias_match"
    assert suggestion.proposed_data["affected_candidate_ids"] == ["cand-a", "cand-b"]
    assert len(suggestion.proposed_data["source_references"]) == 2


def test_i04_detects_similar_names_without_forcing_exact_match():
    basket = _basket(
        _candidate("cand-a", "Eldrin de Nareth", chunk_id="a"),
        _candidate("cand-b", "Eldrin Nareth", chunk_id="b"),
    )

    result = ImportDeduplicationService().analyze_basket(basket)

    assert is_ok(result)
    suggestion = _suggestions(basket)[0]
    assert suggestion.proposed_data["reason"] in {"similar_name_match", "exact_name_match"}
    assert suggestion.confidence >= 0.68


def test_i04_marks_type_conflict_without_auto_merging():
    left = _candidate("cand-a", "La Cicatriz", entity_type="personaje", chunk_id="a")
    right = _candidate("cand-b", "La Cicatriz", entity_type="localizacion", chunk_id="b")
    basket = _basket(left, right)

    result = ImportDeduplicationService().analyze_basket(basket)

    assert is_ok(result)
    suggestion = _suggestions(basket)[0]
    assert suggestion.proposed_data["recommended_resolution"] == "manual_review_required"
    assert suggestion.proposed_data["conflicting_fields"] == [
        {"field": "type", "values": ["personaje", "localizacion"]}
    ]
    assert left.possible_contradictions == ["cand-b"]
    assert right.possible_contradictions == ["cand-a"]


def test_i04_accepting_merge_preserves_all_source_references():
    left = _candidate("cand-a", "Eldrin", aliases=["El Mago"], chunk_id="a")
    right = _candidate("cand-b", "El Mago", chunk_id="b")
    basket = _basket(left, right)
    service = ImportDeduplicationService()
    service.analyze_basket(basket)
    suggestion = _suggestions(basket)[0]

    result = service.accept_merge_suggestion(basket, suggestion.id)

    assert is_ok(result)
    merged = unwrap(result)
    assert merged.review_state is ImportReviewState.PENDIENTE
    assert left.review_state is ImportReviewState.FUSIONADO
    assert right.review_state is ImportReviewState.FUSIONADO
    assert suggestion.review_state is ImportReviewState.ACEPTADO
    refs = merged.proposed_data["source_references"]
    assert {ref["chunk_id"] for ref in refs} == {"a", "b"}
    assert merged.proposed_data["merged_from"] == ["cand-a", "cand-b"]
    assert "El Mago" in merged.proposed_data["aliases"]


def test_i04_rejecting_merge_keeps_candidates_separate():
    left = _candidate("cand-a", "Eldrin", aliases=["El Mago"], chunk_id="a")
    right = _candidate("cand-b", "El Mago", chunk_id="b")
    basket = _basket(left, right)
    service = ImportDeduplicationService()
    service.analyze_basket(basket)
    suggestion = _suggestions(basket)[0]

    result = service.reject_merge_suggestion(basket, suggestion.id)

    assert is_ok(result)
    assert suggestion.review_state is ImportReviewState.RECHAZADO
    assert left.review_state is ImportReviewState.PENDIENTE
    assert right.review_state is ImportReviewState.PENDIENTE
    assert len([c for c in basket.import_candidates if c.proposed_data.get("merged_from")]) == 0


def test_i04_marks_duplicate_against_existing_entity_alias():
    entity = NarrativeEntity(id="entity-1", name="Eldrin", entity_type=EntityType.PERSONAJE)
    entity.aliases = ["El Mago del Norte"]
    project = Project(name="I04")
    project.entities.append(entity)
    candidate = _candidate("cand-a", "El Mago del Norte", chunk_id="a")
    basket = _basket(candidate)

    result = ImportDeduplicationService(project=project).analyze_basket(basket)

    assert is_ok(result)
    assert candidate.possible_duplicates == ["entity-1"]
    assert candidate.proposed_data["duplicate_candidates"][0]["entity_id"] == "entity-1"


def test_i04_import_service_accepts_merge_suggestion_without_losing_refs():
    left = _candidate("cand-a", "Eldrin", aliases=["El Mago"], chunk_id="a")
    right = _candidate("cand-b", "El Mago", chunk_id="b")
    basket = _basket(left, right)
    project = Project(name="I04")
    project.import_baskets.append(basket)
    service = ImportService(project_service=FakeProjectService(project))

    analysis = service.analyze_import_duplicates("basket-1")
    suggestion = unwrap(analysis)[0]
    accepted = service.accept_import_merge_suggestion("basket-1", suggestion.id)

    assert is_ok(accepted)
    merged = unwrap(accepted)
    assert {ref["chunk_id"] for ref in merged.proposed_data["source_references"]} == {"a", "b"}
    assert len(basket.import_candidates) == 4

