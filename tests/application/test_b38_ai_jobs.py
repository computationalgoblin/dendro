from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from packages.application.ai_jobs import (
    AIJobService,
    AIJobStatus,
    AIJobType,
    COMMAND_BAR_SYSTEM_PROMPT_ES,
    build_job_plan,
    classify_ai_job_intent,
    classify_intent,
)
from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


class CapturingCommandBarProvider(AIProvider):
    provider_name = "test_command_bar"

    def __init__(self, *, error: str | None = None):
        self.error = error
        self.calls: list[tuple[str, str, object]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message, timeout))
        if self.error:
            return None, self.error
        data = json.loads(user_message)
        prompt = data["prompt_exacto_usuario"]
        lower = prompt.lower()
        if "herman" in lower and "traidor" in lower and "tragic" in lower:
            return json.dumps(
                {
                    "summary": "Tres hermanos traidores tragicómicos listos para revisión",
                    "report": "La propuesta respeta hermandad, traición mutua y tono tragicómico.",
                    "entities": [
                        {"name": "Bruno, hermano traidor tragicómico", "entity_type": "personaje", "brief_description": "Hermano mayor que traiciona con solemnidad absurda."},
                        {"name": "Clara, hermana traidora tragicómica", "entity_type": "personaje", "brief_description": "Hermana que vende secretos familiares por orgullo ridículo."},
                        {"name": "Mateo, hermano traidor tragicómico", "entity_type": "personaje", "brief_description": "Hermano menor que sabotea a todos intentando reconciliarlos."},
                    ],
                    "open_questions": [],
                },
                ensure_ascii=False,
            ), None
        if "cient" in lower and "hard sci-fi" in lower:
            return json.dumps(
                {
                    "summary": "Tres científicos hard sci-fi listos para revisión",
                    "report": "La propuesta usa ciencia dura y evita tono tragicómico.",
                    "entities": [
                        {"name": "Dra. Kepler", "entity_type": "personaje", "brief_description": "Astrofísica orbital obsesionada con errores de medición."},
                        {"name": "Dr. Raman", "entity_type": "personaje", "brief_description": "Ingeniero de materiales para hábitats de vacío."},
                        {"name": "Dra. Noether", "entity_type": "personaje", "brief_description": "Matemática de simetrías conservadas."},
                    ],
                },
                ensure_ascii=False,
            ), None
        if "agujeros negros" in lower and "dioses" in lower:
            return json.dumps(
                {
                    "summary": "Sistema metafísico de agujeros negros/dioses",
                    "report": "Dos agujeros negros divinos en combate explican gravedad, tiempo y culto.",
                    "trees": [
                        {"name": "Cosmología de los Dioses Colapsados", "brief_description": "Sistema metafísico basado en dos agujeros negros combatientes."}
                    ],
                    "entities": [
                        {"name": "Gravedad como herida divina", "entity_type": "ley", "brief_description": "Toda atracción material deriva del forcejeo entre dioses."}
                    ],
                },
                ensure_ascii=False,
            ), None
        if "revisa" in lower and "grafo" in lower:
            return json.dumps(
                {
                    "summary": "Informe de revisión del grafo",
                    "report": "Revisión basada en resumen visible y contexto relevante, no exhaustiva global.",
                    "issues": [{"title": "Causa ausente", "description": "Hay elementos sin justificación superior.", "severity": "media"}],
                    "proposals": [{"title": "Añadir causas", "description": "Crear candidatos de explicación antes de canonizar."}],
                    "open_questions": ["¿Qué parte del grafo debe priorizarse?"],
                },
                ensure_ascii=False,
            ), None
        if "devian" in lower and "hermandad" in lower:
            return json.dumps(
                {
                    "summary": "Relaciones para Devian en la Hermandad",
                    "report": "Propone vínculos solo si existen endpoints reales en contexto.",
                    "relations": [
                        {"source_id": "devian", "target_id": "hermandad", "relation_type": "pertenece_a", "description": "Devian opera dentro de la Hermandad con lealtad ambigua."}
                    ],
                },
                ensure_ascii=False,
            ), None
        return json.dumps({"summary": "Plan libre", "report": prompt}, ensure_ascii=False), None

    def invoke(self, operation):  # pragma: no cover - command bar uses chat
        raise AssertionError("Command bar jobs must use chat(), not invoke()")


def test_b38_ai_job_service_creates_reviewable_queued_job_with_plan():
    service = AIJobService(provider=CapturingCommandBarProvider())
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
    assert job.intent["intent_type"] == "generate_entities"
    assert job.plan["prompt"] == "Créame tres personajes para empezar esta historia"
    assert service.list_jobs() == [job]


def test_b38_ai_job_service_rejects_empty_prompt():
    result = AIJobService(provider=CapturingCommandBarProvider()).create_job(AIJobType.REVIEW_GRAPH, "   ")
    assert isinstance(result, Error)


@pytest.mark.parametrize(
    "prompt,worldbuilding,expected",
    [
        ("Créame tres personajes", False, AIJobType.GENERATE_ENTITIES),
        ("Crea un sistema metafísico", False, AIJobType.GENERATE_TREE),
        ("Crea un sistema metafísico", True, AIJobType.EXPAND_WORLDBUILDING),
        ("Propón relaciones para Devian", False, AIJobType.SUGGEST_RELATIONS),
        ("Busca incoherencias", False, AIJobType.ANALYZE_COHERENCE),
        ("Revisa todo el grafo y proponme mejoras", False, AIJobType.REVIEW_GRAPH),
        ("Explícame esto desde causas superiores", True, AIJobType.EXPLAIN_FROM_CAUSES),
        ("No sé qué hacer", False, AIJobType.UNKNOWN),
    ],
)
def test_b38_intent_classifier(prompt, worldbuilding, expected):
    assert classify_ai_job_intent(prompt, worldbuilding_active=worldbuilding) is expected


def test_b38_build_job_plan_separates_classification_from_execution():
    intent = classify_intent("Propón relaciones para Devian dentro de la Hermandad del Acero", {})
    plan = build_job_plan(intent, "Propón relaciones para Devian dentro de la Hermandad del Acero", {"language": "es"})
    assert intent.intent_type is AIJobType.SUGGEST_RELATIONS
    assert plan.expected_result == "relation_candidates"
    assert "candidatos de relación" in plan.creates
    assert plan.prompt == "Propón relaciones para Devian dentro de la Hermandad del Acero"


def test_b38_prompt_exact_is_sent_to_provider_and_results_are_prompt_sensitive():
    provider = CapturingCommandBarProvider()
    service = AIJobService(provider=provider)

    job_a = service.create_job(AIJobType.GENERATE_ENTITIES, "Créame tres personajes que sean hermanos, todos traidores entre sí, en tono tragicómico.").value
    job_b = service.create_job(AIJobType.GENERATE_ENTITIES, "Créame tres científicos en hard sci-fi.").value

    result_a = service.execute_job(job_a.id)
    result_b = service.execute_job(job_b.id)

    assert isinstance(result_a, Ok)
    assert isinstance(result_b, Ok)
    assert provider.calls[0][0] == COMMAND_BAR_SYSTEM_PROMPT_ES
    sent_a = json.loads(provider.calls[0][1])
    sent_b = json.loads(provider.calls[1][1])
    assert sent_a["prompt_exacto_usuario"] == job_a.prompt
    assert sent_b["prompt_exacto_usuario"] == job_b.prompt

    names_a = [c["proposed_data"]["name"] for c in result_a.value.result["candidates"]]
    names_b = [c["proposed_data"]["name"] for c in result_b.value.result["candidates"]]
    assert names_a != names_b
    assert any("herman" in c["proposed_data"]["brief_description"].lower() or "herman" in c["proposed_data"]["name"].lower() for c in result_a.value.result["candidates"])
    assert any("traidor" in c["proposed_data"]["name"].lower() for c in result_a.value.result["candidates"])
    assert any("cient" in c["proposed_data"]["brief_description"].lower() or "kepler" in c["proposed_data"]["name"].lower() for c in result_b.value.result["candidates"])


def test_b38_unconfigured_default_provider_fails_instead_of_fake_success():
    service = AIJobService()  # default environment is simulated unless user configured provider
    job = service.create_job(AIJobType.GENERATE_ENTITIES, "Créame tres personajes").value
    result = service.execute_job(job.id)
    assert isinstance(result, Error)
    failed = service.get_job(job.id).value
    assert failed.status is AIJobStatus.FAILED
    assert "proveedor IA real" in failed.error
    assert failed.result == {}


def test_b38_job_lifecycle_emits_real_phase_progress_and_can_cancel():
    service = AIJobService(provider=CapturingCommandBarProvider())
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa todo el grafo y proponme mejoras").value
    seen: list[tuple[AIJobStatus, float, str]] = []
    result = service.execute_job(job.id, progress_callback=lambda j: seen.append((j.status, j.progress, j.message)))
    assert isinstance(result, Ok)
    assert [s for s, _p, _m in seen] == [
        AIJobStatus.BUILDING_CONTEXT,
        AIJobStatus.PLANNING,
        AIJobStatus.WAITING_FOR_MODEL,
        AIJobStatus.POSTPROCESSING,
        AIJobStatus.READY_FOR_REVIEW,
    ]
    assert [p for _s, p, _m in seen] == [0.2, 0.35, 0.6, 0.8, 1.0]

    job2 = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo visible").value
    cancelled = service.cancel_job(job2.id)
    assert isinstance(cancelled, Ok)
    assert cancelled.value.status is AIJobStatus.CANCELLED


def test_b38_provider_error_becomes_failed_with_sanitized_inline_error():
    service = AIJobService(provider=CapturingCommandBarProvider(error="401 Bearer sk-secret-token"))
    job = service.create_job(AIJobType.GENERATE_ENTITIES, "Créame tres personajes").value
    result = service.execute_job(job.id)
    assert isinstance(result, Error)
    failed = service.get_job(job.id).value
    assert failed.status is AIJobStatus.FAILED
    assert "sk-secret" not in failed.error
    assert "[REDACTED]" in failed.error


def test_b38_generate_entities_produces_candidates_not_entities():
    project = Project(name="B38 smoke")
    project_service = SimpleNamespace(active_project=project)
    candidate_service = CandidateService(
        project_service=project_service,
        entity_service=EntityService(project_service),
        relation_service=RelationService(project_service),
    )
    service = AIJobService(provider=CapturingCommandBarProvider())
    job = service.create_job(AIJobType.GENERATE_ENTITIES, "Créame tres personajes que sean hermanos, todos traidores entre sí, en tono tragicómico.").value
    executed = service.execute_job(job.id)
    assert isinstance(executed, Ok)
    assert project.entities == []

    candidate_data = executed.value.result["candidates"][0]
    created = candidate_service.create_candidate(candidate_data)
    assert isinstance(created, Ok)
    assert project.entities == []
    accepted = candidate_service.accept_candidate(created.value.id)
    assert isinstance(accepted, Ok)
    assert len(project.entities) == 1
    assert project.entities[0].name == candidate_data["proposed_data"]["name"]


def test_b38_suggest_relations_uses_real_context_endpoints_only():
    service = AIJobService(provider=CapturingCommandBarProvider())
    job = service.create_job(
        AIJobType.SUGGEST_RELATIONS,
        "Propón relaciones para Devian dentro de la Hermandad del Acero",
        context_scope={"relevant_entities": [{"id": "devian", "name": "Devian"}, {"id": "hermandad", "name": "Hermandad del Acero"}]},
    ).value
    result = service.execute_job(job.id)
    assert isinstance(result, Ok)
    candidates = result.value.result["candidates"]
    assert candidates[0]["candidate_type"] == "relacion"
    assert candidates[0]["proposed_data"]["source_id"] == "devian"
    assert candidates[0]["proposed_data"]["target_id"] == "hermandad"


def test_b38_review_graph_produces_report_and_no_structural_mutation_candidates():
    service = AIJobService(provider=CapturingCommandBarProvider())
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa todo el grafo y proponme mejoras").value
    result = service.execute_job(job.id)
    assert isinstance(result, Ok)
    ready = result.value
    assert ready.result["kind"] == "analysis_report"
    assert "no exhaustiva" in ready.result["report"]
    assert ready.result["candidates"][0]["candidate_type"] == "sugerencia_ia"
    assert all(c["metadata"]["canon_auto_mutation"] is False for c in ready.result["candidates"])


def test_b38_worldbuilding_prompt_does_not_return_same_three_characters():
    service = AIJobService(provider=CapturingCommandBarProvider())
    job = service.create_job(
        AIJobType.EXPAND_WORLDBUILDING,
        "Crea un sistema metafísico basado en dos agujeros negros que son dioses combatiendo.",
        context_scope={"worldbuilding_active": True},
    ).value
    result = service.execute_job(job.id)
    assert isinstance(result, Ok)
    names = [c["proposed_data"]["name"] for c in result.value.result["candidates"]]
    assert any("agujeros" in result.value.result["report"].lower() or "gravedad" in name.lower() for name in names)
    assert not {"Bruno, hermano traidor tragicómico", "Clara, hermana traidora tragicómica", "Mateo, hermano traidor tragicómico"}.issubset(set(names))
