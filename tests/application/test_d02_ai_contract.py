"""D02: AI product contract guards."""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

from packages.application.ai_request_gateway import AIRequestGateway, GatewayRequest
from packages.application.output_schema_validator import validate_ai_output


WORKSPACE = Path(__file__).resolve().parents[2]


def test_validator_rejects_direct_canon_state_mutation():
    text = '{"entities": [{"name": "Fosco", "canon_state": "canon"}]}'

    result = validate_ai_output(text, "generate_entities")

    assert not result.is_valid
    assert "mutacion directa" in result.error


def test_validator_rejects_auto_apply_flags_nested_in_relations():
    text = (
        '{"relations": [{"source_name": "A", "target_name": "B", '
        '"relation_type": "x", "metadata": {"apply_directly": true}}]}'
    )

    result = validate_ai_output(text, "generate_relations")

    assert not result.is_valid
    assert "apply_directly" in result.error


def test_gateway_rejects_structured_output_with_mutation_keys():
    provider = MagicMock()
    provider.provider_name = "mock"
    provider.chat.return_value = (
        '{"entities": [{"name": "Fosco", "canon_state": "canon"}]}',
        None,
    )
    gateway = AIRequestGateway(provider=provider)

    result = gateway.execute(GatewayRequest(
        intent="generate_entities",
        user_prompt="crea un candidato",
        context={"project_name": "Demo"},
    ))

    assert not result.is_valid
    assert result.metadata["status"] == "error"
    assert result.metadata["error_type"] == "validation"


def test_gateway_sanitizes_nested_context_before_provider_call():
    provider = MagicMock()
    provider.provider_name = "mock"
    provider.chat.return_value = ("ok", None)
    gateway = AIRequestGateway(provider=provider)

    gateway.execute(GatewayRequest(
        intent="chat",
        user_prompt="hola",
        context={"project": {"name": "Demo", "api_key": "secret-value"}},
    ))

    system_prompt = provider.chat.call_args.kwargs["system_prompt"]
    assert "secret-value" not in system_prompt
    assert "api_key" not in system_prompt


def test_ai_application_modules_do_not_create_canon_directly():
    forbidden = {"create_entity", "create_relation", "update_entity", "update_relation"}
    offenders: list[str] = []

    for path in (WORKSPACE / "packages" / "application").glob("ai_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden:
                    offenders.append(f"{path.relative_to(WORKSPACE)}:{node.lineno}:{node.func.attr}")

    assert offenders == []
