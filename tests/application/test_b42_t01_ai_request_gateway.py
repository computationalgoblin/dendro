"""Tests for B42-T01: AIRequestGateway.

The gateway wraps AI calls with: build context, sanitize, select prompt,
select model params, call provider, validate output, return typed result.
It does NOT break existing APIs — it sits between application services
and the provider.
"""
import pytest
from unittest.mock import MagicMock, patch

from packages.application.ai_request_gateway import (
    AIRequestGateway,
    GatewayRequest,
    GatewayResponse,
    ModelParams,
    INTENT_PARAMS,
)


# ---------------------------------------------------------------------------
# 1. GatewayRequest construction
# ---------------------------------------------------------------------------

class TestGatewayRequest:
    def test_request_has_required_fields(self):
        req = GatewayRequest(
            intent="generate_entities",
            user_prompt="Crea tres personajes",
            context={"project_name": "Test"},
        )
        assert req.intent == "generate_entities"
        assert req.user_prompt == "Crea tres personajes"
        assert req.context == {"project_name": "Test"}
        assert req.system_prompt_override is None
        assert req.timeout is None

    def test_request_optional_fields(self):
        req = GatewayRequest(
            intent="coherence",
            user_prompt="Analiza",
            context={},
            system_prompt_override="Custom system",
            timeout=60,
        )
        assert req.system_prompt_override == "Custom system"
        assert req.timeout == 60


# ---------------------------------------------------------------------------
# 2. ModelParams derivation from intent
# ---------------------------------------------------------------------------

class TestModelParams:
    def test_coherence_uses_low_temperature(self):
        params = ModelParams.from_intent("coherence")
        assert params.temperature <= 0.3

    def test_generation_uses_higher_temperature(self):
        params = ModelParams.from_intent("generate_entities")
        assert params.temperature >= 0.5

    def test_extraction_uses_low_temperature(self):
        params = ModelParams.from_intent("extract")
        assert params.temperature <= 0.3

    def test_classification_uses_low_temperature(self):
        params = ModelParams.from_intent("classify")
        assert params.temperature <= 0.3

    def test_default_params_exist(self):
        params = ModelParams.default()
        assert params.temperature == 0.7
        assert params.max_tokens == 2000

    def test_unknown_intent_gets_default(self):
        params = ModelParams.from_intent("unknown_whatever")
        assert params.temperature == 0.7

    def test_review_uses_more_tokens(self):
        params = ModelParams.from_intent("review_graph")
        assert params.max_tokens >= 2000


# ---------------------------------------------------------------------------
# 3. Gateway sanitizes context (removes sensitive fields)
# ---------------------------------------------------------------------------

class TestContextSanitization:
    def test_removes_api_keys(self):
        ctx = {"api_key": "sk-123", "base_url": "https://api.example.com", "safe": "yes"}
        sanitized = AIRequestGateway.sanitize_context(ctx)
        assert "api_key" not in sanitized
        assert "safe" in sanitized

    def test_removes_provider_config(self):
        ctx = {"provider_config": {"api_key": "x"}, "name": "Proj"}
        sanitized = AIRequestGateway.sanitize_context(ctx)
        assert "provider_config" not in sanitized
        assert "name" in sanitized

    def test_removes_raw_metadata(self):
        ctx = {"raw_metadata": {"internal": True}, "title": "OK"}
        sanitized = AIRequestGateway.sanitize_context(ctx)
        assert "raw_metadata" not in sanitized
        assert "title" in sanitized

    def test_removes_source_ids(self):
        ctx = {"source_ids": ["a", "b"], "entity_name": "Fosco"}
        sanitized = AIRequestGateway.sanitize_context(ctx)
        assert "source_ids" not in sanitized
        assert "entity_name" in sanitized

    def test_preserves_safe_fields(self):
        ctx = {
            "project_name": "Test",
            "genre": "fantasy",
            "tone": "epic",
            "entities": [{"name": "Fosco"}],
        }
        sanitized = AIRequestGateway.sanitize_context(ctx)
        assert sanitized["project_name"] == "Test"
        assert sanitized["genre"] == "fantasy"
        assert len(sanitized["entities"]) == 1


# ---------------------------------------------------------------------------
# 4. Gateway validates output
# ---------------------------------------------------------------------------

class TestOutputValidation:
    def test_valid_text_response(self):
        resp = GatewayResponse(text="Hello", error=None, intent="chat")
        assert resp.is_valid

    def test_error_response_is_invalid(self):
        resp = GatewayResponse(text=None, error="Timeout", intent="chat")
        assert not resp.is_valid

    def test_empty_text_is_invalid(self):
        resp = GatewayResponse(text="", error=None, intent="chat")
        assert not resp.is_valid

    def test_valid_json_response(self):
        resp = GatewayResponse(
            text='{"entities": []}', error=None, intent="generate_entities"
        )
        assert resp.is_valid
        assert resp.parsed_json == {"entities": []}

    def test_invalid_json_still_valid_as_text(self):
        resp = GatewayResponse(
            text="Not JSON but valid text", error=None, intent="freeform"
        )
        assert resp.is_valid


# ---------------------------------------------------------------------------
# 5. Gateway calls provider with correct params
# ---------------------------------------------------------------------------

class TestGatewayExecution:
    def test_gateway_calls_chat(self):
        mock_provider = MagicMock()
        mock_provider.chat.return_value = ("AI response text", None)
        mock_provider.provider_name = "mock"

        gw = AIRequestGateway(provider=mock_provider)
        req = GatewayRequest(intent="chat", user_prompt="Hello", context={})
        result = gw.execute(req)

        assert result.is_valid
        assert result.text == "AI response text"
        mock_provider.chat.assert_called_once()

    def test_gateway_handles_provider_error(self):
        mock_provider = MagicMock()
        mock_provider.chat.return_value = (None, "Connection error")
        mock_provider.provider_name = "mock"

        gw = AIRequestGateway(provider=mock_provider)
        req = GatewayRequest(intent="chat", user_prompt="Hello", context={})
        result = gw.execute(req)

        assert not result.is_valid
        assert "Connection error" in result.error

    def test_gateway_records_metadata(self):
        mock_provider = MagicMock()
        mock_provider.chat.return_value = ("OK", None)
        mock_provider.provider_name = "mock"

        gw = AIRequestGateway(provider=mock_provider)
        req = GatewayRequest(intent="chat", user_prompt="Hello", context={})
        result = gw.execute(req)

        assert result.metadata["provider"] == "mock"
        assert result.metadata["intent"] == "chat"
        assert "duration_ms" in result.metadata
