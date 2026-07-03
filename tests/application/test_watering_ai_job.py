"""Riego IA end-to-end: job WATER_ENTITY (BETA2-FOCO-05).

El riego consume IA autorizada y produce SOLO un diagnóstico persistente:
jamás candidatos, jamás mutación de canon. Sin proveedor real falla claro.
"""

from __future__ import annotations

import json

import pytest

from packages.application.ai_jobs import _TEXT_INTENTS, AIJobService, AIJobType
from packages.application.ai_request_gateway import INTENT_PARAMS
from packages.application.command_prompts import has_intent_prompt, system_prompt_for_intent
from packages.application.context_budget import INTENT_TO_TIER, ContextTier
from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.watering_service import WateringService
from packages.domain.entity import CanonState, NarrativeEntity, NarrativeImportance
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok
from packages.domain.watering import WateringStatus
from packages.infrastructure.ai_provider import AIProvider

_VALID_PAYLOAD = {
    # La IA intenta colar "relevancia": debe DESCARTARSE (la fija el usuario).
    "scores": {"arraigo": 34, "nutrida": 71, "iluminada": 18, "relevancia": 99},
    "summary": "Bien nutrida pero flota sin raíces.",
    "metric_explanations": {
        "arraigo": "Sin causa previa que la haga verosímil.",
        "nutrida": "Ficha sólida e integrada.",
        "iluminada": "Apenas proyecta derivaciones.",
    },
    "risks": ["Entidad flotante sin sostén"],
}


class FakeWateringProvider(AIProvider):
    provider_name = "fake_watering"
    model = "fake-model-1"

    def __init__(self, *, payload=None, raw_text=None, error=None):
        self.payload = payload if payload is not None else dict(_VALID_PAYLOAD)
        self.raw_text = raw_text
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message))
        if self.error:
            return None, self.error
        if self.raw_text is not None:
            return self.raw_text, None
        return json.dumps(self.payload, ensure_ascii=False), None


def _setup(provider=None):
    project_service = ProjectService()
    project_service.create("Jardín IA")
    ai_service = None
    if provider is not None:
        ai_service = AIJobService(
            provider=provider, project_provider=lambda: project_service.active_project
        )
    watering = WateringService(
        project_service,
        ai_job_service=ai_service,
        history_service=HistoryService(project_service),
    )
    return project_service, watering


def _entity(project_service, name, **kwargs):
    entity = NarrativeEntity(name=name, **kwargs)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _relate(project_service, source, target, relation_type=RelationType.ESTA_RELACIONADO_CON):
    relation = NarrativeRelation(
        source_id=source.id, target_id=target.id, relation_type=relation_type
    )
    project_service.active_project.relations.append(relation)
    project_service.active_project.touch()
    return relation


@pytest.mark.application
class TestWaterEntityRegistry:
    def test_intent_registered_everywhere(self):
        assert INTENT_TO_TIER["water_entity"] is ContextTier.FAST_LOCAL
        assert "water_entity" in INTENT_PARAMS
        assert has_intent_prompt("water_entity")
        assert AIJobType.WATER_ENTITY not in _TEXT_INTENTS

    def test_system_prompt_contract(self):
        prompt = system_prompt_for_intent("water_entity")
        for token in ("arraigo", "nutrida", "iluminada", "fantasma", "JSON"):
            assert token in prompt
        assert "PROHIBIDO proponer" in prompt
        assert "NO evalúes ni devuelvas 'relevancia'" in prompt


@pytest.mark.application
class TestWaterEntity:
    def test_success_persists_diagnostic_and_nothing_else(self):
        provider = FakeWateringProvider()
        project_service, watering = _setup(provider)
        entity = _entity(
            project_service, "Banda del Cuervo", narrative_importance=NarrativeImportance.ALTO
        )
        cause = _entity(project_service, "Guerra del Norte")
        ghost = _entity(project_service, "¿Un mecenas?", canon_state=CanonState.FANTASMA)
        _relate(project_service, cause, entity, RelationType.CAUSO)
        _relate(project_service, ghost, entity, RelationType.CAUSO)
        project = project_service.active_project
        entities_before = len(project.entities)
        relations_before = len(project.relations)

        result = watering.water_entity(entity.id)
        assert isinstance(result, Ok), getattr(result, "error", None)
        diagnostic = result.value

        # Métricas IA + relevancia del USUARIO (ALTO→75; el 99 de la IA se descarta).
        expected_scores = {"arraigo": 34, "nutrida": 71, "iluminada": 18, "relevancia": 75}
        assert diagnostic.scores == expected_scores
        assert diagnostic.summary.startswith("Bien nutrida")
        assert diagnostic.provider == "fake_watering"
        assert diagnostic.model == "fake-model-1"
        assert diagnostic.cost_class == "bajo"
        assert diagnostic.origin == "single"
        assert diagnostic.context_manifest["estimated_tokens"] > 0
        assert entity.id in diagnostic.context_manifest["entity_ids"]

        # Persistencia + estado + historial. Y CERO candidatos / CERO canon nuevo.
        assert len(project.watering_diagnostics) == 1
        assert watering.status_of(entity.id).value.status == WateringStatus.REGADA.value
        assert project.candidates == []
        assert len(project.entities) == entities_before
        assert len(project.relations) == relations_before
        events = [entry.event_type.value for entry in project.history]
        assert "riego_entidad" in events

    def test_prompt_contains_compact_context_with_marked_ghosts(self):
        provider = FakeWateringProvider()
        project_service, watering = _setup(provider)
        entity = _entity(project_service, "Banda del Cuervo")
        ghost = _entity(project_service, "¿Un mecenas?", canon_state=CanonState.FANTASMA)
        _relate(project_service, ghost, entity, RelationType.CAUSO)

        assert isinstance(watering.water_entity(entity.id), Ok)
        system_prompt, user_message = provider.calls[-1]
        envelope = json.loads(user_message)
        prompt_text = envelope["prompt_exacto_usuario"]
        assert "ENTIDAD EN FOCO: Banda del Cuervo" in prompt_text
        assert "RAÍCES" in prompt_text and "ENTORNO" in prompt_text and "BROTES" in prompt_text
        assert "¿Un mecenas?" in prompt_text
        assert "[fantasma/no-canon" in prompt_text
        assert "fantasma" in system_prompt  # instrucción: intención, no sostén

    def test_rewatering_includes_previous_reading(self):
        provider = FakeWateringProvider()
        project_service, watering = _setup(provider)
        entity = _entity(project_service, "Banda del Cuervo")
        assert isinstance(watering.water_entity(entity.id), Ok)
        assert isinstance(watering.water_entity(entity.id), Ok)

        _, user_message = provider.calls[-1]
        prompt_text = json.loads(user_message)["prompt_exacto_usuario"]
        assert "ÚLTIMO RIEGO" in prompt_text

    def test_without_provider_fails_clearly(self):
        project_service, watering = _setup(provider=None)
        entity = _entity(project_service, "Sola")
        result = watering.water_entity(entity.id)
        assert isinstance(result, Error)
        assert "IA no configurada" in result.error

    def test_unconfigured_default_provider_fails_clearly(self):
        project_service = ProjectService()
        project_service.create("Sin IA")
        ai_service = AIJobService()  # proveedor simulado por defecto, no permitido
        watering = WateringService(project_service, ai_job_service=ai_service)
        entity = _entity(project_service, "Sola")
        result = watering.water_entity(entity.id)
        assert isinstance(result, Error)
        assert "IA no configurada" in result.error

    def test_invalid_payload_shape_registers_nothing(self):
        provider = FakeWateringProvider(payload={"summary": "sin scores"})
        project_service, watering = _setup(provider)
        entity = _entity(project_service, "Banda")

        result = watering.water_entity(entity.id)
        assert isinstance(result, Error)
        assert "scores" in result.error or "métrica" in result.error
        assert project_service.active_project.watering_diagnostics == []

    def test_non_json_answer_registers_nothing(self):
        provider = FakeWateringProvider(raw_text="esto no es json")
        project_service, watering = _setup(provider)
        entity = _entity(project_service, "Banda")

        result = watering.water_entity(entity.id)
        assert isinstance(result, Error)
        assert project_service.active_project.watering_diagnostics == []

    def test_paused_entity_never_reaches_the_provider(self):
        provider = FakeWateringProvider()
        project_service, watering = _setup(provider)
        entity = _entity(project_service, "Dormida")
        watering.pause(entity.id)

        result = watering.water_entity(entity.id)
        assert isinstance(result, Error)
        assert "secada" in result.error.lower()
        assert provider.calls == []

    def test_ghost_never_reaches_the_provider(self):
        provider = FakeWateringProvider()
        project_service, watering = _setup(provider)
        ghost = _entity(project_service, "¿Algo?", canon_state=CanonState.FANTASMA)

        result = watering.water_entity(ghost.id)
        assert isinstance(result, Error)
        assert provider.calls == []


@pytest.mark.application
class TestEstimate:
    def test_single_small_entity_is_cheap(self):
        project_service, watering = _setup(FakeWateringProvider())
        entity = _entity(project_service, "Pequeña")
        result = watering.estimate([entity.id])
        assert isinstance(result, Ok)
        assert result.value.entity_count == 1
        assert result.value.cost_class == "bajo"
        assert result.value.estimated_input_tokens > 0

    def test_batch_size_bumps_cost_class(self):
        project_service, watering = _setup(FakeWateringProvider())
        ids = [_entity(project_service, f"E{i}").id for i in range(20)]
        result = watering.estimate(ids)
        assert isinstance(result, Ok)
        assert result.value.entity_count == 20
        assert result.value.cost_class in ("medio", "alto")

    def test_ineligible_ids_are_skipped(self):
        project_service, watering = _setup(FakeWateringProvider())
        entity = _entity(project_service, "Real")
        ghost = _entity(project_service, "¿Fantasma?", canon_state=CanonState.FANTASMA)
        result = watering.estimate([entity.id, ghost.id, "desconocida"])
        assert isinstance(result, Ok)
        assert result.value.entity_count == 1
