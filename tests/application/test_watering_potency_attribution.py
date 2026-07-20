"""BETA2-STRUCT-09: la IA atribuye la potencialidad causal al Regar.

El detector estructural ya NO infiere el potencial de la topología: lo LEE de la métrica que la
IA atribuye semánticamente durante Regar (`custom_metadata["_causal_potency_basal"]`, §14). Aquí
se prueba que (a) el normalizador del payload de riego deja pasar `potencial_causal` (opcional) y
(b) `WateringService.water_entity` lo escribe en la entidad.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from packages.application.causal_potency import get_annotated_potency
from packages.application.watering_payload import normalize_watering_payload
from packages.application.watering_service import WateringService
from packages.domain.entity import NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Ok


@dataclass
class _FakeProjectService:
    active_project: Project = None


class _FakeAI:
    provider = SimpleNamespace(provider_name="test", model="m")

    def __init__(self, potencial):
        self._potencial = potencial

    def provider_unconfigured(self) -> bool:
        return False

    def run_focused_job(self, job_type, prompt, context_scope=None, progress_callback=None):
        watering = {
            "scores": {"arraigo": 50, "nutrida": 50, "iluminada": 50},
            "summary": "estado ok",
            "metric_explanations": {},
            "risks": [],
        }
        if self._potencial is not None:
            watering["potencial_causal"] = self._potencial
        return Ok(SimpleNamespace(result={"watering": watering}))


# ── normalizador ───────────────────────────────────────────────────────────


def _norm_potency(**extra):
    base = {"scores": {"arraigo": 1, "nutrida": 1, "iluminada": 1}, "summary": "s"}
    return normalize_watering_payload({**base, **extra}).value["potencial_causal"]


@pytest.mark.application
def test_normalizer_passes_optional_potencial_causal():
    assert _norm_potency(potencial_causal=90) == 90
    assert _norm_potency() is None  # ausente → None (opcional)
    assert _norm_potency(potencial_causal="x") is None  # no numérico → None
    assert _norm_potency(potencial_causal=250) == 100  # clamp 0..100


# ── atribución al Regar ──────────────────────────────────────────────────────


@pytest.mark.application
def test_water_entity_attributes_potency_to_entity():
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e", name="Guerra de Granada"))
    svc = WateringService(_FakeProjectService(active_project=p), ai_job_service=_FakeAI(88))
    res = svc.water_entity("e")
    assert isinstance(res, Ok)
    assert get_annotated_potency(p.entity_by_id("e")) == 88


@pytest.mark.application
def test_water_entity_without_potency_leaves_entity_unannotated():
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e", name="Objeto menor"))
    svc = WateringService(_FakeProjectService(active_project=p), ai_job_service=_FakeAI(None))
    res = svc.water_entity("e")
    assert isinstance(res, Ok)
    assert get_annotated_potency(p.entity_by_id("e")) is None
