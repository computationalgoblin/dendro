"""Tests for B42-T06: Prompt Registry versionado.

Verify that prompts are centralized, versioned, and retrievable by key.
"""
import pytest

from packages.application.prompt_registry import (
    PromptRegistry,
    get_prompt,
    PROMPT_VERSIONS,
)


class TestRegistryStructure:
    def test_registry_has_all_keys(self):
        expected = {
            "command_bar", "inline_leaf", "inline_branch",
            "inline_relation", "coherence", "coherence_repair",
            "wizard_suggestion",
        }
        for key in expected:
            assert key in PromptRegistry, f"Missing prompt key: {key}"

    def test_all_prompts_have_version(self):
        for key, entry in PromptRegistry.items():
            assert "version" in entry, f"Prompt '{key}' missing version"
            assert isinstance(entry["version"], int), f"Prompt '{key}' version not int"

    def test_all_prompts_have_text(self):
        for key, entry in PromptRegistry.items():
            assert "es" in entry or "en" in entry, f"Prompt '{key}' has no text"
            for lang in ("es", "en"):
                if lang in entry:
                    assert len(entry[lang]) > 20, f"Prompt '{key}/{lang}' too short"

    def test_versions_are_tracked(self):
        assert len(PROMPT_VERSIONS) >= 7
        for key, ver in PROMPT_VERSIONS.items():
            assert isinstance(ver, int), f"Version for '{key}' not int"


class TestGetPrompt:
    def test_get_spanish_prompt(self):
        text = get_prompt("command_bar", lang="es")
        assert text is not None
        assert len(text) > 50
        assert "Dendro" in text or "canon" in text.lower() or "narrati" in text.lower()

    def test_get_english_prompt(self):
        text = get_prompt("coherence", lang="en")
        assert text is not None
        assert len(text) > 50

    def test_get_prompt_falls_back_to_es(self):
        text = get_prompt("wizard_suggestion", lang="fr")
        # Should fall back to Spanish if French not available
        assert text is not None

    def test_get_unknown_prompt_returns_none(self):
        text = get_prompt("nonexistent_prompt_xyz")
        assert text is None

    def test_coherence_prompt_mentions_structure(self):
        text = get_prompt("coherence", lang="es")
        assert "veredicto" in text.lower() or "Verdict" in text or "estructur" in text.lower()

    def test_command_bar_prompt_mentions_candidates(self):
        text = get_prompt("command_bar", lang="es")
        assert "candidato" in text.lower() or "revisab" in text.lower()
