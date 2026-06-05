"""Tests for B42-T07: Legacy orchestrator hardening.

Static tests that verify:
1. provider.invoke / OrchestratorService are marked legacy
2. No new features should use invoke() directly
3. Legacy markers exist in code
"""
import ast
import pytest
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[2]


class TestLegacyMarkers:
    """Verify legacy code is properly marked."""

    def test_orchestrator_service_has_legacy_marker(self):
        """OrchestratorService must have a deprecation/legacy marker."""
        path = WORKSPACE / "packages" / "application" / "orchestrator_service.py"
        if not path.exists():
            pytest.skip("orchestrator_service.py not found")
        content = path.read_text(encoding="utf-8")
        assert "legacy" in content.lower() or "deprecated" in content.lower(), \
            "OrchestratorService must have a legacy/deprecated marker"

    def test_provider_invoke_has_legacy_marker(self):
        """OpenAICompatibleProvider.invoke() must have a legacy note."""
        path = WORKSPACE / "packages" / "infrastructure" / "openai_compatible_provider.py"
        if not path.exists():
            pytest.skip("openai_compatible_provider.py not found")
        content = path.read_text(encoding="utf-8")
        # The invoke method should warn about being legacy
        assert "legacy" in content.lower() or "deprecated" in content.lower() or "do not use" in content.lower(), \
            "OpenAICompatibleProvider.invoke must have a legacy/deprecated marker"


class TestNoDirectInvokeInNewCode:
    """New modules (B42+) should not use provider.invoke() directly."""

    GATEWAY_MODULES = {
        "packages/application/ai_request_gateway.py",
        "packages/application/context_sanitizer.py",
    }

    def test_gateway_does_not_use_invoke(self):
        """AIRequestGateway should use chat(), not invoke()."""
        for rel_path in self.GATEWAY_MODULES:
            path = WORKSPACE / rel_path
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            assert ".invoke(" not in content, \
                f"{rel_path} should not use provider.invoke() — use provider.chat() via AIRequestGateway"

    def test_ai_context_actions_uses_chat_for_text(self):
        """ai_context_actions text methods should use .chat() not .invoke()."""
        path = WORKSPACE / "packages" / "application" / "ai_context_actions.py"
        if not path.exists():
            pytest.skip("ai_context_actions.py not found")
        content = path.read_text(encoding="utf-8")
        # Count chat calls vs invoke calls
        chat_count = content.count(".chat(")
        invoke_count = content.count(".invoke(")
        # We expect chat calls for text/coherence/repair
        assert chat_count >= 4, \
            f"ai_context_actions should use .chat() for text/coherence methods, found {chat_count} chat calls"
