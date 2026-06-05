from __future__ import annotations

import pytest

from packages.application.ai_jobs import (
    AIJobService,
    AIJobStatus,
    AIJobType,
    classify_ai_job_intent,
)
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
