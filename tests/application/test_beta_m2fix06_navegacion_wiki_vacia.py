"""BETA2-FIX-06 (G2-10): el gasto de la navegacion de la wiki.

Dos hallazgos del beta ronda 2, ambos medidos:

- `suggest`/`compose_generation` mandaban ~91.777 caracteres (~25.500 tokens) por
  llamada — DOCE veces un riego — **aunque la wiki estuviera vacia**: se pagaba por
  navegar un indice donde `con_pagina = 0`, o sea sin una sola pagina que abrir.
- El presupuesto declarado (`token_budget = 4000`) solo media lo TRAIDO; el indice
  re-enviado en cada ronda no entraba en la cuenta.

Aqui se verifica el contrato nuevo (`docs/contracts/wiki_memoria.md` §4.1/§4.2):
wiki sin paginas → cero llamadas al proveedor; wiki con paginas → se navega igual que
antes (no romper WIKI-08); y el mensaje de cada ronda por debajo de un tope DURO.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from packages.application.ai_jobs import AIJobService
from packages.application.watering_service import WateringService
from packages.application.wiki_index_service import WikiIndexService
from packages.application.wiki_navigator import (
    NavigationBundle,
    NavigationRequest,
    WikiNavigator,
)
from packages.domain.entity import NarrativeEntity
from packages.domain.narrative_memory import (
    MemoryFreshness,
    MemoryTargetKind,
    NarrativeMemory,
)
from packages.domain.project import Project
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider


class _FakeProvider(AIProvider):
    """Proveedor de un turno que CUENTA sus llamadas (patron test_wiki_navigator)."""

    def __init__(self, responses=()):
        self._responses = list(responses)
        self.calls = 0
        self.messages: list[str] = []

    @property
    def provider_name(self):
        return "fake"

    def chat(self, system_prompt, user_message, timeout=None, **kwargs):
        self.calls += 1
        self.messages.append(user_message)
        payload = self._responses.pop(0) if self._responses else {"reads": [], "enough": True}
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return text, None


@dataclass
class _FakeProjectService:
    active_project: Project = None


@dataclass
class _CapturingJobService:
    """AIJobService minimo: captura run_focused_job (patron test_wiki_suggestions)."""

    calls: list = field(default_factory=list)

    def provider_unconfigured(self):
        return False

    def run_focused_job(self, job_type, prompt, *, context_scope=None, progress_callback=None):
        self.calls.append({"job_type": job_type, "prompt": prompt, "context_scope": context_scope})
        return Ok("job-ok")


def _proyecto(*, con_pagina: bool) -> Project:
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Ana", brief_description="Reina en el exilio."))
    p.entities.append(NarrativeEntity(id="e2", name="Beto", brief_description="Aliado leal."))
    p.relations.append(
        NarrativeRelation(
            id="r1", source_id="e1", target_id="e2", relation_type=RelationType.ES_ALIADO_DE
        )
    )
    if con_pagina:
        p.narrative_memories.append(
            NarrativeMemory(
                target_kind=MemoryTargetKind.ENTITY,
                target_id="e1",
                resumen_editorial="Ana, reina que conspira.",
                cuerpo="Ana perdio el trono y busca aliados.",
                freshness=MemoryFreshness.REGADA,
            )
        )
    return p


def _navegador(project: Project) -> tuple[WikiNavigator, _FakeProvider]:
    provider = _FakeProvider()
    aijob = AIJobService(provider=provider)
    ps = _FakeProjectService(active_project=project)
    return WikiNavigator(ps, ai_job_service=aijob), provider


def _servicio(project: Project, navigator) -> tuple[WateringService, _CapturingJobService]:
    job = _CapturingJobService()
    svc = WateringService(
        _FakeProjectService(active_project=project), ai_job_service=job, navigator=navigator
    )
    return svc, job


# ── Wiki vacia: cero navegacion, cero coste ──────────────────────────────────


@pytest.mark.application
def test_beta_m2fix06_wiki_sin_paginas_no_llama_al_proveedor():
    nav, provider = _navegador(_proyecto(con_pagina=False))
    res = nav.assemble_context(NavigationRequest(intent="suggest", focus_ids=["e1"]))
    assert isinstance(res, Ok)  # Result, nunca excepcion de flujo
    bundle = res.value
    assert provider.calls == 0  # NINGUNA ronda: raw_json_completion no se ejecuta
    assert bundle.is_empty()
    assert bundle.rounds_used == 0
    assert bundle.skipped_reason  # el motivo viaja: nada de degradacion silenciosa
    assert "página" in bundle.skipped_reason


@pytest.mark.application
def test_beta_m2fix06_suggest_con_wiki_vacia_lanza_el_job_determinista():
    project = _proyecto(con_pagina=False)
    nav, provider = _navegador(project)
    svc, job = _servicio(project, nav)
    result = svc.suggest("e1", "iluminada", peticion="dame un rival")
    assert isinstance(result, Ok)  # la Sugerencia SALE igual
    assert provider.calls == 0  # sin navegacion => sin coste
    scope = job.calls[0]["context_scope"]
    assert "contexto_wiki" not in scope  # el prompt determinista es el plan B
    assert scope["foco_hint"]["center_entity_id"] == "e1"
    assert "PETICIÓN DEL USUARIO" in job.calls[0]["prompt"]


@pytest.mark.application
def test_beta_m2fix06_compose_generation_declara_el_atajo():
    """El usuario tiene que ENTERARSE de que no se navego (criterio heredado de FIX-02)."""
    project = _proyecto(con_pagina=False)
    nav, provider = _navegador(project)
    svc, _job = _servicio(project, nav)
    fases: list[str] = []
    res = svc.compose_generation("e1", "calidad", "algo", progress_callback=fases.append)
    assert isinstance(res, Ok)
    assert provider.calls == 0
    assert res.value["wiki_skipped"]  # el host lo saca por estado + toast
    assert any("sin navegación" in f for f in fases)


# ── Wiki con paginas: se navega como siempre (no romper WIKI-08) ─────────────


@pytest.mark.application
def test_beta_m2fix06_con_pagina_la_navegacion_sigue_corriendo():
    project = _proyecto(con_pagina=True)
    nav, provider = _navegador(project)
    nav.ai_job_service = AIJobService(
        provider=_FakeProvider(
            [
                {"reads": [{"op": "open_page", "kind": "entity", "id": "e1"}], "enough": False},
                {"reads": [], "enough": True},
            ]
        )
    )
    res = nav.assemble_context(NavigationRequest(intent="suggest", focus_ids=["e1"]))
    assert isinstance(res, Ok)
    bundle = res.value
    assert bundle.skipped_reason == ""
    assert bundle.rounds_used == 2
    assert [p["id"] for p in bundle.pages] == ["e1"]
    assert provider.calls == 0  # el proveedor viejo quedo sustituido; ver el nuevo


@pytest.mark.application
def test_beta_m2fix06_suggest_con_pagina_adjunta_contexto_wiki():
    project = _proyecto(con_pagina=True)

    @dataclass
    class _StubNavigator:
        bundle: object = None

        def assemble_context(self, request):
            return Ok(self.bundle)

    bundle = NavigationBundle(pages=[{"kind": "entity", "id": "e1", "resumen": "Ana"}])
    svc, job = _servicio(project, _StubNavigator(bundle=bundle))
    assert isinstance(svc.suggest("e1", "iluminada"), Ok)
    assert "contexto_wiki" in job.calls[0]["context_scope"]


@pytest.mark.application
def test_beta_m2fix06_error_del_navegador_devuelve_result_no_excepcion():
    @dataclass
    class _NavRoto:
        def assemble_context(self, request):
            return Error("proveedor caido")

    project = _proyecto(con_pagina=True)
    svc, job = _servicio(project, _NavRoto())
    assert isinstance(svc.suggest("e1", "iluminada"), Ok)  # la Sugerencia sobrevive
    assert "contexto_wiki" not in job.calls[0]["context_scope"]


# ── Tope de tamano por ronda (el indice no se dispara) ───────────────────────


def _mundo_grande(entidades: int = 800) -> Project:
    """Reproduce el mundo sintetico con el que se midio el ticket."""
    p = Project(id="big", name="Mundo grande")
    for i in range(entidades):
        p.entities.append(
            NarrativeEntity(
                id=f"e{i}",
                name=f"Entidad numero {i}",
                brief_description=(
                    f"Descripcion razonablemente larga de la entidad {i}, con detalles "
                    "narrativos suficientes para que el indice pese lo que pesa de verdad."
                ),
            )
        )
    for i in range(entidades * 2 // 1000 + 1760):
        origen, destino = f"e{i % entidades}", f"e{(i * 7 + 3) % entidades}"
        if origen == destino:
            continue
        p.relations.append(
            NarrativeRelation(
                id=f"r{i}",
                source_id=origen,
                target_id=destino,
                relation_type=RelationType.ES_ALIADO_DE,
                description=f"Relacion {i} entre dos piezas del mundo.",
            )
        )
    # Una sola pagina: basta para que la navegacion NO se cortocircuite.
    p.narrative_memories.append(
        NarrativeMemory(
            target_kind=MemoryTargetKind.ENTITY,
            target_id="e0",
            resumen_editorial="La primera entidad tiene pagina.",
            cuerpo="Cuerpo de la pagina.",
            freshness=MemoryFreshness.REGADA,
        )
    )
    return p


@pytest.mark.application
def test_beta_m2fix06_mensaje_de_ronda_bajo_el_tope_declarado():
    """800 entidades: antes 73.548 caracteres (~21.000 tokens) por ronda."""
    project = _mundo_grande()
    nav, _provider = _navegador(project)
    index = WikiIndexService().build_index(project).value
    assert index.counts["con_pagina"] == 1  # hay pagina: SI se navega
    compact = WikiIndexService().compact_for_prompt(index, max_entries=400, priority_ids=["e0"])
    request = NavigationRequest(intent="suggest", focus_ids=["e0"])
    mensaje = nav._round_message(request, compact, NavigationBundle())
    assert len(mensaje) <= request.max_round_chars
    # El recorte se DECLARA (no se trunca en silencio, contrato §9).
    payload = json.loads(mensaje)
    assert payload["indice"]["recortadas_por_tope"] > 0
    assert "search" in payload["indice"]["nota"]


@pytest.mark.application
def test_beta_m2fix06_mundo_pequeno_no_se_recorta():
    """Un proyecto que cabe viaja entero: el tope no penaliza a quien no lo necesita."""
    project = _proyecto(con_pagina=True)
    nav, _provider = _navegador(project)
    index = WikiIndexService().build_index(project).value
    compact = WikiIndexService().compact_for_prompt(index, max_entries=400)
    request = NavigationRequest(intent="suggest", focus_ids=["e1"])
    mensaje = nav._round_message(request, compact, NavigationBundle())
    assert len(mensaje) <= request.max_round_chars
    payload = json.loads(mensaje)
    assert "recortadas_por_tope" not in payload["indice"]
    assert len(payload["indice"]["entradas"]) == len(index.entries)
