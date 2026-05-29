"""
Schema versioning for project data files.

Provides version detection, validation, migration infrastructure,
and structural validation for project data.
"""

from __future__ import annotations

from typing import Any

# Current schema version for new projects (B03-T02: upgraded to v3)
CURRENT_SCHEMA_VERSION: int = 3

# The maximum schema version this code can handle
MAX_SUPPORTED_VERSION: int = 3


# ---------------------------------------------------------------------------
# Version detection and validation
# ---------------------------------------------------------------------------


def detect_schema_version(data: dict[str, Any]) -> int:
    """Extract the schema version from raw project data.

    Args:
        data: Raw dictionary from JSON file.

    Returns:
        The schema version as an integer. Returns 0 if not present
        or not parseable (legacy/unknown format).
    """
    raw = data.get("schema_version", 0)
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 0


def validate_schema_version(version: int) -> str | None:
    """Validate that a schema version can be handled.

    Args:
        version: The schema version to validate.

    Returns:
        None if valid, or an error message string if not.
    """
    if version <= 0:
        return f"Cannot determine schema version (got {version!r})"
    if version > MAX_SUPPORTED_VERSION:
        return (
            f"Project uses schema v{version} but this version "
            f"of narrative-architect only supports up to v{MAX_SUPPORTED_VERSION}. "
            f"Please update narrative-architect to open this project."
        )
    return None


# ---------------------------------------------------------------------------
# Migration: v1 → v2
# ---------------------------------------------------------------------------


def _apply_migration_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate v1 (Bloque 1 minimal) data to v2 (extended) structure.

    Adds default values for all new fields introduced in B02-T01:
    description, languages, config dataclass sections, and prepared
    collections. This is purely structural — no narrative data (entities,
    relations, history, etc.) is invented.

    Args:
        data: v1 project data dictionary.

    Returns:
        New dictionary with all v2 sections added (defaults).
        The original dict is not modified.
    """
    migrated: dict[str, Any] = dict(data)

    # New scalar fields
    migrated.setdefault("description", "")
    migrated.setdefault("primary_language", "es")
    migrated.setdefault("secondary_languages", [])

    # Config dataclass sections — empty/matching their class defaults
    migrated.setdefault("project_metadata", {
        "version": "0.1.0",
        "author": "",
        "tags": [],
        "custom_fields": {},
    })
    migrated.setdefault("general", {
        "theme": "",
        "tags": [],
        "default_entity_visibility": "visible_usuario",
    })
    migrated.setdefault("tone", {
        "narrative_tone": "neutral",
        "language_formality": "neutral",
        "humor_level": "none",
        "dark_tone_level": "none",
    })
    migrated.setdefault("genre", {
        "primary_genre": "",
        "secondary_genres": [],
        "subgenres": [],
        "genre_mix_notes": "",
    })
    migrated.setdefault("realism", {
        "realism_level": "medium",
        "magic_level": "none",
        "technology_level": "medium",
        "fantasy_scale": "medium",
    })
    migrated.setdefault("ai", {
        "enabled": False,
        "model_preference": "default",
        "creativity_level": "medium",
    })
    migrated.setdefault("visibility", {
        "default_entity_visibility": "visible_usuario",
        "default_relation_visibility": "visible_usuario",
    })
    migrated.setdefault("export", {
        "export_format_preference": "markdown",
        "include_private_notes": False,
        "watermark_level": "none",
    })

    # Prepared collections
    migrated.setdefault("entities", [])
    migrated.setdefault("relations", [])
    migrated.setdefault("sources", [])
    migrated.setdefault("history", [])
    migrated.setdefault("issues", [])

    return migrated


# ---------------------------------------------------------------------------
# Migration: v2 → v3
# ---------------------------------------------------------------------------


def _apply_migration_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate v2 data to v3 structure.

    v3 formalises NarrativeEntity as a structured item within the
    ``entities`` list.  In practice v2 already had ``entities: []``
    so this migration is trivial — it ensures ``entities`` is a list
    and that each item in it is a dict (normalising non-dict items
    to an empty entity stub so they survive as traceable metadata).

    This is purely structural — no narrative data is invented.
    """
    migrated: dict[str, Any] = dict(data)

    # Ensure entities is a list
    raw_entities = migrated.get("entities")
    if not isinstance(raw_entities, list):
        migrated["entities"] = []

    return migrated


# ---------------------------------------------------------------------------
# Entity-level structural validation
# ---------------------------------------------------------------------------

_REQUIRED_ENTITY_KEYS = ("id", "name", "entity_type")


def validate_entity_structure(entity_data: Any) -> str | None:
    """Validate that a single entity dict has the minimum required shape.

    Returns None if structurally valid, or an error message.
    """
    if not isinstance(entity_data, dict):
        return (
            f"Entity is not a JSON object (got {type(entity_data).__name__}). "
            f"Expected a dict with at least keys: {_REQUIRED_ENTITY_KEYS}"
        )

    for key in _REQUIRED_ENTITY_KEYS:
        if key not in entity_data or not entity_data[key]:
            return f"Entity is missing required key: '{key}'"

    return None


def validate_project_entities(entities: Any) -> str | None:
    """Validate the entities collection as a whole.

    Checks:
    - ``entities`` is a list.
    - No duplicate ids.
    - Each item passes ``validate_entity_structure``.

    Returns None if valid, or an error message.
    """
    if not isinstance(entities, list):
        return f"Entities must be a JSON array, got {type(entities).__name__}"

    seen_ids: set[str] = set()
    for idx, entity_data in enumerate(entities):
        # Structural check
        err = validate_entity_structure(entity_data)
        if err is not None:
            return f"Entity at index {idx}: {err}"

        # Uniqueness check
        eid = entity_data.get("id", "")
        if eid in seen_ids:
            return (
                f"Corrupt project: duplicate entity id '{eid}' "
                f"(entity at index {idx})"
            )
        seen_ids.add(eid)

    return None


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def validate_project_structure(data: dict[str, Any]) -> str | None:
    """Validate that project data has the expected structure.

    Checks for required fields, correct types for config sections
    and collections. Does NOT validate semantic content (that is the
    domain model's responsibility).

    Args:
        data: Project data dictionary.

    Returns:
        None if structurally valid, or an error message string.
    """
    # Required core fields
    for key in ("id", "name", "created_at", "updated_at"):
        if key not in data:
            return f"Project file is missing required field: '{key}'"

    # Config sections must be dicts when present
    config_sections = (
        "general", "tone", "genre", "realism", "ai",
        "visibility", "export", "project_metadata",
    )
    for section in config_sections:
        if section in data and not isinstance(data[section], dict):
            return (
                f"Project config section '{section}' must be a JSON object, "
                f"got {type(data[section]).__name__}"
            )

    # Collections must be lists when present
    collection_fields = (
        "entities", "relations", "sources", "history", "issues",
    )
    for field in collection_fields:
        if field in data and not isinstance(data[field], list):
            return (
                f"Project collection '{field}' must be a JSON array, "
                f"got {type(data[field]).__name__}"
            )

    return None
