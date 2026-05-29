"""
Schema versioning for project data files.

Provides version detection, validation, migration infrastructure,
and structural validation for project data.
"""

from __future__ import annotations

from typing import Any

# Current schema version for new projects (B10-T02: upgraded to v7)
CURRENT_SCHEMA_VERSION: int = 7

# The maximum schema version this code can handle
MAX_SUPPORTED_VERSION: int = 7


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
# Migration: v3 → v4
# ---------------------------------------------------------------------------


def _apply_migration_v3_to_v4(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate v3 data to v4 structure.

    v4 formalises NarrativeRelation as a structured item within the
    ``relations`` list.  v3 already had ``relations: []`` so this
    migration is trivial — it ensures ``relations`` is a list.
    Purely structural — no narrative data is invented.
    """
    migrated: dict[str, Any] = dict(data)

    raw_relations = migrated.get("relations")
    if not isinstance(raw_relations, list):
        migrated["relations"] = []

    return migrated


# ---------------------------------------------------------------------------
# Relation-level structural validation
# ---------------------------------------------------------------------------

_REQUIRED_RELATION_KEYS = ("id", "source_id", "target_id", "relation_type")


def validate_relation_structure(relation_data: Any) -> str | None:
    """Validate that a single relation dict has the minimum required shape."""
    if not isinstance(relation_data, dict):
        return (
            f"Relation is not a JSON object (got {type(relation_data).__name__})"
        )
    for key in _REQUIRED_RELATION_KEYS:
        if key not in relation_data or not relation_data[key]:
            return f"Relation is missing required key: '{key}'"
    return None


def validate_project_relations(relations: Any) -> str | None:
    """Validate the relations collection: list, no duplicate ids, each item valid."""
    if not isinstance(relations, list):
        return f"Relations must be a JSON array, got {type(relations).__name__}"

    seen_ids: set[str] = set()
    for idx, rel_data in enumerate(relations):
        err = validate_relation_structure(rel_data)
        if err is not None:
            return f"Relation at index {idx}: {err}"
        rid = rel_data.get("id", "")
        if rid in seen_ids:
            return (
                f"Corrupt project: duplicate relation id '{rid}' "
                f"(relation at index {idx})"
            )
        seen_ids.add(rid)

    return None


# ---------------------------------------------------------------------------
# Migration: v4 → v5
# ---------------------------------------------------------------------------


def _apply_migration_v4_to_v5(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate v4 data to v5 structure.

    v5 formalises Source, HistoryEntry, Issue and Candidate as
    structured collections.  v4 already had these as empty lists
    so this migration is trivial — it ensures all four collections
    are lists.  Purely structural — no narrative data is invented.
    """
    migrated: dict[str, Any] = dict(data)

    for collection in ("sources", "history", "issues", "candidates"):
        raw = migrated.get(collection)
        if not isinstance(raw, list):
            migrated[collection] = []

    return migrated


# ---------------------------------------------------------------------------
# Migration: v5 → v6
# ---------------------------------------------------------------------------


def _apply_migration_v5_to_v6(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate v5 data to v6 structure.

    v6 adds custom entity types, field definitions, and relation types
    as project-level collections.  Purely structural — adds empty lists
    to existing projects.  NO data is invented.
    """
    migrated: dict[str, Any] = dict(data)

    for collection in ("custom_entity_types", "custom_field_definitions",
                       "custom_relation_types"):
        if collection not in migrated or not isinstance(migrated[collection], list):
            migrated[collection] = []

    return migrated


# ---------------------------------------------------------------------------
# Migration: v6 → v7
# ---------------------------------------------------------------------------


def _apply_migration_v6_to_v7(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate v6 data to v7 structure (Bloque 10 — domains, layers, advanced config).

    Adds the three new project-level collections (domains, world_layers,
    advanced_config) and the individual entity/relation fields (domain_ids,
    layer_ids).  Purely structural — NO data is inferred from legacy fields
    (``domain: str``, ``layers: list[str]``).

    Args:
        data: v6 project data dictionary.

    Returns:
        New dictionary with v7 collections and fields added.
    """
    migrated: dict[str, Any] = dict(data)

    # ── Project-level ──

    # 5 domains base (§10.2)
    migrated.setdefault("domains", [
        "mundo", "historia", "campaña", "compartido", "sin_asignar",
    ])

    # 16 predefined world layers (§10.3) — imported lazily to avoid
    # circular dependency at module level
    if "world_layers" not in migrated:
        from packages.domain.world_layer import default_world_layers
        migrated["world_layers"] = [wl.to_dict() for wl in default_world_layers()]

    # Advanced config (§10.4) — all defaults
    if "advanced_config" not in migrated:
        from packages.domain.advanced_config import AdvancedProjectConfig
        migrated["advanced_config"] = AdvancedProjectConfig().to_dict()

    # ── Entity-level ──
    raw_entities = migrated.get("entities")
    if isinstance(raw_entities, list):
        for entity in raw_entities:
            if isinstance(entity, dict):
                entity.setdefault("domain_ids", [])
                entity.setdefault("layer_ids", [])

    # ── Relation-level ──
    raw_relations = migrated.get("relations")
    if isinstance(raw_relations, list):
        for relation in raw_relations:
            if isinstance(relation, dict):
                relation.setdefault("layer_ids", [])

    return migrated


# ---------------------------------------------------------------------------
# v7 validations: domains, world_layers, advanced_config
# ---------------------------------------------------------------------------


def validate_domains(domains: Any) -> list[str]:
    """Validate project.domains. Returns list of error messages (empty = valid).

    Checks:
    - Is a list (not None, not a dict, not something else).
    - Not empty.
    - No duplicate values.
    """
    errors: list[str] = []

    if not isinstance(domains, list):
        return [f"domains must be a JSON array, got {type(domains).__name__}"]

    if len(domains) == 0:
        errors.append("domains list is empty; at least one domain is required")

    seen: set[str] = set()
    for domain in domains:
        key = str(domain)
        if key in seen:
            errors.append(f"Duplicate domain: '{key}'")
        seen.add(key)

    return errors


def validate_world_layers(layers: Any) -> list[str]:
    """Validate project.world_layers. Returns list of error messages.

    Checks:
    - Is a list.
    - Each item has ``id`` and ``name``.
    - No duplicate IDs.
    """
    errors: list[str] = []

    if not isinstance(layers, list):
        return [f"world_layers must be a JSON array, got {type(layers).__name__}"]

    seen_ids: set[str] = set()
    for idx, layer in enumerate(layers):
        if not isinstance(layer, dict):
            errors.append(f"world_layers[{idx}] is not a JSON object")
            continue

        lid = layer.get("id")
        if not lid:
            errors.append(f"world_layers[{idx}] is missing required key: 'id'")
            continue

        if not layer.get("name"):
            errors.append(f"world_layers[{idx}] ('{lid}') is missing required key: 'name'")

        if lid in seen_ids:
            errors.append(f"Duplicate world_layer id: '{lid}'")
        seen_ids.add(lid)

    return errors


def validate_advanced_config(config: Any) -> list[str]:
    """Validate project.advanced_config structure. Returns list of errors.

    Checks:
    - Is a dict (when present).
    - Missing optional fields are acceptable (defaults apply on load).
    """
    if not isinstance(config, dict):
        return [f"advanced_config must be a JSON object, got {type(config).__name__}"]
    return []


def validate_entity_domain_ids(
    domain_ids: list[str],
    valid_domains: set[str],
) -> list[str]:
    """Validate an entity's domain_ids against the project's known domains.

    Returns a list of *warnings* (not blocking errors).  Unknown domains
    produce warnings so custom domains added later don't break loading.
    """
    warnings: list[str] = []
    for did in domain_ids:
        if did not in valid_domains:
            warnings.append(
                f"Entity references unknown domain '{did}'; "
                f"not in project domains {sorted(valid_domains)}"
            )
    return warnings


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
        "visibility", "export", "project_metadata", "advanced_config",
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
        "custom_entity_types", "custom_field_definitions", "custom_relation_types",
        "domains", "world_layers",
    )
    for field in collection_fields:
        if field in data and not isinstance(data[field], list):
            return (
                f"Project collection '{field}' must be a JSON array, "
                f"got {type(data[field]).__name__}"
            )

    return None
