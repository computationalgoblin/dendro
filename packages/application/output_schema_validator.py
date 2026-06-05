"""Output Schema Validator — B42-T05.

Validates AI output JSON by intent type. Invalid JSON produces a sanitized
error with retry hint — never crashes.

Schema enforcement checks that required fields exist per intent type.
Freeform/unknown intents always pass.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Schema definitions per intent
# ---------------------------------------------------------------------------

# Each schema defines required top-level keys and required fields per item
EXPECTED_SCHEMAS: dict[str, dict[str, Any]] = {
    "generate_entities": {
        "container_key": "entities",
        "required_item_fields": ["name"],
    },
    "generate_trees": {
        "container_key": "trees",
        "required_item_fields": ["name"],
    },
    "generate_relations": {
        "container_key": "relations",
        "required_item_fields": ["relation_type"],
        # At least one of source_name/source_id must be present
        "require_one_of": [["source_name", "source_id"], ["target_name", "target_id"]],
    },
    "coherence": {
        "container_key": None,  # flat object
        "required_fields": [],
        "optional_structure": True,
    },
    "coherence_repair": {
        "container_key": None,
        "required_fields": [],
        "optional_structure": True,
    },
    "edit_entities": {
        "container_key": "entity_edits",
        "required_item_fields": ["entity_name"],
    },
    "review_graph": {
        "container_key": None,
        "required_fields": [],
        "optional_structure": True,
    },
}

# Intents that are always valid (freeform text)
_FREEFORM_INTENTS = {"freeform", "chat", "explain", "suggest", "improvise", "wizard_suggestion"}


@dataclass
class ValidationResult:
    """Result of validating AI output against expected schema."""
    is_valid: bool
    parsed: dict[str, Any] | list | None = None
    error: str | None = None
    retry_hint: str | None = None


def validate_ai_output(text: str | None, intent: str) -> ValidationResult:
    """Validate AI output text against the expected schema for the intent.

    Args:
        text: Raw AI output text (expected JSON for structured intents).
        intent: The intent type that generated this output.

    Returns:
        ValidationResult with is_valid, parsed data, error message, and retry hint.
    """
    # Freeform intents always pass
    if intent in _FREEFORM_INTENTS or intent not in EXPECTED_SCHEMAS:
        return ValidationResult(is_valid=True, parsed=text)

    # Must have text
    if not text or not text.strip():
        return ValidationResult(
            is_valid=False,
            error="Output vacío",
            retry_hint="Reintentar — el modelo no produjo salida",
        )

    # Try to parse JSON
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        return ValidationResult(
            is_valid=False,
            error=f"JSON inválido: {str(e)[:100]}",
            retry_hint="Reintentar — el modelo no produjo JSON válido",
        )

    # Validate against schema
    schema = EXPECTED_SCHEMAS[intent]

    # Flat object schemas (coherence, etc.) — any valid JSON passes
    if schema.get("optional_structure"):
        return ValidationResult(is_valid=True, parsed=parsed)

    container_key = schema.get("container_key")
    if container_key:
        items = parsed.get(container_key) if isinstance(parsed, dict) else None
        if items is None:
            return ValidationResult(
                is_valid=False,
                error=f"Falta clave '{container_key}' en output",
                retry_hint=f"Reintentar — el modelo debe incluir '{container_key}'",
            )
        if not isinstance(items, list):
            return ValidationResult(
                is_valid=False,
                error=f"'{container_key}' debe ser una lista",
                retry_hint="Reintentar — formato incorrecto",
            )

        # Check required fields per item
        required = schema.get("required_item_fields", [])
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for req_field in required:
                if req_field not in item or not item[req_field]:
                    return ValidationResult(
                        is_valid=False,
                        error=f"Item {i} falta campo requerido: '{req_field}'",
                        retry_hint=f"Reintentar — cada item necesita '{req_field}'",
                    )

        # Check require_one_of constraints
        require_one_of = schema.get("require_one_of", [])
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for group in require_one_of:
                if not any(item.get(k) for k in group):
                    return ValidationResult(
                        is_valid=False,
                        error=f"Item {i} necesita al menos uno de: {', '.join(group)}",
                        retry_hint=f"Reintentar — incluir source/target en relaciones",
                    )

    return ValidationResult(is_valid=True, parsed=parsed)
