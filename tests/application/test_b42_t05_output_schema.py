"""Tests for B42-T05: Output schema validation.

Validates that JSON output from command bar is checked per intent type
and that invalid JSON doesn't crash the system.
"""
import pytest

from packages.application.output_schema_validator import (
    validate_ai_output,
    ValidationResult,
    EXPECTED_SCHEMAS,
)


class TestSchemaRegistry:
    def test_entity_schema_exists(self):
        assert "generate_entities" in EXPECTED_SCHEMAS

    def test_tree_schema_exists(self):
        assert "generate_trees" in EXPECTED_SCHEMAS

    def test_relation_schema_exists(self):
        assert "generate_relations" in EXPECTED_SCHEMAS

    def test_coherence_schema_exists(self):
        assert "coherence" in EXPECTED_SCHEMAS

    def test_edit_schema_exists(self):
        assert "edit_entities" in EXPECTED_SCHEMAS

    def test_import_extraction_schema_exists(self):
        assert "import_extraction" in EXPECTED_SCHEMAS


class TestValidJson:
    def test_valid_entity_output(self):
        text = '{"entities": [{"name": "Fosco", "entity_type": "personaje"}]}'
        result = validate_ai_output(text, "generate_entities")
        assert result.is_valid
        assert result.parsed is not None
        assert len(result.parsed["entities"]) == 1

    def test_valid_relation_output(self):
        text = '{"relations": [{"source_name": "A", "relation_type": "es_aliado_de", "target_name": "B"}]}'
        result = validate_ai_output(text, "generate_relations")
        assert result.is_valid

    def test_valid_coherence_output(self):
        text = '{"verdict": "coherent", "findings": [], "severity": "ok"}'
        result = validate_ai_output(text, "coherence")
        assert result.is_valid

    def test_valid_import_extraction_output(self):
        text = '{"candidates": [{"kind": "entity", "name": "Eldrin"}]}'
        result = validate_ai_output(text, "import_extraction")
        assert result.is_valid


class TestInvalidJson:
    def test_malformed_json_no_crash(self):
        text = "This is not JSON at all"
        result = validate_ai_output(text, "generate_entities")
        assert not result.is_valid
        assert result.error is not None
        assert "JSON" in result.error

    def test_incomplete_json_no_crash(self):
        text = '{"entities": [{"name": "Fosco"'
        result = validate_ai_output(text, "generate_entities")
        assert not result.is_valid
        assert result.error is not None

    def test_empty_json_no_crash(self):
        text = ""
        result = validate_ai_output(text, "generate_entities")
        assert not result.is_valid


class TestSchemaEnforcement:
    def test_entity_missing_name_flagged(self):
        text = '{"entities": [{"entity_type": "personaje"}]}'
        result = validate_ai_output(text, "generate_entities")
        assert not result.is_valid
        assert "name" in result.error.lower()

    def test_relation_missing_source_flagged(self):
        text = '{"relations": [{"relation_type": "x", "target_name": "B"}]}'
        result = validate_ai_output(text, "generate_relations")
        assert not result.is_valid

    def test_freeform_always_valid(self):
        """Freeform text output is always valid — no schema to enforce."""
        text = "The world of Arda is vast and ancient."
        result = validate_ai_output(text, "freeform")
        assert result.is_valid

    def test_unknown_intent_treated_as_freeform(self):
        text = "Some arbitrary text"
        result = validate_ai_output(text, "unknown_intent")
        assert result.is_valid


class TestRetryHint:
    def test_invalid_json_suggests_retry(self):
        text = "Not JSON"
        result = validate_ai_output(text, "generate_entities")
        assert result.retry_hint is not None

    def test_valid_json_no_retry_needed(self):
        text = '{"entities": [{"name": "Fosco", "entity_type": "personaje"}]}'
        result = validate_ai_output(text, "generate_entities")
        assert result.retry_hint is None
