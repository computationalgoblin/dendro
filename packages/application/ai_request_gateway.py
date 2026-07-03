"""AIRequestGateway — B42-T01.

Common layer for all AI calls. Provides:
- Context sanitization (remove sensitive fields)
- Model parameter selection based on intent
- Provider dispatch with correct params
- Output validation
- Typed result with metadata

Does NOT break existing APIs. Wraps provider calls with guard rails.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from packages.application.context_sanitizer import sanitize_nested
from packages.application.output_schema_validator import ValidationResult, validate_ai_output
from packages.infrastructure.ai_provider import AIProvider, create_provider, provider_chat


DEFAULT_AI_TIMEOUT_SECONDS = 300


# ---------------------------------------------------------------------------
# Blocked fields — never pass to AI
# ---------------------------------------------------------------------------

_BLOCKED_CONTEXT_KEYS: frozenset[str] = frozenset({
    "api_key", "api_secret", "auth_token", "bearer",
    "provider_config", "provider_settings",
    "raw_metadata", "internal_metadata",
    "source_ids", "source_id",
    "visibility_legacy", "_visibility",
    "password", "secret", "credentials",
    "narrative_ai_api_key", "narrative_ai_base_url",
})


# ---------------------------------------------------------------------------
# Intent → model params mapping
# ---------------------------------------------------------------------------

@dataclass
class ModelParams:
    """Parameters derived from intent type."""
    temperature: float = 0.7
    max_tokens: int = 2000

    @staticmethod
    def from_intent(intent: str) -> ModelParams:
        """Derive params from intent. Unknown intents get defaults."""
        return INTENT_PARAMS.get(intent, ModelParams.default())

    @staticmethod
    def default() -> ModelParams:
        return ModelParams(temperature=0.7, max_tokens=2000)


# Intent → params lookup
INTENT_PARAMS: dict[str, ModelParams] = {
    # Low temperature: analytical, precise
    "coherence":           ModelParams(temperature=0.2, max_tokens=2000),
    "consistency":         ModelParams(temperature=0.2, max_tokens=2000),
    "extract":             ModelParams(temperature=0.15, max_tokens=1500),
    "classify":            ModelParams(temperature=0.15, max_tokens=1000),
    "coherence_repair":    ModelParams(temperature=0.2, max_tokens=2000),
    # BETA2-FOCO: riego — diagnóstico JSON acotado y analítico.
    "water_entity":        ModelParams(temperature=0.2, max_tokens=1400),
    "review_graph":        ModelParams(temperature=0.3, max_tokens=3000),
    "detect_contradiction": ModelParams(temperature=0.2, max_tokens=2000),
    "detect_inconsistency": ModelParams(temperature=0.2, max_tokens=2000),
    # Medium temperature: balanced
    "chat":                ModelParams(temperature=0.7, max_tokens=2000),
    "freeform":            ModelParams(temperature=0.7, max_tokens=2000),
    "explain":             ModelParams(temperature=0.5, max_tokens=2000),
    "edit":                ModelParams(temperature=0.5, max_tokens=1500),
    "edit_entities":       ModelParams(temperature=0.5, max_tokens=2200),
    "suggest":             ModelParams(temperature=0.6, max_tokens=2000),
    "node_text_suggestion": ModelParams(temperature=0.6, max_tokens=1500),
    "relation_text_suggestion": ModelParams(temperature=0.6, max_tokens=1500),
    # Higher temperature: creative generation
    "generate_entities":   ModelParams(temperature=0.8, max_tokens=2200),
    "generate_trees":      ModelParams(temperature=0.8, max_tokens=2000),
    "generate_relations":  ModelParams(temperature=0.7, max_tokens=2000),
    "improvise":           ModelParams(temperature=0.85, max_tokens=2500),
    "expand":              ModelParams(temperature=0.75, max_tokens=2000),
    "wizard_suggestion":   ModelParams(temperature=0.8, max_tokens=2000),

    # BETA1-AI02: command-bar AIJobType.value intents. Single source of truth —
    # these replace the old `_JOB_MODEL_PARAMS` map in ai_jobs.py. Keyed by the
    # literal AIJobType values (kept as strings here to avoid an import cycle:
    # ai_jobs already imports ModelParams from this module). Analytical jobs run
    # cold, creative jobs run warm.
    "generate_tree":       ModelParams(temperature=0.8, max_tokens=2400),
    "suggest_relations":   ModelParams(temperature=0.55, max_tokens=2000),
    "analyze_coherence":   ModelParams(temperature=0.2, max_tokens=2600),
    "expand_worldbuilding": ModelParams(temperature=0.8, max_tokens=2600),
    "explain_from_causes": ModelParams(temperature=0.4, max_tokens=2200),
    "freeform_planning":   ModelParams(temperature=0.7, max_tokens=2000),
    "propose_milestones":  ModelParams(temperature=0.7, max_tokens=2200),
    # Deterministic command matrix (Acción × Ámbito) — new focused job types.
    "create_ring_template": ModelParams(temperature=0.8, max_tokens=2600),
    "edit_relation":       ModelParams(temperature=0.5, max_tokens=1800),
    "edit_ring":           ModelParams(temperature=0.5, max_tokens=2000),
    "edit_milestone":      ModelParams(temperature=0.5, max_tokens=1800),
    # CRON: análisis editorial por hito. Analítico (temp baja por defecto); el
    # servicio la sobreescribe según el Modo (Consistencia/Mixto/Creativo).
    "chronology_walk_step": ModelParams(temperature=0.25, max_tokens=3000),
    # Text-only intents (BETA1-AI02 Fase 2): free text, no JSON staging.
    "improve_text":        ModelParams(temperature=0.6, max_tokens=1500),
    "generate_text":       ModelParams(temperature=0.7, max_tokens=1800),
    "unknown":             ModelParams(temperature=0.6, max_tokens=1500),
}


# ---------------------------------------------------------------------------
# Request / Response types
# ---------------------------------------------------------------------------

@dataclass
class GatewayRequest:
    """Typed request through the gateway."""
    intent: str
    user_prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    system_prompt_override: str | None = None
    timeout: int | None = None
    # BETA1-AI01: opt-in strict JSON output (provider response_format). Off by
    # default so free-text callers (e.g. text suggestions) are unaffected.
    json_mode: bool = False
    # BETA1-AI02: callers that own their parsing/staging (the command-bar job
    # pipeline tolerates Spanish container keys like `hojas`/`ramas` that the
    # English EXPECTED_SCHEMAS would reject) can skip schema validation here.
    validate: bool = True
    # F3: optional UI overrides (radial tuners). When set, they take precedence
    # over the intent's recommended ModelParams.
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass
class GatewayResponse:
    """Typed response from the gateway."""
    text: str | None
    error: str | None
    intent: str
    metadata: dict[str, Any] = field(default_factory=dict)
    _parsed_json: Any = field(default=None, repr=False)

    @property
    def is_valid(self) -> bool:
        if self.error:
            return False
        if not self.text or len(self.text.strip()) < 1:
            return False
        return True

    @property
    def parsed_json(self) -> Any:
        if self._parsed_json is not None:
            return self._parsed_json
        if self.text:
            try:
                self._parsed_json = json.loads(self.text)
            except (json.JSONDecodeError, ValueError):
                pass
        return self._parsed_json


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class AIRequestGateway:
    """Common layer for AI requests.

    Wraps provider calls with:
    1. Context sanitization
    2. Model param selection
    3. Provider dispatch
    4. Output validation
    5. Typed result with metadata
    """

    def __init__(self, provider: AIProvider | None = None,
                 provider_name: str = "simulated"):
        self.provider = provider or create_provider(provider_name)

    def execute(self, request: GatewayRequest) -> GatewayResponse:
        """Execute an AI request through the pipeline."""
        t0 = time.time()

        # 1. Sanitize context
        safe_ctx = self.sanitize_context(request.context)

        # 2. Select model params (intent recommendation, optionally overridden
        #    by the UI tuners on the request).
        base = ModelParams.from_intent(request.intent)
        temperature = base.temperature if request.temperature is None else float(request.temperature)
        max_tokens = base.max_tokens if request.max_tokens is None else int(request.max_tokens)
        params = ModelParams(temperature=max(0.0, min(2.0, temperature)), max_tokens=max(1, max_tokens))

        # 3. Build system prompt
        system = request.system_prompt_override or ""
        if safe_ctx:
            ctx_block = json.dumps(safe_ctx, ensure_ascii=False, default=str)
            if len(ctx_block) > 8000:
                ctx_block = ctx_block[:8000] + "\n...[truncated]"
            system = f"{system}\n\nContext: {ctx_block}" if system else f"Context: {ctx_block}"

        # 4. Call provider — BETA1-AI01: actually apply the intent's params
        # (provider_chat passes only the kwargs the provider declares).
        text, error = provider_chat(
            self.provider,
            system,
            request.user_prompt,
            timeout=request.timeout or DEFAULT_AI_TIMEOUT_SECONDS,
            temperature=params.temperature,
            max_tokens=params.max_tokens,
            json_mode=request.json_mode,
        )

        # The job pipeline (validate=False) parses and stages results itself;
        # only validate when the caller relies on the gateway's schema check.
        if request.validate:
            validation = validate_ai_output(text, request.intent)
        else:
            validation = ValidationResult(is_valid=True, parsed=None)

        # 5. Build response
        duration_ms = (time.time() - t0) * 1000
        metadata = {
            "provider": getattr(self.provider, "provider_name", "unknown"),
            "intent": request.intent,
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
            "context_depth": len(safe_ctx),
            "input_size": len(request.user_prompt) + len(system),
            "output_size": len(text) if text else 0,
            "duration_ms": round(duration_ms, 1),
            "status": "ok" if not error and validation.is_valid else "error",
            # BETA1-AI01: error is a string message, not an exception — report a
            # stable category instead of always "str".
            "error_type": "provider_error" if error else ("validation" if not validation.is_valid else None),
            "validation_error": validation.error,
            "retry_hint": validation.retry_hint,
        }
        if error or not validation.is_valid:
            return GatewayResponse(
                text=text,
                error=error or validation.error,
                intent=request.intent,
                metadata=metadata,
                _parsed_json=validation.parsed if validation.is_valid else None,
            )
        return GatewayResponse(
            text=text,
            error=error,
            intent=request.intent,
            metadata=metadata,
            _parsed_json=validation.parsed if isinstance(validation.parsed, (dict, list)) else None,
        )

    @staticmethod
    def sanitize_context(context: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive fields from context before sending to AI."""
        if not context:
            return {}
        sanitized = dict(sanitize_nested(context) or {})
        for key, value in context.items():
            k_lower = key.lower()
            # Block exact matches
            if k_lower in _BLOCKED_CONTEXT_KEYS:
                continue
            # Block common sensitive patterns
            if any(p in k_lower for p in ("api_key", "secret", "password", "token", "credential")):
                continue
            # Allow known safe prefixes and anything not blocked
            sanitized[key] = sanitize_nested({key: value}).get(key)
        return sanitized
