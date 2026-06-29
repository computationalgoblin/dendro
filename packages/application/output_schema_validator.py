"""Output Schema Validator — B42-T05.

Validates AI output JSON by intent type. Invalid JSON produces a sanitized
error with retry hint — never crashes.

Schema enforcement checks that required fields exist per intent type.
Freeform/unknown intents always pass.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_FENCE_OPEN_RE = re.compile(r"^```[a-zA-Z0-9_-]*\s*")
_FENCE_CLOSE_RE = re.compile(r"\s*```\s*$")


def _coerce_json(text: str) -> Any:
    """Parsea JSON tolerando fences markdown y prosa alrededor del objeto.

    Los modelos reales a menudo envuelven la salida en ```json ... ``` o añaden un
    preámbulo en prosa, lo que rompe ``json.loads`` en el carácter 0. Se intenta:
    1) parseo directo, 2) quitar los fences, 3) extraer el objeto más externo
    ``{...}``. Lanza ``json.JSONDecodeError`` si no hay un objeto JSON parseable
    (incl. JSON truncado sin cierre), preservando el contrato de "inválido → error".
    """
    s = (text or "").strip()
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        pass
    if s.startswith("```"):
        inner = _FENCE_CLOSE_RE.sub("", _FENCE_OPEN_RE.sub("", s)).strip()
        try:
            return json.loads(inner)
        except (json.JSONDecodeError, ValueError):
            s = inner
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        return json.loads(s[start:end + 1])  # puede lanzar → inválido
    raise json.JSONDecodeError("no se encontró un objeto JSON", s or "", 0)


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
    "import_extraction": {
        "container_key": "candidates",
        "required_item_fields": ["kind"],
    },
    "import_map": {
        # I26: fase MAP — menciones por ventana. Cada mención lleva 'kind'; la
        # validación rica por tipo (body obligatorio, relation_type del vocabulario)
        # la hace el servicio al normalizar.
        "container_key": "mentions",
        "required_item_fields": ["kind"],
    },
    "import_reconcile": {
        # I27: fase REDUCE — el árbitro devuelve un objeto con el grafo consolidado;
        # estructura libre validada/normalizada por el servicio de reconciliación.
        "container_key": None,
        "required_fields": [],
        "optional_structure": True,
    },
    "import_project_config": {
        # Andamiaje del mundo (I22): objeto plano libre (chronology/config/
        # world_layers/milestones). Cualquier JSON válido pasa; el servicio normaliza.
        "container_key": None,
        "required_fields": [],
        "optional_structure": True,
    },
    "import_grouping": {
        # Agrupación estructural (I23): objeto con "branches"; cada rama puede traer
        # members/parent. Estructura opcional: cualquier JSON válido pasa y el servicio
        # normaliza/expande a candidatos branch + relaciones contiene.
        "container_key": "branches",
        "required_item_fields": [],
        "optional_structure": True,
    },
    "import_context_summary": {
        # Resumen no-canon del documento de referencia (modo contexto).
        "container_key": "topic_cards",
        "required_item_fields": [],
    },
}

# Intents that are always valid (freeform text)
_FREEFORM_INTENTS = {"freeform", "chat", "explain", "suggest", "improvise", "wizard_suggestion"}


# Keys that mean the model is trying to apply, canonize or persist changes
# instead of returning reviewable data. IDs are allowed because coherence repair
# patches may target already selected objects by id.
FORBIDDEN_MUTATION_KEYS: frozenset[str] = frozenset({
    "canon_state",
    "visibility_state",
    "final_action",
    "reviewed_at",
    "apply_directly",
    "auto_apply",
    "auto_accept",
    "mutate_canon",
    "direct_mutation",
    "canonize",
    "canonize_automatically",
    "canonizes_automatically",
    "write_to_project",
    "persist",
    "save_to_project",
    "project_store",
})


@dataclass
class ValidationResult:
    """Result of validating AI output against expected schema."""
    is_valid: bool
    parsed: dict[str, Any] | list | None = None
    error: str | None = None
    retry_hint: str | None = None


def _find_forbidden_mutation(value: Any, path: str = "$") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            next_path = f"{path}.{key_text}"
            if key_text.lower() in FORBIDDEN_MUTATION_KEYS:
                return next_path
            found = _find_forbidden_mutation(item, next_path)
            if found:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _find_forbidden_mutation(item, f"{path}[{index}]")
            if found:
                return found
    return None


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

    # Try to parse JSON (tolerante a fences markdown / prosa envolvente)
    try:
        parsed = _coerce_json(text)
    except (json.JSONDecodeError, ValueError) as e:
        return ValidationResult(
            is_valid=False,
            error=f"JSON inválido: {str(e)[:100]}",
            retry_hint="Reintentar — el modelo no produjo JSON válido",
        )

    forbidden_path = _find_forbidden_mutation(parsed)
    if forbidden_path:
        return ValidationResult(
            is_valid=False,
            error=f"Output intenta mutacion directa no permitida: {forbidden_path}",
            retry_hint="Reintentar: la IA debe devolver preview/candidate/suggestion, no mutacion canon directa",
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
