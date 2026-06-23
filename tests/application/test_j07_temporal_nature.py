"""BETA1-J07 — Naturaleza temporal: prompt, staging y aplicación en servicios."""

from __future__ import annotations

import pytest

from packages.application.ai_jobs import AIJob, AIJobType, stage_results
from packages.application.command_prompts import system_prompt_for_intent
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.domain.result import Ok
from packages.domain.temporal_models import TemporalNature


@pytest.fixture
def ps():
    svc = ProjectService()
    svc.create("Proyecto J07")
    return svc


# ── Prompt ─────────────────────────────────────────────────────────────────


def test_prompt_mentions_temporal_nature_and_eternal():
    prompt = system_prompt_for_intent("generate_entities")
    assert "temporal_nature" in prompt
    assert "eterno" in prompt.lower()


# ── Staging ──────────────────────────────────────────────────────────────


def _job(t):
    return AIJob(type=t, prompt="x")


def test_staging_propagates_nature_for_entity():
    payload = {
        "hojas": [
            {"name": "Ángel", "entity_type": "criatura", "temporal_nature": "eterno"}
        ]
    }
    out = stage_results(payload, _job(AIJobType.GENERATE_ENTITIES))
    ang = next(c for c in out["candidates"] if c["proposed_data"].get("name") == "Ángel")
    assert ang["proposed_data"]["temporal_nature"] == "eterno"


def test_staging_sanitizes_bad_nature_to_mortal():
    payload = {"hojas": [{"name": "X", "entity_type": "personaje", "temporal_nature": "???"}]}
    out = stage_results(payload, _job(AIJobType.GENERATE_ENTITIES))
    ent = next(c for c in out["candidates"] if c["proposed_data"].get("name") == "X")
    assert ent["proposed_data"]["temporal_nature"] == "mortal"


# ── Servicios: aplicar la naturaleza ─────────────────────────────────────


def test_create_eternal_has_no_mortal_birth(ps):
    svc = EntityService(ps, ps.store)
    res = svc.create_entity(
        {
            "name": "Ángel",
            "entity_type": "criatura",
            "birth_year": 650,  # la IA podría haberlo puesto; la naturaleza manda
            "temporal_nature": "eterno",
        }
    )
    assert isinstance(res, Ok)
    span = res.value.life_span
    assert span.nature is TemporalNature.ETERNO
    assert span.start_year is None  # NO nace en 650
    assert res.value.birth_year is None
    assert span.ongoing is True and span.end is None


def test_create_immortal_keeps_birth_but_no_death(ps):
    svc = EntityService(ps, ps.store)
    res = svc.create_entity(
        {
            "name": "Vampiro",
            "entity_type": "criatura",
            "birth_year": 1200,
            "death_year": 1400,  # se descarta: un inmortal no muere
            "temporal_nature": "inmortal",
        }
    )
    assert isinstance(res, Ok)
    span = res.value.life_span
    assert span.start_year == 1200
    assert span.end is None and res.value.death_year is None


def test_enforce_dating_allows_eternal_without_year(ps):
    svc = EntityService(ps, ps.store)
    res = svc.create_entity(
        {"name": "Primordial", "entity_type": "criatura", "temporal_nature": "eterno"},
        enforce_dating=True,
    )
    assert isinstance(res, Ok)  # un eterno está 'datado' por naturaleza


def test_update_sets_temporal_nature(ps):
    svc = EntityService(ps, ps.store)
    created = svc.create_entity(
        {"name": "Mortal", "entity_type": "personaje", "birth_year": 10}
    )
    assert isinstance(created, Ok)
    upd = svc.update_entity(created.value.id, {"temporal_nature": "eterno"})
    assert isinstance(upd, Ok)
    assert upd.value.life_span.nature is TemporalNature.ETERNO
    assert upd.value.birth_year is None  # pasa a origen primordial


def test_create_mortal_default_unchanged(ps):
    svc = EntityService(ps, ps.store)
    res = svc.create_entity(
        {"name": "Normal", "entity_type": "personaje", "birth_year": 50}
    )
    assert isinstance(res, Ok)
    assert res.value.life_span.nature is TemporalNature.MORTAL
    assert res.value.birth_year == 50
