from __future__ import annotations

import pytest
from types import SimpleNamespace

from packages.application.ai_jobs import (
    AIJobService,
    AIJobStatus,
    AIJobType,
    build_ai_job_result,
    classify_ai_job_intent,
)
from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.domain.project import Project
from packages.domain.result import Error, Ok


def test_b38_ai_job_service_creates_reviewable_queued_job():
    service = AIJobService()
    result = service.create_job(
        AIJobType.GENERATE_ENTITIES,
        "Créame tres personajes para empezar esta historia",
        context_scope={"selected_entity_ids": ["e1"], "worldbuilding_active": True},
    )
    assert isinstance(result, Ok)
    job = result.value
    assert job.status is AIJobStatus.QUEUED
    assert job.type is AIJobType.GENERATE_ENTITIES
    assert job.context_scope["selected_entity_ids"] == ["e1"]
    assert job.result == {}
    assert service.list_jobs() == [job]


def test_b38_ai_job_service_rejects_empty_prompt():
    result = AIJobService().create_job(AIJobType.REVIEW_GRAPH, "   ")
    assert isinstance(result, Error)


def test_b38_ai_job_service_updates_and_cancels_without_persistence():
    service = AIJobService()
    created = service.create_job("review_graph", "Revisa todo el grafo")
    assert isinstance(created, Ok)
    job = created.value
    updated = service.update_status(job.id, AIJobStatus.BUILDING_CONTEXT, message="Construyendo contexto", progress=0.25)
    assert isinstance(updated, Ok)
    assert updated.value.message == "Construyendo contexto"
    assert updated.value.progress == 0.25
    cancelled = service.cancel_job(job.id)
    assert isinstance(cancelled, Ok)
    assert cancelled.value.status is AIJobStatus.CANCELLED


@pytest.mark.parametrize(
    "prompt,worldbuilding,expected",
    [
        ("Créame tres personajes", False, AIJobType.GENERATE_ENTITIES),
        ("Crea un sistema metafísico", False, AIJobType.GENERATE_TREE),
        ("Crea un sistema metafísico", True, AIJobType.EXPAND_WORLDBUILDING),
        ("Propón relaciones para Devian", False, AIJobType.SUGGEST_RELATIONS),
        ("Busca incoherencias", False, AIJobType.ANALYZE_COHERENCE),
        ("Revisa todo el grafo y proponme mejoras", False, AIJobType.REVIEW_GRAPH),
    ],
)
def test_b38_heuristic_intent_classifier(prompt, worldbuilding, expected):
    assert classify_ai_job_intent(prompt, worldbuilding_active=worldbuilding) is expected


def test_b38_execute_job_produces_ready_for_review_candidates_without_canon_mutation():
    service = AIJobService()
    created = service.create_job(
        AIJobType.GENERATE_ENTITIES,
        "Créame tres personajes para empezar esta historia",
        context_scope={"active_layer_ids": ["layer_characters"]},
    )
    assert isinstance(created, Ok)
    job = created.value

    executed = service.execute_job(job.id)

    assert isinstance(executed, Ok)
    ready = executed.value
    assert ready.status is AIJobStatus.READY_FOR_REVIEW
    assert ready.progress == 1.0
    assert ready.result["kind"] == "candidate_batch"
    assert len(ready.result["candidates"]) == 3
    assert all(c["state"] == "pendiente" for c in ready.result["candidates"])
    assert all(c["metadata"]["canon_auto_mutation"] is False for c in ready.result["candidates"])
    assert ready.result["candidates"][0]["proposed_data"]["layer_ids"] == ["layer_characters"]


def test_b38_review_graph_result_is_analysis_candidate_not_direct_change():
    service = AIJobService()
    job = service.create_job(
        AIJobType.REVIEW_GRAPH,
        "Revisa todo el grafo y proponme mejoras",
        context_scope={"selected_entity_ids": []},
    ).value

    result = build_ai_job_result(job)

    assert result["kind"] == "analysis_report"
    assert "Revisión MVP" in result["report"]
    assert result["candidates"][0]["candidate_type"] == "sugerencia_ia"
    assert "report" in result["candidates"][0]["proposed_data"]


def test_b38_suggest_relations_requires_real_selected_endpoints():
    service = AIJobService()
    no_selection = service.create_job(
        AIJobType.SUGGEST_RELATIONS,
        "Propón relaciones",
        context_scope={"selected_entity_ids": ["only-one"]},
    ).value
    result = build_ai_job_result(no_selection)
    assert result["candidates"] == []

    selected = service.create_job(
        AIJobType.SUGGEST_RELATIONS,
        "Propón relaciones",
        context_scope={"selected_entity_ids": ["e1", "e2"]},
    ).value
    result = build_ai_job_result(selected)
    assert result["candidates"][0]["candidate_type"] == "relacion"
    assert result["candidates"][0]["proposed_data"]["source_id"] == "e1"
    assert result["candidates"][0]["proposed_data"]["target_id"] == "e2"


def test_b38_job_candidate_can_be_reviewed_then_accepted_by_real_services():
    project = Project(name="B38 smoke")
    project_service = SimpleNamespace(active_project=project)
    candidate_service = CandidateService(
        project_service=project_service,
        entity_service=EntityService(project_service),
        relation_service=RelationService(project_service),
    )
    job_service = AIJobService()
    job = job_service.create_job(
        AIJobType.GENERATE_ENTITIES,
        "Créame tres personajes",
    ).value
    executed = job_service.execute_job(job.id)
    assert isinstance(executed, Ok)

    candidate_data = executed.value.result["candidates"][0]
    created = candidate_service.create_candidate(candidate_data)

    assert isinstance(created, Ok)
    assert project.entities == []  # el job y la bandeja no canonizan automáticamente
    accepted = candidate_service.accept_candidate(created.value.id)
    assert isinstance(accepted, Ok)
    assert len(project.entities) == 1
    assert project.entities[0].name == candidate_data["proposed_data"]["name"]
