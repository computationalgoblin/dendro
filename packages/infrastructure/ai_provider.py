"""AI Provider abstraction + SimulatedAIProvider (B15-T02)."""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod

from packages.domain.ai_models import AIMode, AIOperation, AIResponse


def provider_chat(
    provider,
    system_prompt: str,
    user_message: str,
    *,
    timeout=None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
):
    """Call ``provider.chat`` tolerating older / narrower chat() signatures.

    BETA1-AI01 added temperature/max_tokens/json_mode, but test doubles and
    third-party providers may not accept them. We pass only the kwargs the
    callee actually declares (or all of them if it has ``**kwargs``), so the new
    params are applied when supported and skipped otherwise — without masking a
    real TypeError raised inside the provider.
    """
    fn = provider.chat
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        params = {}
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    kwargs: dict = {}
    for name, value in (
        ("timeout", timeout),
        ("temperature", temperature),
        ("max_tokens", max_tokens),
        ("json_mode", json_mode),
    ):
        if has_var_kw or name in params:
            kwargs[name] = value
    return fn(system_prompt, user_message, **kwargs)


class AIProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    # BETA1-AI01: callers can tune generation per intent and ask for JSON.
    # Defaults keep every existing `chat(system, user, timeout)` call working.
    def chat(
        self,
        system_prompt: str,
        user_message: str,
        timeout=None,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ):
        """Direct chat with a custom system prompt. Returns ``(text, error)``.

        - ``temperature`` / ``max_tokens``: per-intent generation params. ``None``
          means "provider default". Subclasses that ignore them keep working.
        - ``json_mode``: request a strict JSON object response when the provider
          supports it (e.g. OpenAI ``response_format``).
        """
        return None, "Not implemented"

    def invoke(self, operation: AIOperation) -> AIResponse:
        ...


class SimulatedAIProvider(AIProvider):
    provider_name = "simulated"

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        timeout=None,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ):
        """Deterministic local chat fallback for UI smoke tests.

        It returns text only and never creates candidates. The wording mirrors
        the user's instruction enough to reveal routing bugs without using a key.
        """
        lower = (system_prompt + "\n" + user_message).lower()
        if "fosco" in lower:
            return (
                "Fosco atravesó caminos de polvo, posadas medio olvidadas y fronteras donde cada promesa "
                "tenía un precio. Sus aventuras no nacieron de la gloria, sino de una obstinación tranquila: "
                "seguir adelante incluso cuando el mapa dejaba de ser fiable. En cada viaje ganó una cicatriz, "
                "una historia y una deuda pendiente que todavía tira de él hacia el próximo umbral.",
                None,
            )
        if "english" in lower or "respond in english" in lower:
            return ("Draft a focused narrative passage from the selected entity, respecting its current name, type, and project tone.", None)
        return (
            "Desarrolla el contenido de la entidad seleccionada con un tono coherente con el proyecto, "
            "aprovechando el nombre, el tipo y el texto ya escrito sin crear nodos ni relaciones nuevas.",
            None,
        )

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
            raw = "Sugerencia de reescritura simulada. Revisa y acepta solo si encaja con el canon."
            candidates = [{"description": "Texto de reescritura simulado"}]
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
    """Select a provider.

    - ``name == "simulated"`` → always the local simulated provider (honours the
      explicit request; before this it silently went to the env provider).
    - otherwise → env-configurable selection (NARRATIVE_AI_* env vars).
    """
    if name == "simulated":
        return SimulatedAIProvider()
    from packages.infrastructure.openai_compatible_provider import get_provider
    return get_provider()
