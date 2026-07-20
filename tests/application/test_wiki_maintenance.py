"""BETA2-WIKI-06: mantenimiento de la wiki al Regar + propagación causal + rebuild."""

import json
from dataclasses import dataclass

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.memory_ai_service import MemoryAIService
from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.narrative_memory_service import NarrativeMemoryService
from packages.application.watering_service import WateringService
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind
from packages.domain.project import Project
from packages.domain.result import Ok
from packages.domain.structured_reference import ReferenceStatus, StructuredReference
from packages.infrastructure.ai_provider import AIProvider

_WATER = {"scores": {"arraigo": 70, "nutrida": 60, "iluminada": 50}, "summary": "sano"}
_PAGE = {
    "resumen_editorial": "Ana, reina en el exilio.",
    "cuerpo": "Ana perdió el trono tras la traición de Beto.",
    "tags": ["realeza", "exilio"],
    "wikilinks": [{"ref_kind": "entity", "ref_id": "e2"}],
}


class _FakeProvider(AIProvider):
    def __init__(self, payload, name="fake"):
        self._payload, self._name = payload, name

    @property
    def provider_name(self):
        return self._name

    def chat(self, system_prompt, user_message, timeout=None, **kwargs):
        return json.dumps(self._payload, ensure_ascii=False), None


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _fresh(mem, tid):
    return mem.get_memory(MemoryTargetKind.ENTITY, tid).value.freshness


def _setup():
    p = Project(id="p", name="P")
    ana = NarrativeEntity(id="e1", name="Ana", brief_description="Reina.")
    beto = NarrativeEntity(id="e2", name="Beto", brief_description="Aliado.")
    p.entities.extend([ana, beto])
    # Beto @menciona a Ana → backlink Ana←Beto (dependiente por mención).
    p.structured_references.append(
        StructuredReference(
            source_kind=MemoryTargetKind.ENTITY, source_id="e2",
            target_kind=MemoryTargetKind.ENTITY, target_id="e1",
            alias="Ana", status=ReferenceStatus.RESUELTA,
        )
    )
    ps = _FakeProjectService(active_project=p)
    mem = NarrativeMemoryService(ps)
    # Beto ya tiene página vigente; al regar a Ana debe quedar Falta regar.
    mem.upsert_memory(
        MemoryTargetKind.ENTITY, "e2", resumen_editorial="Beto, aliado.",
        freshness=MemoryFreshness.REGADA,
    )
    return ps, p, mem


def _watering(ps, p, mem):
    aijob_w = AIJobService(provider=_FakeProvider(_WATER, "w"), project_provider=lambda: p)
    aijob_m = AIJobService(provider=_FakeProvider(_PAGE, "m"), project_provider=lambda: p)
    return WateringService(
        ps,
        ai_job_service=aijob_w,
        memory_ai_service=MemoryAIService(ps, aijob_m, memory_service=mem),
        impact_service=NarrativeImpactService(ps, memory_service=mem),
    )


@pytest.mark.application
def test_regar_writes_page_body_and_tags():
    ps, p, mem = _setup()
    result = _watering(ps, p, mem).water_entity("e1")
    assert isinstance(result, Ok)
    page = mem.get_memory(MemoryTargetKind.ENTITY, "e1").value
    assert page.freshness == MemoryFreshness.REGADA
    assert page.cuerpo == "Ana perdió el trono tras la traición de Beto."
    assert page.tags == ["realeza", "exilio"]
    assert page.wikilinks and page.wikilinks[0].ref_id == "e2"


@pytest.mark.application
def test_regar_marks_related_pages_stale_but_not_itself():
    ps, p, mem = _setup()
    _watering(ps, p, mem).water_entity("e1")
    # La propia página de Ana queda vigente (no se marca a sí misma).
    assert _fresh(mem, "e1") == MemoryFreshness.REGADA
    # La página de Beto (que menciona a Ana) queda Falta regar por propagación.
    assert _fresh(mem, "e2") == MemoryFreshness.FALTA_REGAR


@pytest.mark.application
def test_propagate_change_include_self_flag():
    ps, p, mem = _setup()
    mem.upsert_memory(
        MemoryTargetKind.ENTITY, "e1", resumen_editorial="Ana.", freshness=MemoryFreshness.REGADA
    )
    impact = NarrativeImpactService(ps, memory_service=mem)
    # include_self=False: e1 NO se marca; sí e2 (lo menciona).
    impact.propagate_change(MemoryTargetKind.ENTITY, "e1", include_self=False)
    assert _fresh(mem, "e1") == MemoryFreshness.REGADA
    assert _fresh(mem, "e2") == MemoryFreshness.FALTA_REGAR


@pytest.mark.application
def test_rebuild_wiki_writes_all_entity_pages():
    ps, p, mem = _setup()
    aijob_m = AIJobService(provider=_FakeProvider(_PAGE, "m"), project_provider=lambda: p)
    svc = MemoryAIService(ps, aijob_m, memory_service=mem)
    seen = []
    res = svc.rebuild_wiki(progress_callback=lambda i, n, k, tid: seen.append(tid))
    assert isinstance(res, Ok)
    assert res.value["total"] == 2 and res.value["done"] == 2
    assert set(seen) == {"e1", "e2"}
    # Ambas entidades tienen página con cuerpo.
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e1").value.cuerpo
    assert mem.get_memory(MemoryTargetKind.ENTITY, "e2").value.cuerpo


@pytest.mark.application
def test_rebuild_wiki_is_cancelable():
    ps, p, mem = _setup()
    aijob_m = AIJobService(provider=_FakeProvider(_PAGE, "m"), project_provider=lambda: p)
    svc = MemoryAIService(ps, aijob_m, memory_service=mem)
    res = svc.rebuild_wiki(should_cancel=lambda: True)  # cancela antes del primero
    assert res.value["cancelled"] is True
    assert res.value["done"] == 0
