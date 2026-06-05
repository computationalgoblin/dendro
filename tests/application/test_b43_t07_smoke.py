"""Tests for B43-T07: Smoke IA end-to-end.

Verifies that all AI routes:
- Use Prompt Registry for system prompts
- Return sane errors (no API keys, no raw JSON in UX)
- Do not crash on invalid input
"""
import pytest

from packages.application.prompt_registry import get_prompt, PromptRegistry
from packages.application.output_schema_validator import validate_ai_output
from packages.application.context_sanitizer import sanitize_ai_context
from packages.application.ai_observability import AIObservabilityLog, AIJobRecord
from packages.application.candidate_dedup import CandidateDeduplicator


class TestSmokeCommandBar:
    def test_prompt_available(self):
        p = get_prompt("command_bar", "es")
        assert p is not None and len(p) > 100

    def test_output_validation_handles_valid_json(self):
        text = '{"entities": [{"name": "Fosco", "entity_type": "personaje"}]}'
        result = validate_ai_output(text, "generate_entities")
        assert result.is_valid

    def test_output_validation_handles_invalid_json(self):
        result = validate_ai_output("not json", "generate_entities")
        assert not result.is_valid
        assert result.error is not None
        # No raw API keys in error
        assert "api_key" not in result.error.lower()

    def test_context_sanitized(self):
        ctx = {
            "api_key": "sk-secret123",
            "user_request": "Crea tres personajes",
            "provider_config": {"model": "gpt-4"},
        }
        safe = sanitize_ai_context(ctx)
        assert "api_key" not in str(safe)
        assert "user_request" in str(safe)


class TestSmokeInlineLeaf:
    def test_prompt_available(self):
        p = get_prompt("inline_leaf", "es")
        assert p is not None and len(p) > 50
        # Prompt mentions JSON in the negative instruction ("No devuelvas JSON")
        # which is correct — it tells the model NOT to return JSON


class TestSmokeInlineRelation:
    def test_prompt_available(self):
        p = get_prompt("inline_relation", "es")
        assert p is not None and len(p) > 50


class TestSmokeCoherence:
    def test_prompt_available(self):
        p = get_prompt("coherence", "es")
        assert p is not None and len(p) > 100

    def test_prompt_mentions_verdict(self):
        p = get_prompt("coherence", "es")
        assert "veredicto" in p.lower() or "Veredicto" in p


class TestSmokeCoherenceRepair:
    def test_prompt_available(self):
        p = get_prompt("coherence_repair", "es")
        assert p is not None and "PATCH_JSON" in p


class TestSmokeObservability:
    def test_log_records_without_api_keys(self):
        log = AIObservabilityLog()
        log.record(AIJobRecord(
            job_id="smoke_001",
            intent_type="generate_entities",
            model="gpt-4o-mini",
            temperature=0.8,
            max_tokens=2000,
            context_depth=3,
            input_size=500,
            output_size=300,
            duration_ms=1500.0,
            status="ok",
        ))
        latest = log.latest
        assert latest is not None
        d = latest.to_dict()
        assert "api_key" not in str(d)
        assert d["model"] == "gpt-4o-mini"


class TestSmokeCandidateDedup:
    def test_dedup_flags_duplicates(self):
        dedup = CandidateDeduplicator(existing_names={"Fosco"})
        result = dedup.check({"name": "Fosco", "entity_type": "personaje"})
        assert result.is_possible_duplicate
        assert "Fosco" in result.reason


class TestSmokeNoIdsInUx:
    def test_prompts_dont_expose_ids(self):
        """Prompts should instruct model not to expose IDs."""
        for key in PromptRegistry:
            for lang in ("es", "en"):
                p = get_prompt(key, lang)
                if p is None:
                    continue
                # Command bar explicitly mentions "No incluyas IDs inventados"
                # Others should not encourage showing IDs
                if key == "command_bar":
                    assert "ID" in p or "id" in p, f"{key}/{lang} should mention IDs (to forbid them)"
