"""
Schema versioning for project data files.

Provides version detection, validation, migration infrastructure,
and structural validation for project data.
"""

from __future__ import annotations

from typing import Any

# Current schema version for new projects (G02: world time — eras + years)
CURRENT_SCHEMA_VERSION: int = 25

# The maximum schema version this code can handle
MAX_SUPPORTED_VERSION: int = 25


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

# ---------------------------------------------------------------------------
# Migration: v7 -> v8
# ---------------------------------------------------------------------------

CATEGORY_TO_TYPE: dict[str, str] = {
    "contradiction": "contradictory_relation",
    "contradiccion": "contradictory_relation",
    "warning": "no_description",
    "advertencia": "no_description",
    "error": "invalid_entity_type",
    "broken_relation": "broken_relation",
    "duplicate": "duplicate_entity",
}


def _apply_migration_v7_to_v8(data):
    legacy = data.get("issues", [])
    structured = []
    for item in legacy:
        if not isinstance(item, dict):
            continue
        cat = item.get("issue_type", "") or item.get("category", "")
        itype = CATEGORY_TO_TYPE.get(cat, "broken_relation")
        detected = item.get("created_at") or item.get("detected_at") or ""
        structured.append({
            "id": item.get("id", ""),
            "type": itype,
            "severity": item.get("severity", "media"),
            "state": item.get("state", "abierta"),
            "affected_entity_ids": [item["affected_entity_id"]] if item.get("affected_entity_id") else [],
            "affected_relation_ids": [item["affected_relation_id"]] if item.get("affected_relation_id") else [],
            "affected_source_ids": [item["affected_source_id"]] if item.get("affected_source_id") else [],
            "description": item.get("description", "") or item.get("title", ""),
            "evidence": item.get("evidence", ""),
            "possible_solutions": item.get("possible_solutions", []),
            "detected_at": detected,
            "reviewed_at": item.get("reviewed_at") or item.get("resolved_at"),
            "resolution": item.get("resolution", ""),
            "is_intentional": item.get("is_intentional", False),
            "metadata": {"legacy_category": cat} if cat and cat not in CATEGORY_TO_TYPE else {},
        })
    data["structured_issues"] = structured
    data["schema_version"] = 8
    return data




def _apply_migration_v8_to_v9(data):
    migrated = dict(data)
    migrated.setdefault('narrative_frameworks', [])
    migrated.setdefault('framework_templates', [])
    migrated['schema_version'] = 9
    return migrated



def _apply_migration_v9_to_v10(data):
    migrated = dict(data)
    candidates = migrated.get('candidates', [])
    for item in candidates:
        if isinstance(item, dict):
            item.setdefault('affected_entity_ids', [])
            item.setdefault('affected_relation_ids', [])
            item.setdefault('confidence', 0.5)
            item.setdefault('justification', '')
            item.setdefault('expected_impact', '')
            item.setdefault('possible_contradictions', [])
            item.setdefault('reviewed_at', None)
            item.setdefault('final_action', '')
            # Clamp confidence
            conf = item.get('confidence', 0.5)
            if isinstance(conf, (int, float)) and (conf < 0.0 or conf > 1.0):
                item['confidence'] = max(0.0, min(1.0, conf))
    migrated['schema_version'] = 10
    return migrated


# ---------------------------------------------------------------------------
# Migration: v10 -> v11
# ---------------------------------------------------------------------------


def _apply_migration_v10_to_v11(data):
    """v10 → v11: adds import_baskets collection."""
    migrated = dict(data)
    migrated.setdefault('import_baskets', [])
    migrated['schema_version'] = 11
    return migrated



def _apply_migration_v11_to_v12(data):
    migrated = dict(data)
    migrated.setdefault('timeline_events', [])
    migrated['schema_version'] = 12
    return migrated

def _apply_migration_v12_to_v13(data):
    migrated = dict(data)
    migrated.setdefault('writing_units', [])
    migrated['schema_version'] = 13
    return migrated

def _apply_migration_v13_to_v14(data):
    """v13 → v14: adds campaign collections (B20-T02)."""
    migrated = dict(data)
    migrated.setdefault('campaigns', [])
    migrated.setdefault('player_character_profiles', [])
    migrated.setdefault('campaign_clocks', [])
    migrated['schema_version'] = 14
    return migrated

def _apply_migration_v14_to_v15(data):
    """v14 → v15: adds secrets and clues collections (B21-T02)."""
    migrated = dict(data)
    migrated.setdefault('secrets', [])
    migrated.setdefault('clues', [])
    migrated['schema_version'] = 15
    return migrated

def _apply_migration_v15_to_v16(data):
    """v15 → v16: adds factions and fronts collections (B22-T02)."""
    migrated = dict(data)
    migrated.setdefault('factions', [])
    migrated.setdefault('fronts', [])
    migrated['schema_version'] = 16
    return migrated

def _apply_migration_v16_to_v17(data):
    """v16 → v17: adds sessions collection (B23-T02)."""
    migrated = dict(data)
    migrated.setdefault('sessions', [])
    migrated['schema_version'] = 17
    return migrated

def _apply_migration_v17_to_v18(data):
    """v17 → v18: adds post_session_summary and source_id to sessions (B25-T02)."""
    migrated = dict(data)
    for s in migrated.get('sessions', []):
        if isinstance(s, dict):
            s.setdefault('post_session_summary', '')
            s.setdefault('source_id', None)
    migrated['schema_version'] = 18
    return migrated


def _apply_migration_v18_to_v19(data):
    """v18 → v19: adds saved_graph_views collection (B28-T03)."""
    migrated = dict(data)
    migrated.setdefault('saved_graph_views', [])
    migrated['schema_version'] = 19
    return migrated


def _apply_migration_v19_to_v20(data):
    """v19 → v20: adds project_type, worldbuilding_active, creative_config, novela_config (B31-T03)."""
    migrated = dict(data)
    migrated.setdefault('project_type', 'otro')
    migrated.setdefault('worldbuilding_active', False)
    migrated.setdefault('creative_config', {})
    migrated.setdefault('novela_config', None)
    migrated['schema_version'] = 20
    return migrated


def _apply_migration_v20_to_v21(data):
    """v20 → v21: no structural changes — CONTENEDOR entity_type is enum-only (B31-T04)."""
    migrated = dict(data)
    migrated['schema_version'] = 21
    return migrated


def _apply_migration_v21_to_v22(data):
    """v21 → v22: expanded CreativeProjectConfig and AIConfig (B40).

    Adds new sub-objects to creative_config with sensible defaults.
    Old projects keep all existing fields and get empty defaults for new ones.
    Does NOT remove any existing data.
    """
    migrated = dict(data)

    # Expand creative_config with new B40 sub-objects
    cc = migrated.get("creative_config", {})
    cc.setdefault("core_premise", "")
    cc.setdefault("short_summary", "")
    cc.setdefault("development_status", "")
    cc.setdefault("format", "")
    cc.setdefault("creative_intent", {})
    cc.setdefault("narrative_engine", {})
    cc.setdefault("poetics", {})
    cc.setdefault("canon", {})
    cc.setdefault("negative_space", {})
    cc.setdefault("taste_memory", {})
    cc.setdefault("presets_applied", [])
    migrated["creative_config"] = cc

    # Expand ai config with new B40 fields
    ai = migrated.get("ai", {})
    ai.setdefault("default_role", "coauthor")
    ai.setdefault("change_aggressiveness", 5)
    ai.setdefault("default_num_options", 3)
    ai.setdefault("output_mode", "contrastive_options")
    ai.setdefault("uncertainty_policy", "conservative_proposal")
    ai.setdefault("default_strategy", "profundizar")
    ai.setdefault("context_depth", "balanced")
    migrated["ai"] = ai

    migrated["schema_version"] = 22
    return migrated


def _apply_migration_v22_to_v23(data):
    """v22 → v23: adds causal_milestones collection (B41-T01)."""
    migrated = dict(data)
    migrated.setdefault("causal_milestones", [])
    migrated["schema_version"] = 23
    return migrated


def _apply_migration_v23_to_v24(data):
    """v23 -> v24: adds project_chronology container (H02)."""
    migrated = dict(data)
    if not isinstance(migrated.get("project_chronology"), dict):
        from packages.domain.project_chronology import ProjectChronology
        migrated["project_chronology"] = ProjectChronology().to_dict()
    migrated["schema_version"] = 24
    return migrated


def _apply_migration_v24_to_v25(data):
    """v24 -> v25: world time (BETA1-G02).

    No-atemporalidad: garantiza era "Presente" + present_year en
    project_chronology y backfill de birth_year (entidades) y year (hitos)
    a 0. Sin pérdida, sin intervención manual.
    """
    migrated = dict(data)

    # 1-2. Chronology: era "Presente" + present_year
    chronology = migrated.get("project_chronology")
    if not isinstance(chronology, dict):
        from packages.domain.project_chronology import ProjectChronology
        chronology = ProjectChronology().to_dict()
    else:
        chronology = dict(chronology)
    if not isinstance(chronology.get("present_year"), int) or isinstance(chronology.get("present_year"), bool):
        chronology["present_year"] = 0
    eras = chronology.get("eras")
    if not isinstance(eras, list) or not eras:
        from packages.domain.era import Era
        chronology["eras"] = [
            Era(name="Presente", start_year=0, end_year=None, order=0).to_dict()
        ]
    migrated["project_chronology"] = chronology

    # 3. Backfill: entidades sin birth_year → 0; hitos sin year → 0
    entities = migrated.get("entities")
    if isinstance(entities, list):
        patched_entities = []
        for raw in entities:
            if isinstance(raw, dict):
                raw = dict(raw)
                if raw.get("birth_year") is None:
                    raw["birth_year"] = 0
                raw.setdefault("death_year", None)
            patched_entities.append(raw)
        migrated["entities"] = patched_entities

    milestones = migrated.get("causal_milestones")
    if isinstance(milestones, list):
        patched_milestones = []
        for raw in milestones:
            if isinstance(raw, dict):
                raw = dict(raw)
                if raw.get("year") is None:
                    raw["year"] = 0
            patched_milestones.append(raw)
        migrated["causal_milestones"] = patched_milestones

    migrated["schema_version"] = 25
    return migrated

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
        "project_chronology",
    )
    for section in config_sections:
        if section in data and not isinstance(data[section], dict):
            return (
                f"Project config section '{section}' must be a JSON object, "
                f"got {type(data[section]).__name__}"
            )

    # Collections must be lists when present
    collection_fields = (
        "entities", "relations", "sources", "history", "issues", "structured_issues", "narrative_frameworks", "framework_templates", "timeline_events", "writing_units",
        "custom_entity_types", "custom_field_definitions", "custom_relation_types",
        "domains", "world_layers", "import_baskets",
        "campaigns", "player_character_profiles", "campaign_clocks",
        "secrets", "clues",
        "factions", "fronts",
        "sessions", "saved_graph_views", "causal_milestones",
    )
    for field in collection_fields:
        if field in data and not isinstance(data[field], list):
            return (
                f"Project collection '{field}' must be a JSON array, "
                f"got {type(data[field]).__name__}"
            )


    return None


# --- Writing units structural validation (B19-T03) ---


def _validate_writing_units(units):
    """Validate structural integrity of writing_units list.

    Returns list of error messages (empty = OK).
    """
    errors = []
    if not isinstance(units, list):
        return [f"writing_units must be a list, got {type(units).__name__}"]

    ids = set()
    for i, u in enumerate(units):
        if not isinstance(u, dict):
            errors.append(f"writing_units[{i}] is not a dict")
            continue
        uid = u.get("id")
        if uid is None:
            errors.append(f"writing_units[{i}] missing id")
            continue
        if uid in ids:
            errors.append(f"writing_units[{i}] duplicate id '{uid}'")
        ids.add(uid)

    # Validate parent_id references and cycles
    unit_ids = {u.get("id") for u in units if isinstance(u, dict) and u.get("id")}
    for i, u in enumerate(units):
        if not isinstance(u, dict):
            continue
        pid = u.get("parent_id")
        if pid is not None and pid not in unit_ids:
            errors.append(f"writing_units[{i}] parent_id '{pid}' does not exist")

    # Cycle detection via DFS
    parent_map = {}
    for u in units:
        if isinstance(u, dict) and u.get("id"):
            parent_map[u["id"]] = u.get("parent_id")
    for uid in unit_ids:
        visited = set()
        current = uid
        while current in parent_map and parent_map[current] is not None:
            current = parent_map[current]
            if current in visited:
                errors.append(f"writing_units cycle detected involving '{current}'")
                break
            visited.add(current)

    return errors

# --- Campaign collections structural validation (B20-T02) ---


def _validate_campaigns(campaigns):
    """Validate structural integrity of campaigns list.

    Checks: is a list, unique IDs.
    Returns list of error messages (empty = OK).
    """
    errors = []
    if not isinstance(campaigns, list):
        return [f"campaigns must be a list, got {type(campaigns).__name__}"]

    ids = set()
    for i, c in enumerate(campaigns):
        if not isinstance(c, dict):
            errors.append(f"campaigns[{i}] is not a dict")
            continue
        cid = c.get("id")
        if cid is None:
            errors.append(f"campaigns[{i}] missing id")
            continue
        if cid in ids:
            errors.append(f"campaigns[{i}] duplicate id '{cid}'")
        ids.add(cid)

    return errors


def _validate_player_character_profiles(profiles):
    """Validate structural integrity of player_character_profiles list.

    Checks: is a list, unique IDs, entity_id mandatory (non-empty string).
    Returns list of error messages (empty = OK).
    """
    errors = []
    if not isinstance(profiles, list):
        return [f"player_character_profiles must be a list, got {type(profiles).__name__}"]

    ids = set()
    for i, p in enumerate(profiles):
        if not isinstance(p, dict):
            errors.append(f"player_character_profiles[{i}] is not a dict")
            continue
        pid = p.get("id")
        if pid is None:
            errors.append(f"player_character_profiles[{i}] missing id")
            continue
        if pid in ids:
            errors.append(f"player_character_profiles[{i}] duplicate id '{pid}'")
        ids.add(pid)

        # entity_id mandatory
        entity_id = p.get("entity_id")
        if not entity_id or not isinstance(entity_id, str) or not entity_id.strip():
            errors.append(
                f"player_character_profiles[{i}] entity_id is required "
                f"and must be a non-empty string"
            )

    return errors


def _validate_campaign_clocks(clocks, all_campaign_clock_ids=None):
    """Validate structural integrity of campaign_clocks list.

    Checks: is a list, unique IDs.
    If all_campaign_clock_ids is provided (set of clock IDs referenced from campaigns),
    also validates that campaign.clock_ids reference existing clocks.

    Returns list of error messages (empty = OK).
    """
    errors = []
    if not isinstance(clocks, list):
        return [f"campaign_clocks must be a list, got {type(clocks).__name__}"]

    clock_ids = set()
    for i, c in enumerate(clocks):
        if not isinstance(c, dict):
            errors.append(f"campaign_clocks[{i}] is not a dict")
            continue
        cid = c.get("id")
        if cid is None:
            errors.append(f"campaign_clocks[{i}] missing id")
            continue
        if cid in clock_ids:
            errors.append(f"campaign_clocks[{i}] duplicate id '{cid}'")
        clock_ids.add(cid)

    # Cross-reference: campaign.clock_ids must exist in campaign_clocks
    if all_campaign_clock_ids is not None:
        missing = all_campaign_clock_ids - clock_ids
        for m in sorted(missing):
            errors.append(f"campaign references clock_id '{m}' which does not exist in campaign_clocks")

    return errors

# --- Secrets and clues structural validation (B21-T02) ---


def _validate_secrets(secrets):
    """Validate structural integrity of secrets list."""
    errors = []
    if not isinstance(secrets, list):
        return [f"secrets must be a list, got {type(secrets).__name__}"]

    ids = set()
    for i, s in enumerate(secrets):
        if not isinstance(s, dict):
            errors.append(f"secrets[{i}] is not a dict")
            continue
        sid = s.get("id")
        if sid is None:
            errors.append(f"secrets[{i}] missing id")
            continue
        if sid in ids:
            errors.append(f"secrets[{i}] duplicate id '{sid}'")
        ids.add(sid)

        content = s.get("content")
        if not content or not isinstance(content, str) or not content.strip():
            errors.append(f"secrets[{i}] content is required and must be a non-empty string")

        entity_id = s.get("entity_id")
        if entity_id is not None and (not isinstance(entity_id, str) or not entity_id.strip()):
            errors.append(f"secrets[{i}] entity_id must be a non-empty string or null")

        importance = s.get("importance")
        if importance is not None and isinstance(importance, (int, float)) and not isinstance(importance, bool):
            if importance < 1 or importance > 5:
                errors.append(f"secrets[{i}] importance must be 1-5, got {importance}")

    return errors


def _validate_clues(clues, all_secret_ids=None):
    """Validate structural integrity of clues list."""
    errors = []
    if not isinstance(clues, list):
        return [f"clues must be a list, got {type(clues).__name__}"]

    ids = set()
    for i, c in enumerate(clues):
        if not isinstance(c, dict):
            errors.append(f"clues[{i}] is not a dict")
            continue
        cid = c.get("id")
        if cid is None:
            errors.append(f"clues[{i}] missing id")
            continue
        if cid in ids:
            errors.append(f"clues[{i}] duplicate id '{cid}'")
        ids.add(cid)

        content = c.get("content")
        if not content or not isinstance(content, str) or not content.strip():
            errors.append(f"clues[{i}] content is required and must be a non-empty string")

        entity_id = c.get("entity_id")
        if entity_id is not None and (not isinstance(entity_id, str) or not entity_id.strip()):
            errors.append(f"clues[{i}] entity_id must be a non-empty string or null")

        for field, name in [("clarity", "clarity"), ("redundancy", "redundancy"), ("loss_risk", "loss_risk")]:
            val = c.get(field)
            if val is not None and isinstance(val, (int, float)) and not isinstance(val, bool):
                if val < 1 or val > 5:
                    errors.append(f"clues[{i}] {name} must be 1-5, got {val}")

    if all_secret_ids is not None:
        for i, c in enumerate(clues):
            if not isinstance(c, dict):
                continue
            secret_id = c.get("associated_secret_id")
            if secret_id and isinstance(secret_id, str) and secret_id.strip():
                if secret_id not in all_secret_ids:
                    errors.append(
                        f"clues[{i}] associated_secret_id '{secret_id}' "
                        f"does not exist in secrets"
                    )

    return errors


def _validate_factions(factions):
    """Validate structural integrity of factions list."""
    errors = []
    if not isinstance(factions, list):
        return [f"factions must be a list, got {type(factions).__name__}"]
    valid_states = {"activa", "debilitada", "destruida", "inactiva"}
    ids = set()
    for i, f in enumerate(factions):
        if not isinstance(f, dict): errors.append(f"factions[{i}] is not a dict"); continue
        fid = f.get("id")
        if fid is None: errors.append(f"factions[{i}] missing id"); continue
        if fid in ids: errors.append(f"factions[{i}] duplicate id '{fid}'"); continue
        ids.add(fid)
        entity_id = f.get("entity_id")
        if not entity_id or not isinstance(entity_id, str) or not entity_id.strip():
            errors.append(f"factions[{i}] entity_id is required")
        state = f.get("state")
        if state is not None and isinstance(state, str) and state not in valid_states:
            errors.append(f"factions[{i}] invalid state '{state}'")
    return errors

def _validate_fronts(fronts):
    """Validate structural integrity of fronts list."""
    errors = []
    if not isinstance(fronts, list):
        return [f"fronts must be a list, got {type(fronts).__name__}"]
    valid_front_types = {"frente", "amenaza", "inminente"}
    valid_front_states = {"latente", "activo", "contenido", "resuelto"}
    ids = set()
    for i, f in enumerate(fronts):
        if not isinstance(f, dict): errors.append(f"fronts[{i}] is not a dict"); continue
        fid = f.get("id")
        if fid is None: errors.append(f"fronts[{i}] missing id"); continue
        if fid in ids: errors.append(f"fronts[{i}] duplicate id '{fid}'"); continue
        ids.add(fid)
        name = f.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            errors.append(f"fronts[{i}] name is required")
        ft = f.get("front_type")
        if ft is not None and isinstance(ft, str) and ft not in valid_front_types:
            errors.append(f"fronts[{i}] invalid front_type '{ft}'")
        fs = f.get("state")
        if fs is not None and isinstance(fs, str) and fs not in valid_front_states:
            errors.append(f"fronts[{i}] invalid state '{fs}'")
        stages = f.get("stages")
        if isinstance(stages, list):
            stage_index = f.get("current_stage_index", 0)
            if isinstance(stage_index, (int, float)) and not isinstance(stage_index, bool):
                si = int(stage_index)
                if si < 0 or (len(stages) > 0 and si >= len(stages)):
                    errors.append(f"fronts[{i}] current_stage_index {si} out of range for {len(stages)} stages")
            for si, stage in enumerate(stages):
                if isinstance(stage, dict):
                    sn = stage.get("name")
                    if not sn or not isinstance(sn, str) or not sn.strip():
                        errors.append(f"fronts[{i}].stages[{si}] name is required")
                    st = stage.get("threshold")
                    if st is not None and isinstance(st, (int, float)) and not isinstance(st, bool) and st < 0:
                        errors.append(f"fronts[{i}].stages[{si}] threshold must be >= 0")
    return errors

def _validate_sessions(sessions):
    errors = []
    if not isinstance(sessions, list): return [f"sessions must be a list, got {type(sessions).__name__}"]
    valid_states = {"preparacion", "activa", "completada", "archivada"}
    valid_scene_types = {"prevista", "opcional", "improvisada"}
    ids = set()
    for i, s in enumerate(sessions):
        if not isinstance(s, dict): errors.append(f"sessions[{i}] is not a dict"); continue
        sid = s.get("id")
        if sid is None: errors.append(f"sessions[{i}] missing id"); continue
        if sid in ids: errors.append(f"sessions[{i}] duplicate id '{sid}'"); continue
        ids.add(sid)
        if not isinstance(s.get("campaign_id"), str) or not s["campaign_id"].strip(): errors.append(f"sessions[{i}] campaign_id is required")
        if not isinstance(s.get("name"), str) or not s["name"].strip(): errors.append(f"sessions[{i}] name is required")
        st = s.get("state")
        if st is not None and isinstance(st, str) and st not in valid_states: errors.append(f"sessions[{i}] invalid state '{st}'")
        for list_name in ("clock_ids", "available_clue_ids", "revealable_secret_ids", "relevant_faction_ids", "planned_location_ids", "planned_npc_ids", "active_conflict_ids"):
            if list_name in s and not isinstance(s[list_name], list): errors.append(f"sessions[{i}] {list_name} must be a list")
        for scene_list in ("planned_scenes", "optional_scenes"):
            scenes = s.get(scene_list)
            if isinstance(scenes, list):
                for si, sc in enumerate(scenes):
                    if isinstance(sc, dict):
                        if not isinstance(sc.get("name"), str) or not sc["name"].strip(): errors.append(f"sessions[{i}].{scene_list}[{si}] name is required")
                        if not isinstance(sc.get("id"), str) or not sc["id"].strip(): errors.append(f"sessions[{i}].{scene_list}[{si}] id is required")
                        sct = sc.get("scene_type")
                        if sct is not None and isinstance(sct, str) and sct not in valid_scene_types: errors.append(f"sessions[{i}].{scene_list}[{si}] invalid scene_type '{sct}'")
    return errors
