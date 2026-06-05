"""Context Sanitizer — B42-T02.

Standalone module for sanitizing AI context before sending to providers.
Removes sensitive fields, API keys, provider configs, raw metadata, etc.

Can be used independently of AIRequestGateway by any service that builds
context for AI calls.
"""
from __future__ import annotations

from typing import Any


# Keys that are always blocked
BLOCKED_KEYS: frozenset[str] = frozenset({
    "api_key", "api_secret", "auth_token", "bearer",
    "provider_config", "provider_settings",
    "raw_metadata", "internal_metadata",
    "source_ids", "source_id",
    "visibility_legacy", "_visibility",
    "password", "secret", "credentials",
    "narrative_ai_api_key", "narrative_ai_base_url",
    "narrative_ai_provider", "narrative_ai_model",
})

# Patterns in key names that indicate sensitive data
BLOCKED_PATTERNS: tuple[str, ...] = (
    "api_key", "api_secret", "secret", "password",
    "token", "credential", "auth_",
)


def sanitize_ai_context(context: dict[str, Any] | None) -> dict[str, Any]:
    """Remove sensitive fields from a flat context dict.

    Args:
        context: Raw context dict that may contain sensitive fields.

    Returns:
        Sanitized dict with blocked keys/patterns removed.
    """
    if not context:
        return {}
    result = {}
    for key, value in context.items():
        if _is_blocked(key):
            continue
        result[key] = value
    return result


def sanitize_nested(context: dict[str, Any] | None) -> dict[str, Any]:
    """Remove sensitive fields from nested context (dicts within dicts/lists).

    Recursively walks the context tree and removes blocked keys at every level.

    Args:
        context: Raw nested context dict.

    Returns:
        Deep copy with blocked keys removed at all levels.
    """
    if not context:
        return {}
    return _sanitize_value(context)


def _is_blocked(key: str) -> bool:
    """Check if a key should be blocked."""
    k_lower = key.lower()
    if k_lower in BLOCKED_KEYS:
        return True
    return any(p in k_lower for p in BLOCKED_PATTERNS)


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize a value."""
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items() if not _is_blocked(k)}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value
