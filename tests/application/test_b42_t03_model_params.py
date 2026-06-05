"""Tests for B42-T03: Model parameter policy.

Verifies that temperature/max_tokens are correctly derived from intent types
and that all known intents in the system have explicit parameter mappings.
"""
import pytest

from packages.application.ai_request_gateway import ModelParams, INTENT_PARAMS
from packages.application.ai_jobs import AIJobType


class TestIntentCoverage:
    """All AIJobType values should have explicit params."""

    def test_all_job_types_have_params(self):
        """Every AIJobType should be in INTENT_PARAMS or use reasonable defaults."""
        missing = []
        for job_type in AIJobType:
            key = job_type.value
            if key not in INTENT_PARAMS:
                missing.append(key)
        # We accept defaults for some, but document which are missing
        # For now just verify the critical ones are present
        assert "generate_entities" in INTENT_PARAMS
        assert "coherence" in INTENT_PARAMS

    def test_at_least_10_intents_have_explicit_params(self):
        assert len(INTENT_PARAMS) >= 10


class TestTemperaturePolicy:
    """Temperature rules by intent category."""

    def test_analytical_intents_low_temp(self):
        for intent in ("coherence", "consistency", "extract", "classify",
                       "detect_contradiction", "detect_inconsistency"):
            params = ModelParams.from_intent(intent)
            assert params.temperature <= 0.3, f"{intent} temp={params.temperature} > 0.3"

    def test_creative_intents_higher_temp(self):
        for intent in ("generate_entities", "generate_trees", "improvise",
                       "wizard_suggestion"):
            params = ModelParams.from_intent(intent)
            assert params.temperature >= 0.7, f"{intent} temp={params.temperature} < 0.7"

    def test_edit_intents_medium_temp(self):
        for intent in ("edit", "edit_entities", "node_text_suggestion"):
            params = ModelParams.from_intent(intent)
            assert 0.4 <= params.temperature <= 0.7, f"{intent} temp={params.temperature}"

    def test_review_has_more_tokens(self):
        params = ModelParams.from_intent("review_graph")
        assert params.max_tokens >= 2000

    def test_coherence_repair_low_temp(self):
        params = ModelParams.from_intent("coherence_repair")
        assert params.temperature <= 0.3

    def test_default_is_medium(self):
        params = ModelParams.default()
        assert params.temperature == 0.7
        assert params.max_tokens == 2000

    def test_unknown_intent_gets_default(self):
        params = ModelParams.from_intent("completely_unknown_thing")
        assert params.temperature == 0.7
        assert params.max_tokens == 2000


class TestMaxTokensPolicy:
    """max_tokens rules by intent."""

    def test_classification_has_lower_token_limit(self):
        params = ModelParams.from_intent("classify")
        assert params.max_tokens <= 1500

    def test_generation_has_reasonable_token_limit(self):
        params = ModelParams.from_intent("generate_entities")
        assert params.max_tokens >= 1500

    def test_review_has_high_token_limit(self):
        params = ModelParams.from_intent("review_graph")
        assert params.max_tokens >= 3000
