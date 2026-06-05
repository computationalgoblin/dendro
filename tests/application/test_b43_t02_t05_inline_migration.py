"""Tests for B43-T02..T05: Inline prompt migration verification.

Static tests that verify ai_context_actions.py no longer contains
long inline prompts and instead uses get_prompt from registry.
"""
import pytest


def _read_module(filename: str) -> str:
    with open(filename) as f:
        return f.read()


class TestInlineLeafMigration:
    """T02: inline_leaf migrated to registry."""

    def test_no_inline_entity_text_prompt_es(self):
        source = _read_module("packages/application/ai_context_actions.py")
        # Should NOT contain the old inline prompt text
        assert "Eres un asistente de escritura integrado en Dendro" not in source

    def test_uses_get_prompt_for_leaf(self):
        source = _read_module("packages/application/ai_context_actions.py")
        assert 'get_prompt("inline_leaf"' in source


class TestInlineRelationMigration:
    """T03: inline_relation migrated to registry."""

    def test_no_inline_relation_text_prompt(self):
        source = _read_module("packages/application/ai_context_actions.py")
        assert "relación narrativa entre dos entidades" not in source

    def test_uses_get_prompt_for_relation(self):
        source = _read_module("packages/application/ai_context_actions.py")
        assert 'get_prompt("inline_relation"' in source


class TestCoherenceMigration:
    """T04: coherence migrated to registry."""

    def test_no_inline_coherence_prompt(self):
        source = _read_module("packages/application/ai_context_actions.py")
        assert "editor de coherencia narrativa integrado en Dendro" not in source

    def test_uses_get_prompt_for_coherence(self):
        source = _read_module("packages/application/ai_context_actions.py")
        assert 'get_prompt("coherence"' in source


class TestCoherenceRepairMigration:
    """T05: coherence_repair migrated to registry."""

    def test_no_inline_repair_prompt(self):
        source = _read_module("packages/application/ai_context_actions.py")
        assert "reparación aplicable solo a los nodos" not in source

    def test_uses_get_prompt_for_repair(self):
        source = _read_module("packages/application/ai_context_actions.py")
        assert 'get_prompt("coherence_repair"' in source


class TestCommandBarMigration:
    """T01: command_bar migrated in ai_jobs.py."""

    def test_no_inline_command_bar_prompt(self):
        source = _read_module("packages/application/ai_jobs.py")
        assert "planificador y asistente central de creación de Dendro" not in source

    def test_uses_get_prompt_for_command_bar(self):
        source = _read_module("packages/application/ai_jobs.py")
        assert 'get_prompt("command_bar"' in source

    def test_command_bar_imports_registry(self):
        source = _read_module("packages/application/ai_jobs.py")
        assert "from packages.application.prompt_registry import" in source
