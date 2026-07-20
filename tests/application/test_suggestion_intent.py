"""BETA2-WIKI-13: análisis de intención + generación compuesta de Sugerencias.

Cubre:
- SuggestionIntentService: parseo del plan, fallback determinista (sin IA / JSON inválido),
  tope de acciones, y las proyecciones (output_keys / summary_line / directivas).
- WateringService.compose_generation: arraigo/iluminada rutean a `suggest_composite` con el
  plan; nutrida/calidad mantienen su job por métrica.
- stage_results: un payload compuesto (hojas/ramas/relations/hitos/entity_edits) se estadía
  entero como Semillas revisables. El prompt del job compuesto está registrado.
"""

import json
from dataclasses import dataclass

import pytest

from packages.application.ai_jobs import AIJob, AIJobType, stage_results
from packages.application.command_prompts import has_intent_prompt, system_prompt_for_intent
from packages.application.suggestion_intent_service import (
    IntentActionKind,
    SuggestionIntentService,
)
from packages.application.watering_service import WateringService
from packages.domain.entity import NarrativeEntity
from packages.domain.project import Project
from packages.domain.result import Ok


@dataclass
class _FakeProjectService:
    active_project: Project = None


@dataclass
class _IntentJobService:
    """AIJobService mínimo para el intent-job: raw_json_completion scripteado."""

    response: object = None  # dict/str a devolver, o None → error del proveedor
    unconfigured: bool = False

    def provider_unconfigured(self):
        return self.unconfigured

    def raw_json_completion(self, system_prompt, user_message):
        if self.response is None:
            return None, "sin respuesta"
        text = self.response if isinstance(self.response, str) else json.dumps(self.response)
        return text, None


def _project():
    p = Project(id="p", name="P")
    p.entities.append(NarrativeEntity(id="e1", name="Ana", brief_description="Reina en el exilio."))
    return _FakeProjectService(active_project=p)


def _intent_service(response=None, unconfigured=False):
    return SuggestionIntentService(
        _project(), ai_job_service=_IntentJobService(response, unconfigured)
    )


# ── SuggestionIntentService ─────────────────────────────────────────────────


@pytest.mark.application
def test_intent_plan_parses_mixed_actions():
    svc = _intent_service(
        {
            "acciones": [
                {"tipo": "crear_rama", "descripcion": "Casa de Ana", "objetivo": "Ana"},
                {"tipo": "crear_hoja", "descripcion": "un consejero"},
                {"tipo": "crear_relacion", "descripcion": "aliada de Beto", "objetivo": "Beto"},
            ],
            "resumen": "reforzar el arraigo",
        }
    )
    res = svc.plan("e1", "arraigo", "dame apoyos")
    assert isinstance(res, Ok)
    plan = res.value
    assert [a.kind for a in plan.acciones] == [
        IntentActionKind.CREAR_RAMA,
        IntentActionKind.CREAR_HOJA,
        IntentActionKind.CREAR_RELACION,
    ]
    assert plan.output_keys() == ["ramas", "hojas", "relations"]
    assert plan.summary_line() == "Plan: 1 rama, 1 hoja, 1 relación"
    directives = plan.to_generation_directives()
    assert "crear_rama" in directives and "ramas, hojas, relations" in directives
    assert not plan.from_fallback


@pytest.mark.application
def test_intent_plan_fallback_when_unconfigured():
    svc = _intent_service(unconfigured=True)
    res = svc.plan("e1", "arraigo", "lo que sea")
    assert isinstance(res, Ok)
    plan = res.value
    assert plan.from_fallback
    assert [a.kind for a in plan.acciones] == [IntentActionKind.CREAR_RELACION]  # arraigo


@pytest.mark.application
def test_intent_plan_fallback_iluminada_creates_leaf():
    svc = _intent_service(unconfigured=True)
    plan = svc.plan("e1", "iluminada").value
    assert [a.kind for a in plan.acciones] == [IntentActionKind.CREAR_HOJA]


@pytest.mark.application
def test_intent_plan_fallback_on_bad_json():
    svc = _intent_service(response="esto no es json")
    plan = svc.plan("e1", "arraigo", "x").value
    assert plan.from_fallback


@pytest.mark.application
def test_intent_plan_caps_actions():
    many = {"acciones": [{"tipo": "crear_hoja", "descripcion": str(i)} for i in range(20)]}
    svc = SuggestionIntentService(
        _project(), ai_job_service=_IntentJobService(many), max_actions=4
    )
    plan = svc.plan("e1", "iluminada", "muchas").value
    assert len(plan.acciones) == 4
    assert plan.truncated


@pytest.mark.application
def test_intent_plan_ignores_unknown_kinds():
    svc = _intent_service(
        {"acciones": [{"tipo": "crear_universo"}, {"tipo": "crear_hito", "descripcion": "guerra"}]}
    )
    plan = svc.plan("e1", "arraigo").value
    assert [a.kind for a in plan.acciones] == [IntentActionKind.CREAR_HITO]


# ── WateringService.compose_generation (ruteo) ──────────────────────────────


def _watering(intent_response=None, intent=True):
    ps = _project()
    intent_service = (
        SuggestionIntentService(ps, ai_job_service=_IntentJobService(intent_response))
        if intent
        else None
    )
    return WateringService(ps, navigator=None, intent_service=intent_service)


@pytest.mark.application
def test_compose_arraigo_routes_to_composite():
    svc = _watering({"acciones": [{"tipo": "crear_rama", "descripcion": "Casa"}]})
    res = svc.compose_generation("e1", "arraigo", "crea una rama")
    assert isinstance(res, Ok)
    payload = res.value
    assert payload["job_type"] == "suggest_composite"
    assert "PLAN DE GENERACIÓN" in payload["prompt"]
    assert payload["plan_summary"] == "Plan: 1 rama"


@pytest.mark.application
def test_compose_iluminada_routes_to_composite():
    svc = _watering({"acciones": [{"tipo": "crear_hoja", "descripcion": "brote"}]})
    payload = svc.compose_generation("e1", "iluminada", "").value
    assert payload["job_type"] == "suggest_composite"
    assert payload["plan_summary"]  # no vacío incluso sin petición (analiza siempre)


@pytest.mark.application
def test_compose_nutrida_keeps_edit_entities():
    svc = _watering({"acciones": [{"tipo": "crear_rama"}]})  # el intent no debe usarse
    payload = svc.compose_generation("e1", "nutrida", "algo").value
    assert payload["job_type"] == "edit_entities"
    assert payload["plan_summary"] == ""
    assert "PLAN DE GENERACIÓN" not in payload["prompt"]


@pytest.mark.application
def test_compose_without_intent_service_keeps_metric_job():
    svc = _watering(intent=False)
    payload = svc.compose_generation("e1", "arraigo", "crea una rama").value
    assert payload["job_type"] == "suggest_relations"  # spec de arraigo, sin composición
    assert payload["plan_summary"] == ""


# ── generación compuesta: prompt registrado + staging del mix ───────────────


@pytest.mark.application
def test_suggest_composite_prompt_is_registered():
    prompt = system_prompt_for_intent("suggest_composite")
    assert has_intent_prompt("suggest_composite")
    assert "SUGERENCIA COMPUESTA" in prompt
    # No cae al prompt genérico de command_bar.
    assert prompt != system_prompt_for_intent("intento_inexistente_zzz")


@pytest.mark.application
def test_stage_results_stages_the_whole_mix():
    job = AIJob(type=AIJobType.SUGGEST_COMPOSITE, prompt="compuesta")
    payload = {
        "summary": "mix",
        "hojas": [{"name": "Consejero", "entity_type": "personaje", "brief_description": "leal"}],
        "ramas": [{"name": "Casa de Ana", "entity_type": "faccion", "brief_description": "linaje"}],
        "relations": [
            {"source_name": "Ana", "target_name": "Consejero", "relation_type": "confia_en",
             "description": "vínculo"}
        ],
        "hitos": [{"title": "Coronación", "summary": "asciende", "rationale": "causa"}],
        "entity_edits": [
            {"entity_name": "Ana", "field": "brief_description", "proposed_value": "Reina astuta"}
        ],
    }
    staged = stage_results(payload, job)
    titles = [c["title"] for c in staged["candidates"]]
    assert any(t.startswith("Hoja candidata:") for t in titles)
    assert any(t.startswith("Rama candidata:") for t in titles)
    assert any("Relación" in t for t in titles)
    assert any("Coronación" in t for t in titles)
    assert any(t.startswith("Editar Ana") for t in titles)
    # Cinco tipos → al menos cinco Semillas; ninguna muta canon.
    assert len(staged["candidates"]) >= 5
    assert all(c["metadata"]["canon_auto_mutation"] is False for c in staged["candidates"])
