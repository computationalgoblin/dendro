"""Tests for B42-T02: Context Sanitizer (standalone module).

Tests are more exhaustive than the gateway's built-in sanitization.
Covers nested context, edge cases, and allowlist behavior.
"""
import pytest

from packages.application.context_sanitizer import (
    sanitize_ai_context,
    sanitize_nested,
    BLOCKED_KEYS,
    BLOCKED_PATTERNS,
)


class TestBlockedKeys:
    def test_api_key_blocked(self):
        assert "api_key" in BLOCKED_KEYS

    def test_provider_config_blocked(self):
        assert "provider_config" in BLOCKED_KEYS

    def test_raw_metadata_blocked(self):
        assert "raw_metadata" in BLOCKED_KEYS

    def test_source_ids_blocked(self):
        assert "source_ids" in BLOCKED_KEYS

    def test_password_blocked(self):
        assert "password" in BLOCKED_KEYS

    def test_credentials_blocked(self):
        assert "credentials" in BLOCKED_KEYS


class TestBasicSanitization:
    def test_removes_all_blocked_keys(self):
        ctx = {k: "LEAK" for k in BLOCKED_KEYS}
        result = sanitize_ai_context(ctx)
        for k in BLOCKED_KEYS:
            assert k not in result

    def test_preserves_safe_data(self):
        ctx = {
            "project_name": "Test",
            "genre": "fantasy",
            "tone": "epic",
            "entities": [{"name": "Fosco"}],
        }
        result = sanitize_ai_context(ctx)
        assert result == ctx

    def test_empty_context_returns_empty(self):
        assert sanitize_ai_context({}) == {}

    def test_none_context_returns_empty(self):
        assert sanitize_ai_context(None) == {}


class TestPatternBlocking:
    def test_blocks_key_like_patterns(self):
        ctx = {"x_api_key": "sk-123", "my_secret_token": "abc"}
        result = sanitize_ai_context(ctx)
        assert "x_api_key" not in result
        assert "my_secret_token" not in result

    def test_blocks_env_var_names(self):
        ctx = {
            "NARRATIVE_AI_API_KEY": "sk-xxx",
            "NARRATIVE_AI_BASE_URL": "https://api.example.com",
        }
        result = sanitize_ai_context(ctx)
        assert "NARRATIVE_AI_API_KEY" not in result

    def test_allows_names_with_safe_substrings(self):
        ctx = {"entity_name": "Fosco", "description": "A hobbit"}
        result = sanitize_ai_context(ctx)
        assert result["entity_name"] == "Fosco"

    def test_blocks_visibility_legacy(self):
        ctx = {"visibility_legacy": "old", "visibility": "public"}
        result = sanitize_ai_context(ctx)
        assert "visibility_legacy" not in result
        assert "visibility" in result


class TestNestedSanitization:
    def test_sanitizes_nested_dicts(self):
        ctx = {
            "project": {
                "name": "Test",
                "api_key": "sk-leak",
                "config": {"safe": "yes"},
            }
        }
        result = sanitize_nested(ctx)
        assert result["project"]["name"] == "Test"
        assert "api_key" not in result["project"]
        assert result["project"]["config"]["safe"] == "yes"

    def test_sanitizes_deep_nesting(self):
        ctx = {
            "level1": {
                "level2": {
                    "level3": {
                        "password": "secret",
                        "data": "safe",
                    }
                }
            }
        }
        result = sanitize_nested(ctx)
        assert result["level1"]["level2"]["level3"]["data"] == "safe"
        assert "password" not in result["level1"]["level2"]["level3"]

    def test_preserves_lists(self):
        ctx = {"entities": [{"name": "A"}, {"name": "B", "api_key": "X"}]}
        result = sanitize_nested(ctx)
        assert len(result["entities"]) == 2
        assert result["entities"][0]["name"] == "A"
        assert "api_key" not in result["entities"][1]
        assert result["entities"][1]["name"] == "B"

    def test_handles_non_dict_values(self):
        ctx = {"count": 5, "name": "Test", "active": True}
        result = sanitize_ai_context(ctx)
        assert result["count"] == 5
        assert result["name"] == "Test"
        assert result["active"] is True
