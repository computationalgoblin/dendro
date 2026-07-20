"""BETA2-WIKI-12: QA E2E del circuito de la wiki (índice → navegación → canon intacto).

Verifica las invariantes del reencuadre: el índice es siempre completo; la navegación
arma contexto sin tocar canon; la IA NUNCA muta canon; y la app funciona sin proveedor
IA (índice + lint deterministas siguen).
"""

import json
from dataclasses import dataclass

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.wiki_index_service import WikiIndexService
from packages.application.wiki_lint_service import WikiLintService
from packages.application.wiki_navigator import NavigationRequest, WikiNavigator
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import MemoryFreshness, MemoryTargetKind, NarrativeMemory
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


@dataclass
class _FakeProjectService:
    active_project: Project = None


class _NavProvider(AIProvider):
    """Navega: ronda 1 abre la página de Ana y lee el canon de Beto; ronda 2 enough."""

    def __init__(self):
        self._responses = [
            {"reads": [{"op": "open_page", "kind": "entity", "id": "e1"},
                       {"op": "read_canon", "kind": "entity", "id": "e2"}], "enough": False},
            {"reads": [], "enough": True},
        ]

    @property
    def provider_name(self):
        return "nav"

    def chat(self, system_prompt, user_message, timeout=None, **kwargs):
        payload = self._responses.pop(0) if self._responses else {"reads": [], "enough": True}
        return json.dumps(payload, ensure_ascii=False), None


def _project():
    p = Project(id="p", name="Reino")
    p.entities.append(NarrativeEntity(id="e1", name="Ana", brief_description="Reina."))
    p.entities.append(NarrativeEntity(id="e2", name="Beto", brief_description="Aliado."))
    p.relations.append(NarrativeRelation(id="r1", source_id="e1", target_id="e2"))
    p.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY, target_id="e1",
            resumen_editorial="Ana, reina que conspira.", cuerpo="Ana perdió el trono.",
            freshness=MemoryFreshness.REGADA,
        )
    )
    return _FakeProjectService(active_project=p), p


@pytest.mark.application
def test_index_is_always_complete():
    ps, p = _project()
    index = WikiIndexService().build_index(p).value
    # 2 entidades + 1 relación (sin anillos) aparecen todas, aunque solo una tenga página.
    kinds = [e.kind for e in index.entries]
    assert kinds.count("entity") == 2 and kinds.count("relation") == 1
    assert index.counts["con_pagina"] == 1


@pytest.mark.application
def test_navigation_gathers_context_without_touching_canon():
    ps, p = _project()
    nav = WikiNavigator(ps, ai_job_service=AIJobService(provider=_NavProvider()))
    res = nav.assemble_context(NavigationRequest(intent="suggest_relations", focus_ids=["e1"]))
    assert isinstance(res, Ok)
    bundle = res.value
    # Trajo la página de Ana (derivada) + el canon de Beto.
    assert any(pg["id"] == "e1" for pg in bundle.pages)
    assert any(c["id"] == "e2" for c in bundle.canon)
    # INVARIANTE: el canon quedó INTACTO (la IA solo leyó; nunca escribe canon).
    assert p.entity_by_id("e1").name == "Ana"
    assert p.entity_by_id("e1").brief_description == "Reina."
    assert p.entity_by_id("e2").brief_description == "Aliado."
    assert len(p.entities) == 2 and len(p.relations) == 1


@pytest.mark.application
def test_works_without_ai_provider():
    ps, p = _project()
    # Índice y lint son deterministas: funcionan sin proveedor IA.
    assert isinstance(WikiIndexService().build_index(p), Ok)
    assert WikiLintService(ps).lint().value.is_clean()
    # La navegación sin proveedor real falla claro (no rompe la app).
    nav = WikiNavigator(ps, ai_job_service=AIJobService())  # simulado → unconfigured
    assert isinstance(nav.assemble_context(NavigationRequest()), Error)


@pytest.mark.application
def test_lint_flags_a_broken_wiki_after_canon_deletion():
    ps, p = _project()
    # Se borra Beto del canon: la relación queda huérfana de destino y el índice lo refleja.
    p.entities = [e for e in p.entities if e.id != "e2"]
    p._index_dirty = True  # invalida el índice O(1) del dominio
    # La página de Ana sigue sana; añadimos una página huérfana para el lint.
    p.narrative_memories.append(
        NarrativeMemory(target_kind=MemoryTargetKind.ENTITY, target_id="e2",
                        resumen_editorial="Beto (borrado)")
    )
    report = WikiLintService(ps).lint().value
    assert any(o.target_id == "e2" for o in report.orphans)
