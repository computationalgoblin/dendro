"""BETA2-WIKI-13: recorte del prompt por TIPO de job.

Antes el ensamblador colgaba el esquema de cronología (`formatos_h05`) por un match difuso
de palabras (`era` es subcadena de muchas), el calendario (`cronologia`) y las secciones de
creación del system base a CASI TODOS los jobs — incluidos riego (diagnóstico) y memoria
(página), que no crean ni datan nada. Ahora se gatea por tipo de job.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from packages.application.command_prompts import system_prompt_for_intent
from packages.application.prompt_assembler import PromptAssembler


def _plan(prompt="haz algo", context=None, intent="suggest_relations"):
    return SimpleNamespace(
        prompt=prompt,
        context=context or {},
        intent=SimpleNamespace(intent_type=SimpleNamespace(value=intent)),
    )


def _msg(plan):
    return json.loads(PromptAssembler().assemble(plan))


# ── formatos_h05: solo jobs de cronología (por tipo, no por keyword) ─────────


@pytest.mark.application
def test_water_entity_omits_chronology_schema_even_with_hint_words():
    # El prompt menciona "hitos en el año 5-6" y "era" — antes arrastraban formatos_h05.
    msg = _msg(_plan(intent="water_entity", prompt="hitos en el año 5-6 de la Era de la Helada"))
    assert "formatos_h05" not in msg


@pytest.mark.application
def test_update_memory_and_composite_omit_chronology_schema():
    assert "formatos_h05" not in _msg(_plan(intent="update_memory", prompt="hito era manera"))
    assert "formatos_h05" not in _msg(_plan(intent="suggest_composite", prompt="crear_hito era"))


@pytest.mark.application
def test_milestone_jobs_still_get_chronology_schema():
    assert "formatos_h05" in _msg(_plan(intent="propose_milestones", prompt="sugiere un hito"))
    assert "formatos_h05" in _msg(_plan(intent="chronology_walk_step", prompt="recorre"))


# ── cronologia: el CALENDARIO (marco temporal) va a TODOS, también riego/memoria ─────
# (WIKI-13b: es el marco para interpretar años/coherencia; solo formatos_h05 —crear hitos—
#  sigue fuera de riego/memoria.)


@pytest.mark.application
def test_watering_and_memory_get_cronologia():
    ctx = {"cronologia": {"nombre": "Calendario de Granada", "era_actual": "Helada"}}
    assert "cronologia" in _msg(_plan(intent="water_entity", context=ctx))
    assert "cronologia" in _msg(_plan(intent="update_memory", context=ctx))


@pytest.mark.application
def test_creation_jobs_keep_cronologia():
    ctx = {"cronologia": {"nombre": "Calendario de Granada"}}
    assert "cronologia" in _msg(_plan(intent="generate_entities", context=ctx))
    assert "cronologia" in _msg(_plan(intent="suggest_composite", context=ctx))


# ── seleccion / contexto_autorizado sin duplicar ────────────────────────────


@pytest.mark.application
def test_selected_ids_live_only_in_seleccion():
    msg = _msg(_plan(context={"selected_entity_ids": ["e1"], "foco_hint": {"zone": "brotes"}}))
    assert msg["seleccion"]["entity_ids"] == ["e1"]
    # foco_hint mantiene vivo contexto_autorizado, pero sin duplicar los ids.
    assert "selected_entity_ids" not in msg.get("contexto_autorizado", {})
    assert msg["contexto_autorizado"]["foco_hint"] == {"zone": "brotes"}


# ── system prompt: sin secciones de creación en riego/memoria ───────────────


@pytest.mark.application
def test_non_creation_system_prompt_drops_creation_sections():
    for intent in ("water_entity", "update_memory"):
        prompt = system_prompt_for_intent(intent)
        assert "DATACIÓN" not in prompt
        assert "NATURALEZA TEMPORAL" not in prompt
        assert "CALIDAD Y ABSTEN" not in prompt
        # El núcleo sigue: terminología + reglas de salida.
        assert "TERMINOLOGÍA" in prompt and "REGLAS DE SALIDA" in prompt


@pytest.mark.application
def test_creation_system_prompt_keeps_full_base():
    prompt = system_prompt_for_intent("generate_entities")
    assert "DATACIÓN" in prompt
    assert "NATURALEZA TEMPORAL" in prompt
    assert "CALIDAD Y ABSTEN" in prompt


@pytest.mark.application
def test_watering_prompt_asks_for_temporal_coherence():
    # WIKI-13b: la coherencia temporal es parte de arraigo y se señala en risks (sin métrica
    # nueva y sin reintroducir las secciones de creación del base).
    prompt = system_prompt_for_intent("water_entity")
    assert "COHERENCIA TEMPORAL" in prompt
    assert "risks" in prompt
    assert "DATACIÓN" not in prompt  # sigue sin la sección de creación
