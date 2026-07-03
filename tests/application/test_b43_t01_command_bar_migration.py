"""Tests for B43-T01: Command bar registry migration.

Verify that ai_jobs.py uses Prompt Registry instead of inline prompt
and that behavior is preserved.
"""
import pytest

from packages.application.prompt_registry import get_prompt, PromptRegistry
from packages.application.ai_jobs import COMMAND_BAR_SYSTEM_PROMPT_ES


class TestCommandBarUsesRegistry:
    def test_inline_prompt_matches_registry(self):
        """The inline constant should equal the registry version."""
        registry_prompt = get_prompt("command_bar", lang="es")
        assert registry_prompt is not None
        # After migration, the inline should be removed or redirected
        # For now, verify they match
        assert COMMAND_BAR_SYSTEM_PROMPT_ES.strip() == registry_prompt.strip()

    def test_command_bar_prompt_has_terminology(self):
        prompt = get_prompt("command_bar", lang="es")
        assert "Hoja" in prompt
        assert "Rama" in prompt
        assert "Anillo" in prompt

    def test_command_bar_prompt_has_classification_rules(self):
        prompt = get_prompt("command_bar", lang="es")
        assert "REGLAS DE CLASIFICACIÓN" in prompt or "clasificación" in prompt.lower()

    def test_command_bar_prompt_has_creative_brief(self):
        # PA03: la config creativa viaja en una única sección configuracion_creativa.
        prompt = get_prompt("command_bar", lang="es")
        assert "configuracion_creativa" in prompt

    def test_command_bar_prompt_has_json_schema(self):
        prompt = get_prompt("command_bar", lang="es")
        assert "summary" in prompt
        assert "hojas" in prompt
        assert "ramas" in prompt

    def test_command_bar_prompt_has_no_ids(self):
        prompt = get_prompt("command_bar", lang="es")
        assert "No incluyas IDs inventados" in prompt or "IDs inventados" in prompt

    def test_command_bar_prompt_version(self):
        entry = PromptRegistry["command_bar"]
        assert entry["version"] >= 2, "Prompt should be updated to v2 with full text"


class TestCommandBarMigration:
    def test_ai_jobs_imports_registry(self):
        """ai_jobs should import from prompt_registry."""
        import packages.application.ai_jobs as aj
        with open(aj.__file__, encoding="utf-8") as f:
            source = f.read()
        assert "get_prompt" in source or "prompt_registry" in source
