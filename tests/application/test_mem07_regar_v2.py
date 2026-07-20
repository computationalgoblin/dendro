"""BETA2-MEM-07: Regar v2 — regar una entidad actualiza su Memoria (mismo flujo)."""

import json
from dataclasses import dataclass

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.memory_ai_service import MemoryAIService
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.watering_service import WateringService
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.infrastructure.ai_provider import AIProvider

_WATER = {"scores": {"arraigo": 70, "nutrida": 60, "iluminada": 50}, "summary": "estado sano"}
_MEMORY = {
    "resumen_editorial": "Ana, reina exiliada; su regreso amenaza el orden.",
    "issues": [{"kind": "hueco", "texto": "Falta su motivación profunda"}],
}


class _FakeProvider(AIProvider):
    def __init__(self, payload, name="fake"):
        self._payload = payload
        self._name = name

    @property
    def provider_name(self):
        return self._name

    def chat(self, system_prompt, user_message, timeout=None):
        return json.dumps(self._payload, ensure_ascii=False), None


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _setup(*, with_memory=True):
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Ana"))
    p.touch()
    ps = _FakeProjectService(active_project=p)
    aijob_water = AIJobService(provider=_FakeProvider(_WATER, "fake_water"), project_provider=lambda: ps.active_project)
    mem_svc = NarrativeMemoryService(ps)
    memory_ai = None
    if with_memory:
        aijob_mem = AIJobService(provider=_FakeProvider(_MEMORY, "fake_mem"), project_provider=lambda: ps.active_project)
        memory_ai = MemoryAIService(ps, aijob_mem, memory_service=mem_svc)
    watering = WateringService(ps, ai_job_service=aijob_water, memory_ai_service=memory_ai)
    return watering, mem_svc, ps


@pytest.mark.application
def test_watering_updates_memory_in_same_flow():
    watering, mem_svc, _ = _setup()
    result = watering.water_entity("e1")
    assert isinstance(result, Ok)  # el diagnóstico de riego sigue funcionando
    block = mem_svc.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert block is not None
    assert block.freshness == MemoryFreshness.REGADA
    assert block.resumen_editorial.startswith("Ana")
    assert block.issues[0].texto == "Falta su motivación profunda"


@pytest.mark.application
def test_watering_without_memory_service_still_works():
    watering, mem_svc, _ = _setup(with_memory=False)
    result = watering.water_entity("e1")
    assert isinstance(result, Ok)
    assert mem_svc.get_memory(MemoryTargetKind.ENTITY, "e1").value is None  # sin Memoria


@pytest.mark.application
def test_watering_skips_memory_when_already_fresh():
    watering, mem_svc, _ = _setup()
    # Memoria ya vigente (REGADA) editada a mano.
    mem_svc.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="version manual")
    watering.water_entity("e1")
    # No se regenera una Memoria ya vigente (coste acotado, per-entidad).
    assert mem_svc.get_memory(MemoryTargetKind.ENTITY, "e1").value.resumen_editorial == "version manual"


@pytest.mark.application
def test_watering_regenerates_when_falta_regar():
    watering, mem_svc, _ = _setup()
    mem_svc.upsert_memory(MemoryTargetKind.ENTITY, "e1", resumen_editorial="version vieja")
    mem_svc.mark_falta_regar(MemoryTargetKind.ENTITY, "e1")
    watering.water_entity("e1")
    block = mem_svc.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert block.freshness == MemoryFreshness.REGADA
    assert block.resumen_editorial.startswith("Ana")  # regenerada
