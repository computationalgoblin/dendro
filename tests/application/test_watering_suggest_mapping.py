"""Sugerir X → jobs existentes con foco_hint (BETA2-FOCO-06).

Cada sugerencia lanza el job correcto con el hint de zona en context_scope; el
hint llega a la metadata de los candidatos staged y NADA muta canon.
"""

from __future__ import annotations

import json

import pytest

from packages.application.ai_jobs import AIJobService, AIJobType
from packages.application.history_service import HistoryService
from packages.application.project_service import ProjectService
from packages.application.watering_service import WateringService
from packages.domain.entity import CanonState, NarrativeEntity
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


class SuggestProvider(AIProvider):
    provider_name = "fake_suggest"
    model = "fake-model-1"

    def __init__(self, source_id: str = "", target_id: str = "", entity_name: str = ""):
        self.source_id = source_id
        self.target_id = target_id
        self.entity_name = entity_name
        self.calls: list[tuple[str, str]] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append((system_prompt, user_message))
        text = user_message.lower()
        if "arraigo" in text:
            # Propuesta por NOMBRE (la vía de producción): se resuelve al aceptar,
            # sin depender del filtro allowed_ids del contexto staged.
            payload = {
                "summary": "Sostén propuesto",
                "relations": [
                    {
                        "source_name": "Guerra del Norte",
                        "target_name": "Banda del Cuervo",
                        "relation_type": "causo",
                        "description": "La guerra explica a la banda.",
                    }
                ],
            }
        elif "iluminación" in text or "iluminacion" in text:
            payload = {
                "summary": "Brotes propuestos",
                "entities": [
                    {
                        "name": "Leyenda del Cuervo",
                        "entity_type": "trama",
                        "brief_description": "Historia derivada de la banda.",
                    }
                ],
            }
        else:  # nutrición / calidad → ediciones de texto
            payload = {
                "summary": "Ediciones propuestas",
                "entity_edits": [
                    {
                        "entity_name": self.entity_name,
                        "field": "extended_description",
                        "proposed_value": "Versión más rica y coherente del cuerpo.",
                        "rationale": "Desarrolla el interior.",
                    }
                ],
            }
        return json.dumps(payload, ensure_ascii=False), None


def _setup():
    project_service = ProjectService()
    project_service.create("Sugerencias")
    center = NarrativeEntity(name="Banda del Cuervo")
    cause = NarrativeEntity(name="Guerra del Norte")
    project_service.active_project.entities.extend([center, cause])
    project_service.active_project.touch()
    provider = SuggestProvider(
        source_id=cause.id, target_id=center.id, entity_name=center.name
    )
    ai_service = AIJobService(
        provider=provider, project_provider=lambda: project_service.active_project
    )
    watering = WateringService(
        project_service, ai_job_service=ai_service, history_service=HistoryService(project_service)
    )
    return project_service, watering, center, provider


_EXPECTED = {
    "arraigo": (AIJobType.SUGGEST_RELATIONS, "raices"),
    "nutrida": (AIJobType.EDIT_ENTITIES, "drawer"),
    "iluminada": (AIJobType.GENERATE_ENTITIES, "brotes"),
    "calidad": (AIJobType.EDIT_ENTITIES, "drawer"),
}


@pytest.mark.application
class TestSuggestMapping:
    @pytest.mark.parametrize("metric", sorted(_EXPECTED))
    def test_each_metric_maps_to_job_and_zone_hint(self, metric):
        project_service, watering, center, _ = _setup()
        project = project_service.active_project
        entities_before = len(project.entities)
        relations_before = len(project.relations)

        result = watering.suggest(center.id, metric)
        assert isinstance(result, Ok), getattr(result, "error", None)
        job = result.value
        expected_type, expected_zone = _EXPECTED[metric]
        assert job.type == expected_type

        hint = job.context_scope["foco_hint"]
        assert hint == {"zone": expected_zone, "metric": metric, "center_entity_id": center.id}

        candidates = job.result.get("candidates") or []
        assert candidates, f"Sugerir {metric} debe stagear candidatos revisables"
        for candidate in candidates:
            assert candidate["metadata"]["context_scope"]["foco_hint"]["zone"] == expected_zone

        # Nada muta canon: las Semillas son solo propuestas staged.
        assert len(project.entities) == entities_before
        assert len(project.relations) == relations_before

    def test_previous_weak_reading_feeds_the_prompt(self):
        project_service, watering, center, provider = _setup()
        from packages.domain.watering import WateringDiagnostic

        watering.register_diagnostic(
            WateringDiagnostic(
                entity_id=center.id,
                scores={"arraigo": 12, "nutrida": 80, "iluminada": 40, "relevancia": 50},
                summary="Flota sin causas.",
                metric_explanations={"arraigo": "No hay contexto previo que la explique."},
            )
        )
        assert isinstance(watering.suggest(center.id, "arraigo"), Ok)
        _, user_message = provider.calls[-1]
        prompt_text = json.loads(user_message)["prompt_exacto_usuario"]
        assert "Diagnóstico previo de arraigo" in prompt_text
        assert "12" in prompt_text

    def test_guards(self):
        project_service, watering, center, provider = _setup()
        ghost = NarrativeEntity(name="¿Algo?", canon_state=CanonState.FANTASMA)
        project_service.active_project.entities.append(ghost)
        project_service.active_project.touch()

        assert isinstance(watering.suggest(center.id, "inventada"), Error)
        assert isinstance(watering.suggest("desconocida", "arraigo"), Error)
        assert isinstance(watering.suggest(ghost.id, "arraigo"), Error)
        watering.pause(center.id)
        assert isinstance(watering.suggest(center.id, "arraigo"), Error)
        assert provider.calls == []

    def test_without_provider_fails_clearly(self):
        project_service = ProjectService()
        project_service.create("Sin IA")
        center = NarrativeEntity(name="Sola")
        project_service.active_project.entities.append(center)
        project_service.active_project.touch()
        watering = WateringService(project_service, ai_job_service=None)

        result = watering.suggest(center.id, "arraigo")
        assert isinstance(result, Error)
        assert "IA no configurada" in result.error
