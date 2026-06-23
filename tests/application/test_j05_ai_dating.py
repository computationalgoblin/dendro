"""BETA1-J05 — Datación inline por IA: prompt, staging y selección de inciertas."""

from __future__ import annotations

from packages.application.ai_jobs import AIJob, AIJobType, stage_results
from packages.application.command_prompts import system_prompt_for_intent
from packages.application.temporal_dating import (
    find_uncertain_entities,
    is_uncertain_dating,
)
from packages.domain.entity import NarrativeEntity
from packages.domain.temporal_models import EventTemporality, TemporalPrecision
from packages.domain.temporal_span import TemporalSpan

# ── Prompt: la regla de datación está presente y prohíbe el presente ───────


def test_dating_rule_in_system_prompt():
    prompt = system_prompt_for_intent("generate_entities")
    assert "birth_year" in prompt
    assert "DATACIÓN" in prompt
    assert "presente" in prompt.lower()  # "NUNCA asumas el año presente"


def test_entity_format_requests_years():
    prompt = system_prompt_for_intent("generate_entities")
    assert "birth_year" in prompt and "death_year" in prompt


# ── Staging: las fechas de la IA llegan al proposed_data ───────────────────


def _job(jtype):
    return AIJob(type=jtype, prompt="x")


def test_staging_propagates_entity_years():
    payload = {
        "summary": "s",
        "report": "r",
        "hojas": [
            {"name": "Eldrin", "entity_type": "personaje", "birth_year": -40, "death_year": 12}
        ],
    }
    out = stage_results(payload, _job(AIJobType.GENERATE_ENTITIES))
    ent = next(c for c in out["candidates"] if c["proposed_data"].get("name") == "Eldrin")
    assert ent["proposed_data"]["birth_year"] == -40
    assert ent["proposed_data"]["death_year"] == 12


def test_staging_entity_without_year_is_none_not_present():
    payload = {"hojas": [{"name": "X", "entity_type": "personaje"}]}
    out = stage_results(payload, _job(AIJobType.GENERATE_ENTITIES))
    ent = next(c for c in out["candidates"] if c["proposed_data"].get("name") == "X")
    assert ent["proposed_data"]["birth_year"] is None


def test_staging_propagates_milestone_year():
    payload = {"milestones": [{"title": "Pacto", "year": -150}]}
    out = stage_results(payload, _job(AIJobType.PROPOSE_MILESTONES))
    hito = next(
        c for c in out["candidates"]
        if c["proposed_data"].get("kind") == "causal_milestone"
    )
    assert hito["proposed_data"]["milestone"]["year"] == -150


# ── Selección de entidades inciertas para re-datación ──────────────────────


def test_is_uncertain_detects_pending_and_migrated():
    pending = NarrativeEntity(name="Pendiente")  # sin fecha
    pending.set_life_span(
        TemporalSpan(start=EventTemporality(precision=TemporalPrecision.UNKNOWN))
    )
    assert is_uncertain_dating(pending) is True

    migrated = NarrativeEntity(name="Migrada")
    migrated.set_life_span(
        TemporalSpan(
            start=EventTemporality(
                year=312, precision=TemporalPrecision.UNKNOWN,
                notes="no fundamentado (migración v27)",
            )
        )
    )
    assert is_uncertain_dating(migrated) is True


def test_is_uncertain_false_for_solid_date():
    solid = NarrativeEntity(name="Datada")
    solid.set_life_span(TemporalSpan.from_years(-40, 12))  # precision EXACT
    assert is_uncertain_dating(solid) is False


def test_find_uncertain_entities_filters():
    class _P:
        entities = []

    proj = _P()
    a = NarrativeEntity(name="A")
    a.set_life_span(TemporalSpan.from_years(10, None))  # datada
    b = NarrativeEntity(name="B")  # pendiente
    b.set_life_span(TemporalSpan(start=EventTemporality()))
    proj.entities = [a, b]
    names = {e.name for e in find_uncertain_entities(proj)}
    assert names == {"B"}
