"""AI Provider abstraction + SimulatedAIProvider (B15-T02)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from packages.domain.ai_models import AIMode, AIOperation, AIResponse


class AIProvider(ABC):
    @abstractmethod
    def invoke(self, operation: AIOperation) -> AIResponse:
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...


class SimulatedAIProvider(AIProvider):
    provider_name = "simulated"

    def invoke(self, operation: AIOperation) -> AIResponse:
        mode = operation.mode
        raw = ""
        candidates = []
        obs = []

        if mode == AIMode.GENERATE_ENTITY:
            raw = "Simulated entity generation"
            candidates = [
                {"name": "Simulated Entity", "entity_type": "personaje"},
                {"name": "Simulated Location", "entity_type": "localizacion"},
            ][:operation.max_candidates]
        elif mode == AIMode.GENERATE_RELATION:
            raw = "Simulated relation generation"
            candidates = [
                {"source_id": "", "target_id": "", "relation_type": "es_aliado_de"},
            ][:operation.max_candidates]
        elif mode == AIMode.EXPAND_ENTITY:
            raw = "Simulated expansion: this entity could have additional details..."
            candidates = [{"name": "Expanded detail", "entity_type": "objeto"}]
        elif mode == AIMode.SUMMARIZE:
            raw = "Simulated summary of the entity."
        elif mode == AIMode.REWRITE_DESCRIPTION:
            raw = "Rewritten description in a different style."
            candidates = [{"description": "Rewritten description text"}]
        elif mode == AIMode.SUGGEST_TAGS:
            raw = "Suggested tags: magia, anciano, torre"
            candidates = [{"tags": ["magia", "anciano", "torre"]}]
        elif mode == AIMode.SUGGEST_RELATIONS:
            raw = "Simulated relation suggestions"
            candidates = [
                {"source_id": "", "target_id": "", "relation_type": "es_aliado_de"},
            ]

        elif mode == AIMode.CRITICAL_ANALYSIS:
            raw = "Simulated critical analysis"
            candidates = [
                {"type": "invalid_entity_type", "description": "Entity may lack description", "severity": "MEDIA"},
                {"title": "Add description to entity", "proposed_data": {"brief_description": "Suggested brief"}},
            ]
            obs = ["Entity has limited faction interactions"]
        elif mode == AIMode.CAUSAL_ANALYSIS:
            raw = "Simulated causal analysis"
            candidates = [
                {"name": "Consequence X", "entity_type": "evento"},
                {"source_id": "", "target_id": "", "relation_type": "causo"},
            ]
            obs = ["Event has no documented cause"]
        elif mode == AIMode.CONSISTENCY_ANALYSIS:
            raw = "Simulated consistency analysis"
            candidates = [
                {"type": "narrative", "description": "Character motivation contradicts earlier behavior"},
                {"type": "causal_gap", "description": "Missing cause for major event"},
            ]
            obs = []
        elif mode == AIMode.CONTINUITY_QUESTION:
            raw = "Simulated answer to continuity question."
            obs = ["Consider checking historical timeline for consistency."]

        return AIResponse(
            id=operation.mode.value + "_sim",
            operation=operation,
            raw_text=raw,
            candidates=candidates,
            observations=obs,
            provider="simulated",
            latency_ms=10.0,
        )


def create_provider(name: str = "simulated", config: dict | None = None) -> AIProvider:
    """Preferred entry point. Delegates to get_provider() for env-configurable selection."""
    from packages.infrastructure.openai_compatible_provider import get_provider
    return get_provider()
    if name == "simulated":
        return SimulatedAIProvider()
    raise ValueError(f"Unknown AI provider: {name}")
