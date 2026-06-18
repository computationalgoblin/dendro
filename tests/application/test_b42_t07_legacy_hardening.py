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

    def test_provider_invoke_is_removed(self):
        """BETA1-AI02: the legacy provider.invoke() path is gone entirely."""
        from packages.infrastructure.ai_provider import AIProvider, SimulatedAIProvider
        from packages.infrastructure.openai_compatible_provider import OpenAICompatibleProvider
        assert not hasattr(AIProvider, "invoke")
        assert not hasattr(SimulatedAIProvider, "invoke")
        assert not hasattr(OpenAICompatibleProvider, "invoke")


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

    def test_ai_context_actions_routes_through_pipeline_not_invoke(self):
        """BETA1-AI02: ai_context_actions must NOT call provider.invoke(). Every
        action is a focused job through the shared command-bar pipeline
        (run_focused_job → AIRequestGateway → provider.chat)."""
        path = WORKSPACE / "packages" / "application" / "ai_context_actions.py"
        if not path.exists():
            pytest.skip("ai_context_actions.py not found")
        content = path.read_text(encoding="utf-8")
        assert ".invoke(" not in content, \
            "ai_context_actions should not use provider.invoke() — route through the job pipeline"
        assert "run_focused_job(" in content, \
            "ai_context_actions should run focused jobs through AIJobService.run_focused_job"
