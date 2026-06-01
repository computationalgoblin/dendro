from __future__ import annotations

from types import SimpleNamespace

from hosts.DesktopHostPySide.controllers.ai_controller import AIController


def test_ai_provider_info_uses_openai_compatible_env_without_key_leak(monkeypatch):
    monkeypatch.setenv("NARRATIVE_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("NARRATIVE_AI_BASE_URL", "https://opencode.ai/zen/v1")
    monkeypatch.setenv("NARRATIVE_AI_API_KEY", "secret-key-must-not-leak")
    monkeypatch.setenv("NARRATIVE_AI_MODEL", "zen-model")

    controller = AIController(SimpleNamespace(active_project=None))
    info = controller.provider_info()

    assert "provider=openai_compatible" in info
    assert "model=zen-model" in info
    assert "base=https://opencode.ai/zen/v1" in info
    assert "fallback=no" in info
    assert "secret-key-must-not-leak" not in info
    assert "simulated" not in info


def test_ai_provider_info_reports_missing_key_as_fallback_reason(monkeypatch):
    monkeypatch.setenv("NARRATIVE_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("NARRATIVE_AI_BASE_URL", "https://opencode.ai/zen/v1")
    monkeypatch.delenv("NARRATIVE_AI_API_KEY", raising=False)
    monkeypatch.setenv("NARRATIVE_AI_MODEL", "zen-model")

    controller = AIController(SimpleNamespace(active_project=None))
    info = controller.provider_info()

    assert "provider=openai_compatible" in info
    assert "fallback=yes" in info
    assert "missing API_KEY" in info
