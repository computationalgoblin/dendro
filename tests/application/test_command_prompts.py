"""Per-function system prompts."""
from __future__ import annotations

import pytest

from packages.application.ai_jobs import AIJobType
from packages.application.command_prompts import has_intent_prompt, system_prompt_for_intent


def test_ring_template_prompt_only_asks_for_rings():
    p = system_prompt_for_intent("create_ring_template")
    assert "PLANTILLA DE ANILLOS" in p
    assert '"rings"' in p
    # It must forbid the generic structural keys for rings.
    assert "NO generes hojas, ramas ni relations" in p


def test_generate_entities_prompt_asks_for_hojas():
    p = system_prompt_for_intent("generate_entities")
    assert "CREAR HOJAS" in p
    assert '"hojas"' in p
    assert "numero_sugerencias" in p


def test_suggest_relations_prompt_asks_for_relations():
    p = system_prompt_for_intent("suggest_relations")
    assert "CREAR RELACIONES" in p
    assert "par_relacion" in p


@pytest.mark.parametrize("intent,needle", [
    (AIJobType.EDIT_ENTITIES, "entity_edits"),
    (AIJobType.EDIT_RELATION, "relation_edits"),
    (AIJobType.EDIT_RING, "ring_edits"),
    (AIJobType.EDIT_MILESTONE, "milestone_edits"),
])
def test_edit_prompts_ask_only_for_their_edit_key(intent, needle):
    p = system_prompt_for_intent(intent.value)
    assert needle in p
    assert "NO crees" in p  # edits never create new elements


def test_walk_prompt_asks_for_multicampo_edit_fields():
    """PLAY-15: el walk pide patches `edit_fields` y prohíbe visibilidad/canon."""
    p = system_prompt_for_intent("chronology_walk_step")
    assert "edit_fields" in p
    assert "PROHIBIDO" in p and "visibilidad" in p
    # La lista blanca queda enumerada para el modelo.
    assert "extended_description" in p and "milestone_type" in p


def test_retired_intents_fall_back_to_generic():
    # Limpieza post-WIKI: los specs de análisis/planning se podaron; caen al genérico.
    for retired in ("analyze_coherence", "repair_coherence", "review_graph",
                    "explain_from_causes", "expand_worldbuilding", "freeform_planning"):
        assert not has_intent_prompt(retired)
        assert "TERMINOLOGÍA DE DENDRO" in system_prompt_for_intent(retired)


def test_text_intents_use_inline_writing_prompt():
    p = system_prompt_for_intent("improve_text")
    assert "No devuelvas JSON" in p  # free-text, not JSON


def test_unknown_intent_falls_back_to_generic_command_bar():
    p = system_prompt_for_intent("totally_unknown_intent")
    assert "TERMINOLOGÍA DE DENDRO" in p  # the generic command_bar prompt
    assert not has_intent_prompt("totally_unknown_intent")


def test_live_job_types_have_a_dedicated_prompt():
    # Superficie viva post-WIKI: Regar + Sugerencias + wiki + cronología (+ ediciones).
    for value in ("water_entity", "update_memory", "generate_entities", "suggest_relations",
                  "edit_entities", "chronology_walk_step", "suggest_composite"):
        assert has_intent_prompt(value), f"missing prompt for {value}"
        assert "TERMINOLOGÍA DE DENDRO" not in system_prompt_for_intent(value)
