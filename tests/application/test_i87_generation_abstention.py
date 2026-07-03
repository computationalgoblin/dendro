"""I87 — abstención + higiene de calidad, creación libre por defecto.

Verifica sobre el prompt real de ``system_prompt_for_intent`` que la creación conserva la higiene
(propón solo lo que merece ser nodo; pocas; el número es TOPE) sin enjaular: el documento es
inspiración opcional y se puede inventar más allá de él.
"""

from __future__ import annotations

import pytest

from packages.application.command_prompts import system_prompt_for_intent

_GENERATIVE = ("generate_entities", "generate_tree", "suggest_relations", "propose_milestones")


@pytest.mark.parametrize("intent", _GENERATIVE)
def test_free_creation_keeps_hygiene_without_caging(intent: str) -> None:
    prompt = system_prompt_for_intent(intent)  # libre por defecto
    # Higiene de calidad conservada.
    assert "Ante la duda, NO lo propongas" in prompt
    assert "TOPE, no una cuota" in prompt
    # NO enjaula: el documento es inspiración opcional y se puede inventar más allá.
    assert "inspiración OPCIONAL" in prompt
    assert "libertad para inventar" in prompt
    # El anclaje estricto NO está presente en modo libre.
    assert "extrae SOLO lo que el texto respalda" not in prompt
    assert "FUENTE PRIMARIA" not in prompt


def test_expand_worldbuilding_free_by_default() -> None:
    # expand_worldbuilding también crea → hereda la higiene, pero NO enjaula por defecto.
    prompt = system_prompt_for_intent("expand_worldbuilding")
    assert "Ante la duda, NO lo propongas" in prompt
    assert "extrae SOLO lo que el texto respalda" not in prompt


def test_text_intents_carry_neither_rule() -> None:
    # improve_text usa el prompt de escritura inline (sin reglas de nodos).
    prompt = system_prompt_for_intent("improve_text")
    assert "Ante la duda, NO lo propongas" not in prompt
