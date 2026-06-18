"""PA01: presupuestos de contexto por tier."""

from __future__ import annotations

import pytest

from packages.application.context_budget import (
    DEFAULT_TIER,
    INTENT_SECTION_PERCENTAGES,
    INTENT_TO_TIER,
    PROFILE_BY_TIER,
    TIER_INPUT_TOKENS,
    TIER_OUTPUT_TOKENS,
    ContextBudgetManager,
    ContextTier,
)


@pytest.fixture
def mgr():
    return ContextBudgetManager()


def test_rag_retrieval_share_is_positive_and_matches_profile(mgr):
    # PA03: la cuota RAG = suma de % de las secciones nutridas por retrieval.
    from packages.application.context_budget import _RAG_RETRIEVAL_SECTIONS

    profile = mgr.section_percentages("create_ring_template")
    expected = sum(v for k, v in profile.items() if k in _RAG_RETRIEVAL_SECTIONS)
    assert mgr.rag_retrieval_share("create_ring_template") == pytest.approx(expected)
    assert 0.0 < mgr.rag_retrieval_share("create_ring_template") < 1.0


@pytest.mark.parametrize(
    "intent,expected",
    [
        ("improve_text", ContextTier.FAST_LOCAL),
        ("generate_entities", ContextTier.BALANCED),
        ("generate_text", ContextTier.BALANCED),
        ("suggest_relations", ContextTier.CAUSAL),
        ("analyze_coherence", ContextTier.CAUSAL),
        ("propose_milestones", ContextTier.CAUSAL),
        ("expand_worldbuilding", ContextTier.SUBGRAPH),
        ("freeform_planning", ContextTier.SUBGRAPH),
        ("review_graph", ContextTier.GLOBAL),
        ("import_document", ContextTier.MASSIVE),
    ],
)
def test_tier_assignment(mgr, intent, expected):
    assert mgr.tier_for(intent) is expected


def test_unknown_intent_falls_back_to_default_tier(mgr):
    assert mgr.tier_for("intento_inexistente") is DEFAULT_TIER
    assert mgr.tier_for("unknown") is ContextTier.BALANCED


def test_tier_accepts_enum_like_intent(mgr):
    class _Fake:
        value = "suggest_relations"

    assert mgr.tier_for(_Fake()) is ContextTier.CAUSAL


def test_input_budget_uses_tier_when_no_override(mgr):
    assert mgr.input_budget("generate_entities") == TIER_INPUT_TOKENS[ContextTier.BALANCED]
    assert mgr.input_budget("suggest_relations") == 40_000


def test_input_budget_honors_tuner_override_literally(mgr):
    # El override del tuner manda tal cual (control fino del usuario).
    assert mgr.input_budget("suggest_relations", override_tokens=5_000) == 5_000
    assert mgr.input_budget("suggest_relations", override_tokens=0) == 40_000
    assert mgr.input_budget("suggest_relations", override_tokens=None) == 40_000


def test_output_budget_per_tier(mgr):
    assert mgr.output_budget("improve_text") == TIER_OUTPUT_TOKENS[ContextTier.FAST_LOCAL]
    assert mgr.output_budget("suggest_relations") == 6_000
    assert mgr.output_budget("review_graph") == 12_000


def test_section_percentages_returns_profile(mgr):
    causal = mgr.section_percentages("suggest_relations")
    assert causal == PROFILE_BY_TIER[ContextTier.CAUSAL]
    # La selección pesa más en CAUSAL.
    assert causal["seleccion"] >= max(causal["directivas"], causal["menciones"])


def test_unknown_intent_section_percentages_uses_default(mgr):
    assert mgr.section_percentages("intento_inexistente") == PROFILE_BY_TIER[DEFAULT_TIER]


def test_all_profiles_sum_to_one():
    for tier, profile in PROFILE_BY_TIER.items():
        assert abs(sum(profile.values()) - 1.0) < 1e-9, f"perfil {tier} no suma 1.0"


def test_intent_section_percentages_covers_every_intent():
    assert set(INTENT_SECTION_PERCENTAGES) == set(INTENT_TO_TIER)
    for intent, tier in INTENT_TO_TIER.items():
        assert INTENT_SECTION_PERCENTAGES[intent] is PROFILE_BY_TIER[tier]


def test_tiers_increase_monotonically():
    order = [
        ContextTier.FAST_LOCAL,
        ContextTier.BALANCED,
        ContextTier.CAUSAL,
        ContextTier.SUBGRAPH,
        ContextTier.GLOBAL,
        ContextTier.MASSIVE,
    ]
    inputs = [TIER_INPUT_TOKENS[t] for t in order]
    outputs = [TIER_OUTPUT_TOKENS[t] for t in order]
    assert inputs == sorted(inputs)
    assert outputs == sorted(outputs)
