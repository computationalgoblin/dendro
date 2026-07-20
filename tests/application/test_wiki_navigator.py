"""BETA2-WIKI-04: bucle de navegación acotado sobre proveedor single-shot."""

import json
from dataclasses import dataclass

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.wiki_navigator import NavigationRequest, WikiNavigator
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import (
    MemoryFreshness,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


class _FakeProvider(AIProvider):
    """Proveedor de un turno con una cola de respuestas JSON scripteadas."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    @property
    def provider_name(self):
        return "fake"

    def chat(self, system_prompt, user_message, timeout=None, **kwargs):
        self.calls += 1
        payload = self._responses.pop(0) if self._responses else {"reads": [], "enough": True}
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return text, None


@dataclass
class _FakeProjectService:
    active_project: Project = None


def _project():
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Ana", brief_description="Reina en el exilio."))
    p.entities.append(NarrativeEntity(id="e2", name="Beto", brief_description="Aliado leal."))
    p.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY,
            target_id="e1",
            resumen_editorial="Ana, reina que conspira.",
            cuerpo="Ana perdió el trono y busca aliados.",
            freshness=MemoryFreshness.REGADA,
        )
    )
    return _FakeProjectService(active_project=p)


def _nav(responses):
    ps = _project()
    aijob = AIJobService(provider=_FakeProvider(responses))
    return WikiNavigator(ps, ai_job_service=aijob), aijob


@pytest.mark.application
def test_two_round_loop_reads_then_stops():
    nav, aijob = _nav(
        [
            {"reads": [{"op": "open_page", "kind": "entity", "id": "e1"},
                       {"op": "read_canon", "kind": "entity", "id": "e2"}], "enough": False},
            {"reads": [], "enough": True},
        ]
    )
    res = nav.assemble_context(NavigationRequest(intent="suggest", focus_ids=["e1"]))
    assert isinstance(res, Ok)
    bundle = res.value
    assert bundle.rounds_used == 2
    assert len(bundle.pages) == 1 and bundle.pages[0]["id"] == "e1"
    assert bundle.pages[0]["cuerpo"].startswith("Ana perdió")
    assert len(bundle.canon) == 1 and bundle.canon[0]["id"] == "e2"
    assert bundle.canon[0]["ficha"]["nombre"] == "Beto"


@pytest.mark.application
def test_never_exceeds_max_rounds():
    # El proveedor pide siempre una búsqueda nueva (nunca dice enough).
    nav, _ = _nav(
        [
            {"reads": [{"op": "search", "query": "trono"}], "enough": False},
            {"reads": [{"op": "search", "query": "aliado"}], "enough": False},
            {"reads": [{"op": "search", "query": "reina"}], "enough": False},
            {"reads": [{"op": "search", "query": "exilio"}], "enough": False},
        ]
    )
    res = nav.assemble_context(NavigationRequest(intent="suggest", max_rounds=2))
    assert res.value.rounds_used == 2  # tope duro respetado


@pytest.mark.application
def test_dedup_stops_when_no_new_reads():
    nav, _ = _nav(
        [
            {"reads": [{"op": "read_canon", "kind": "entity", "id": "e1"}], "enough": False},
            {"reads": [{"op": "read_canon", "kind": "entity", "id": "e1"}], "enough": False},
        ]
    )
    res = nav.assemble_context(NavigationRequest(max_rounds=5))
    bundle = res.value
    assert bundle.rounds_used == 2  # 2ª ronda repite -> dedup vacío -> para
    assert len(bundle.canon) == 1


@pytest.mark.application
def test_invalid_json_falls_back_with_gathered():
    nav, _ = _nav(
        [
            {"reads": [{"op": "open_page", "kind": "entity", "id": "e1"}], "enough": False},
            "esto no es json",
        ]
    )
    res = nav.assemble_context(NavigationRequest(max_rounds=5))
    bundle = res.value
    assert len(bundle.pages) == 1  # lo reunido antes del fallo se conserva
    assert any("no interpretable" in n for n in bundle.notes)


@pytest.mark.application
def test_budget_truncates():
    nav, _ = _nav(
        [
            {"reads": [{"op": "open_page", "kind": "entity", "id": "e1"}], "enough": False},
        ]
    )
    res = nav.assemble_context(NavigationRequest(token_budget=1))  # presupuesto ínfimo
    assert res.value.truncated is True
    assert res.value.pages == []  # no cabía


@pytest.mark.application
def test_search_returns_index_hits_as_notes():
    nav, _ = _nav(
        [
            {"reads": [{"op": "search", "query": "reina exilio"}], "enough": False},
            {"reads": [], "enough": True},
        ]
    )
    res = nav.assemble_context(NavigationRequest())
    assert any("búsqueda" in n and "entity:e1" in n for n in res.value.notes)


@pytest.mark.application
def test_invalid_op_and_unknown_id_are_ignored():
    nav, _ = _nav(
        [
            {"reads": [{"op": "delete", "kind": "entity", "id": "e1"},
                       {"op": "read_canon", "kind": "entity", "id": "nope"}], "enough": False},
            {"reads": [], "enough": True},
        ]
    )
    res = nav.assemble_context(NavigationRequest())
    bundle = res.value
    assert bundle.pages == [] and bundle.canon == []


@pytest.mark.application
def test_unconfigured_provider_returns_error():
    ps = _project()
    aijob = AIJobService()  # simulado, no permitido -> unconfigured
    nav = WikiNavigator(ps, ai_job_service=aijob)
    res = nav.assemble_context(NavigationRequest())
    assert isinstance(res, Error)
