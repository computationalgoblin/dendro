"""BETA2-MEM-11: QA E2E del circuito de Memoria narrativa viva.

Recorre el circuito completo sin UI: editar canon → el motor de impacto marca
Falta regar al dependiente que lo @menciona → Regar regenera su Memoria (auto-aplica)
→ la Memoria vuelve a vigente. Verifica además que la IA NUNCA muta canon y que la
app funciona sin IA.
"""

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
from packages.domain.result import Error, Ok
from packages.domain.structured_reference import ReferenceStatus, StructuredReference
from packages.infrastructure.ai_provider import AIProvider

_WATER = {"scores": {"arraigo": 70, "nutrida": 60, "iluminada": 50}, "summary": "sano"}
_MEMORY = {"resumen_editorial": "Beto, aliado de Ana, ahora dudoso."}


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


def _circuit():
    p = Project(id="p", name="P")
    ana = NarrativeEntity(id="e1", name="Ana", brief_description="Reina.")
    beto = NarrativeEntity(id="e2", name="Beto", brief_description="Aliado.")
    p.entities.extend([ana, beto])
    # Beto @menciona a Ana (referencia estructurada resuelta) → backlink Ana←Beto.
    p.structured_references.append(
        StructuredReference(
            source_kind=MemoryTargetKind.ENTITY, source_id="e2",
            target_kind=MemoryTargetKind.ENTITY, target_id="e1",
            alias="Ana", status=ReferenceStatus.RESUELTA,
        )
    )
    p.touch()
    ps = _FakeProjectService(active_project=p)
    mem = NarrativeMemoryService(ps)
    mem.upsert_memory(MemoryTargetKind.ENTITY, "e2", resumen_editorial="Beto, aliado de Ana.")
    return ps, p, mem


@pytest.mark.application
def test_full_circuit_mention_impact_regar_memory():
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController

    ps, p, mem = _circuit()
    ctrl = EntityController(ps)  # trae impact_service cableado (MEM-04)

    # 1) Editar el canon de Ana → impacto marca Falta regar la Memoria de Beto
    #    (Beto la @menciona: backlink).
    ctrl.update("e1", {"brief_description": "Reina destronada."})
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e2").value.freshness == MemoryFreshness.FALTA_REGAR

    # 2) Regar a Beto → Regar v2 regenera su Memoria en el mismo flujo (auto-aplica).
    aijob_water = AIJobService(provider=_FakeProvider(_WATER, "w"), project_provider=lambda: p)
    aijob_mem = AIJobService(provider=_FakeProvider(_MEMORY, "m"), project_provider=lambda: p)
    watering = WateringService(
        ps, ai_job_service=aijob_water,
        memory_ai_service=MemoryAIService(ps, aijob_mem, memory_service=mem),
    )
    result = watering.water_entity("e2")
    assert isinstance(result, Ok)

    # 3) La Memoria de Beto vuelve a vigente y con contenido nuevo.
    block = mem.get_memory(MemoryTargetKind.ENTITY, "e2").value
    assert block.freshness == MemoryFreshness.REGADA
    assert block.resumen_editorial == "Beto, aliado de Ana, ahora dudoso."

    # 4) La IA NUNCA muto canon: el nombre/canon de las entidades siguen intactos.
    assert p.entity_by_id("e1").name == "Ana"
    assert p.entity_by_id("e2").name == "Beto"
    assert p.entity_by_id("e2").brief_description == "Aliado."


@pytest.mark.application
def test_works_without_ai_provider():
    ps, p, mem = _circuit()
    # CRUD de Memoria e impacto son deterministas (sin IA).
    assert isinstance(mem.get_memory(MemoryTargetKind.ENTITY, "e2"), Ok)
    assert isinstance(mem.delete_memory(MemoryTargetKind.ENTITY, "e2"), Ok)
    # Regar sin proveedor real (simulated) falla claro, sin romper la app.
    aijob = AIJobService(project_provider=lambda: p)  # simulated → unconfigured
    watering = WateringService(
        ps, ai_job_service=aijob, memory_ai_service=MemoryAIService(ps, aijob, memory_service=mem)
    )
    result = watering.water_entity("e2")
    assert isinstance(result, Error)  # aviso recuperable, no excepción


@pytest.mark.application
def test_ai_memory_output_never_declares_canon():
    """La salida IA de Memoria no crea entidades/relaciones/hitos (normalizador)."""
    from packages.application.memory_payload import normalize_memory_payload

    data = normalize_memory_payload(
        {
            "resumen_editorial": "ok",
            "entities": [{"name": "Inventada"}],  # el modelo intenta colar canon…
            "relations": [{"x": 1}],
        }
    ).value
    # …y el normalizador solo conserva secciones editoriales (nunca canon).
    assert set(data.keys()) == {
        "resumen_editorial", "estado_actual", "cuerpo", "notas_causales",
        "issues", "citations", "wikilinks", "tags",
    }
    assert "entities" not in data and "relations" not in data
