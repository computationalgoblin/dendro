"""
Schema versioning for project data files.

Provides version detection, validation, migration infrastructure,
and structural validation for project data.
"""

from __future__ import annotations

from typing import Any

# Current schema version for new projects
# (v39: BETA2-WIKI-02 — página de wiki: NarrativeMemory gana cuerpo/wikilinks/tags)
CURRENT_SCHEMA_VERSION: int = 40

# The maximum schema version this code can handle
MAX_SUPPORTED_VERSION: int = 40


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

    # Advanced config (§10.4) — placeholder; PA04 (v30→v31) lo descarta luego.
    if "advanced_config" not in migrated:
        migrated["advanced_config"] = {}

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

def _apply_migration_v25_to_v26(data: dict[str, Any]) -> dict[str, Any]:
    """v25 → v26: relation temporal fields (BETA1-G06).

    Promotes birth_year/death_year from custom_metadata to first-class
    relation fields. Relations without those metadata keys default to None.
    """
    migrated = dict(data)
    relations = migrated.get("relations")
    if isinstance(relations, list):
        patched = []
        for raw in relations:
            if isinstance(raw, dict):
                raw = dict(raw)
                meta = raw.get("custom_metadata") or {}
                # Promote from metadata if present; otherwise default to None.
                if "birth_year" not in raw:
                    raw["birth_year"] = _parse_int_or_none(meta.get("birth_year"))
                if "death_year" not in raw:
                    raw["death_year"] = _parse_int_or_none(meta.get("death_year"))
            patched.append(raw)
        migrated["relations"] = patched
    migrated["schema_version"] = 26
    return migrated


def _parse_int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_J27_UNFOUNDED_NOTE = "no fundamentado (migración v27)"


def _build_life_span_dict(
    birth: int | None, death: int | None, present_year: int
) -> dict[str, Any]:
    """BETA1-J27: construye el dict de ``TemporalSpan`` desde el espejo entero.

    Marca el inicio como **incierto / no fundamentado** cuando el año falta o
    coincide con ``present_year`` (default por inercia de v25). No pierde el
    año. Reutiliza los modelos de dominio para serializar con la forma canónica.
    """
    from packages.domain.temporal_models import EventTemporality, TemporalPrecision
    from packages.domain.temporal_span import TemporalSpan

    unfounded = birth is None or birth == present_year
    start = EventTemporality(
        year=birth,
        precision=TemporalPrecision.UNKNOWN if unfounded else TemporalPrecision.EXACT,
        notes=_J27_UNFOUNDED_NOTE if unfounded else "",
    )
    end = (
        EventTemporality(year=death, precision=TemporalPrecision.EXACT)
        if death is not None
        else None
    )
    return TemporalSpan(start=start, end=end, ongoing=death is None).to_dict()


def _apply_migration_v26_to_v27(data: dict[str, Any]) -> dict[str, Any]:
    """v26 → v27: lapso temporal rico (BETA1-J01).

    Añade ``life_span`` a entidades y relaciones a partir de su
    ``birth_year``/``death_year``, marcando como **incierto** lo que venía del
    default ``present_year`` (sin perder el año). Los hitos no ganan campo
    nuevo (su ``temporal_span`` es vista computada); se refleja el año y la
    marca de incertidumbre en su ``temporality`` rico ya persistido.
    """
    migrated = dict(data)

    chronology = migrated.get("project_chronology")
    present_year = 0
    if isinstance(chronology, dict):
        present_year = _parse_int_or_none(chronology.get("present_year")) or 0

    for collection in ("entities", "relations"):
        items = migrated.get(collection)
        if not isinstance(items, list):
            continue
        patched = []
        for raw in items:
            if isinstance(raw, dict) and not isinstance(raw.get("life_span"), dict):
                raw = dict(raw)
                raw["life_span"] = _build_life_span_dict(
                    _parse_int_or_none(raw.get("birth_year")),
                    _parse_int_or_none(raw.get("death_year")),
                    present_year,
                )
            patched.append(raw)
        migrated[collection] = patched

    milestones = migrated.get("causal_milestones")
    if isinstance(milestones, list):
        patched_m = []
        for raw in milestones:
            if isinstance(raw, dict):
                raw = dict(raw)
                year = _parse_int_or_none(raw.get("year"))
                temporality = raw.get("temporality")
                temporality = dict(temporality) if isinstance(temporality, dict) else {}
                # Reflejar el año entero en el temporality rico si falta.
                if temporality.get("year") is None:
                    temporality["year"] = year
                # Marcar incierto lo derivado del presente sin otra evidencia.
                if (year is None or year == present_year) and not temporality.get("world_date"):
                    if temporality.get("precision") in (None, "unknown"):
                        temporality["precision"] = "unknown"
                        if not temporality.get("notes"):
                            temporality["notes"] = _J27_UNFOUNDED_NOTE
                raw["temporality"] = temporality
            patched_m.append(raw)
        migrated["causal_milestones"] = patched_m

    migrated["schema_version"] = 27
    return migrated


def _apply_migration_v27_to_v28(data: dict[str, Any]) -> dict[str, Any]:
    """v27 → v28: recorrido cronológico persistente (CRON).

    Aditiva y sin pérdida: inicializa las colecciones de sesiones e informes
    del Modo Creación Cronológica si no existen. No toca canon.
    """
    migrated = dict(data)
    migrated.setdefault("chronology_walk_sessions", [])
    migrated.setdefault("chronology_walk_reports", [])
    migrated["schema_version"] = 28
    return migrated


def _apply_migration_v28_to_v29(data: dict[str, Any]) -> dict[str, Any]:
    """v28 → v29: modos de importación (canon/contexto) + taxonomía de proyecto.

    Aditiva y sin pérdida: inicializa la taxonomía de importación si no existe
    y marca los baskets previos como modo ``canon`` (comportamiento histórico).
    No toca canon.
    """
    migrated = dict(data)
    migrated.setdefault(
        "import_taxonomy",
        {
            "allowed_entity_types": [],
            "allowed_branch_types": [],
            "allowed_ring_ids": [],
            "extraction_guidance": "",
            "strict": False,
        },
    )
    baskets = migrated.get("import_baskets")
    if isinstance(baskets, list):
        for basket in baskets:
            if isinstance(basket, dict):
                basket.setdefault("import_mode", "canon")
                meta = basket.get("metadata")
                if isinstance(meta, dict):
                    meta.setdefault("import_mode", "canon")
    migrated["schema_version"] = 29
    return migrated


def _apply_migration_v29_to_v30(data: dict[str, Any]) -> dict[str, Any]:
    """v29 → v30: versionado del troceado de documentos importados (I11).

    Aditiva y sin pérdida: marca los segmentos ya persistidos con
    ``chunking_version: 1`` (troceado histórico por párrafo). Los imports nuevos
    usan el troceado con tamaño objetivo y sellan ``chunking_version: 2``. No
    re-trocea (eso es una acción opt-in explícita); no toca canon ni el corpus
    (que es in-memory y se reconstruye al reindexar).
    """
    migrated = dict(data)
    baskets = migrated.get("import_baskets")
    if isinstance(baskets, list):
        for basket in baskets:
            if not isinstance(basket, dict):
                continue
            for segment in basket.get("segments", []) or []:
                if not isinstance(segment, dict):
                    continue
                meta = segment.get("metadata")
                if isinstance(meta, dict):
                    meta.setdefault("chunking_version", 1)
    migrated["schema_version"] = 30
    return migrated


def _strip_accents(text: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _norm_token(value: Any) -> str:
    """Normaliza un texto a token comparable (minúsculas, sin acentos, _)."""
    if not isinstance(value, str):
        return ""
    return _strip_accents(value.strip().lower()).replace(" ", "_").replace("-", "_")


def _pick_option(value: Any, options: list[str]) -> str:
    """Devuelve el valor normalizado si encaja en options; si no, ""."""
    token = _norm_token(value)
    return token if token in options else ""


def _first_option(value: Any, options: list[str]) -> str:
    """Para listas viejas → primer elemento que encaje en options."""
    if isinstance(value, list):
        for item in value:
            picked = _pick_option(item, options)
            if picked:
                return picked
    return _pick_option(value, options)


def _scale3(value: Any, low: str, mid: str, high: str) -> str:
    """Mapea un slider 0-10 a tres categorías. No-int → ""."""
    if isinstance(value, bool) or not isinstance(value, int):
        return ""
    if value <= 3:
        return low
    if value <= 6:
        return mid
    return high


def _scale3_5(value: Any, options: list[str]) -> str:
    """Mapea un slider 0-10 a cinco categorías (options con 5 niveles)."""
    if isinstance(value, bool) or not isinstance(value, int) or len(options) != 5:
        return ""
    buckets = (1, 3, 6, 8, 10)  # convencional..muy_autoral
    for idx, top in enumerate(buckets):
        if value <= top:
            return options[idx]
    return options[-1]


def _apply_migration_v30_to_v31(data: dict[str, Any]) -> dict[str, Any]:
    """v30 → v31 (PA04): config creativa canónica de 30 campos.

    Colapsa las tres generaciones de configuración (Gen A ``genre/tone/realism/...``,
    Gen B ``advanced_config`` y los dicts sin esquema de B40 en ``creative_config``)
    en una única ``creative_config`` tipada de 5 secciones. Convierte sliders 0-10 a
    categorías, fusiona las listas de espacio negativo en ``evitar`` y descarta todo
    lo eliminado (config IA editable, taxonomía, novela_config, metadata estructurada).
    Sin pérdida de los 30 campos conservados; lo demás se descarta a propósito.
    """
    from packages.domain.creative_config import (
        AGENCIA_OPCIONES,
        AMBIGUEDAD_OPCIONES,
        CAMBIO_PERSONAJE_OPCIONES,
        CAUSALIDAD_OPCIONES,
        DENSIDAD_OPCIONES,
        ESCALADA_OPCIONES,
        ESTADO_OPCIONES,
        EXPOSICION_OPCIONES,
        FUENTE_CONFLICTO_OPCIONES,
        GRADO_ESPECULATIVO_OPCIONES,
        MECANISMO_OPCIONES,
        ORIGINALIDAD_OPCIONES,
        REALISMO_OPCIONES,
    )

    migrated = dict(data)
    cc = migrated.get("creative_config") if isinstance(migrated.get("creative_config"), dict) else {}
    genre = migrated.get("genre") if isinstance(migrated.get("genre"), dict) else {}
    tone = migrated.get("tone") if isinstance(migrated.get("tone"), dict) else {}
    realism = migrated.get("realism") if isinstance(migrated.get("realism"), dict) else {}
    advanced = migrated.get("advanced_config") if isinstance(migrated.get("advanced_config"), dict) else {}
    intent = cc.get("creative_intent") if isinstance(cc.get("creative_intent"), dict) else {}
    engine = cc.get("narrative_engine") if isinstance(cc.get("narrative_engine"), dict) else {}
    poetics = cc.get("poetics") if isinstance(cc.get("poetics"), dict) else {}
    canon = cc.get("canon") if isinstance(cc.get("canon"), dict) else {}
    negative = cc.get("negative_space") if isinstance(cc.get("negative_space"), dict) else {}

    def _list(d: dict, key: str) -> list[str]:
        v = d.get(key)
        return [str(x) for x in v if str(x).strip()] if isinstance(v, list) else []

    def _str(d: dict, key: str) -> str:
        v = d.get(key)
        return v.strip() if isinstance(v, str) else ""

    # ── Estado: idea/borrador/expansion/revision/activa/archivado → nuevas opciones ──
    estado_old = _norm_token(cc.get("development_status"))
    estado_map = {
        "idea": "exploracion",
        "borrador": "borrador",
        "expansion": "produccion",
        "revision": "canon_en_consolidacion",
        "activa": "campana_activa",
        "archivado": "borrador",
    }
    estado = estado_map.get(estado_old, estado_old if estado_old in ESTADO_OPCIONES else "")

    # ── Grado especulativo: deriva de magia/fantasía/tecnología (best-effort) ──
    spec_tokens = {_norm_token(realism.get(k)) for k in ("magic_level", "fantasy_scale", "technology_level")}
    if spec_tokens & {"high", "alto", "prevalent", "epico"}:
        grado_especulativo = "alto"
    elif spec_tokens & {"medium", "medio", "moderate", "rare"}:
        grado_especulativo = "moderado"
    elif spec_tokens & {"none", "ninguno", "low", "bajo"}:
        grado_especulativo = "realista"
    else:
        grado_especulativo = ""

    # ── Evitar: fusión de las 5 listas de negative_space + tics de estilo ──
    evitar: list[str] = []
    for key in ("avoid_tropes", "avoid_solutions", "avoid_style_habits", "avoid_tones", "avoid_phrases"):
        evitar.extend(_list(negative, key))
    evitar.extend(_list(poetics, "forbidden_style_habits"))

    nueva_cc = {
        "identidad": {
            "premisa": _str(cc, "core_premise"),
            "resumen_corto": _str(cc, "short_summary"),
            "genero_principal": _str(genre, "primary_genre") or _str(advanced, "primary_genre"),
            "subgeneros": _list(genre, "subgenres") or _list(advanced, "subgenres"),
            "formato": _str(cc, "format"),
            "publico": _str(cc, "target_audience"),
            "estado": estado,
        },
        "direccion": {
            "promesa": _str(intent, "reader_promise"),
            "pregunta_dramatica": _str(intent, "central_question"),
            "temas": _list(cc, "main_themes"),
            "emociones": _list(intent, "desired_emotions"),
            "sensacion_final": _str(intent, "aftertaste"),
            "originalidad": _scale3_5(intent.get("originality"), ORIGINALIDAD_OPCIONES),
            "ambiguedad": _scale3(intent.get("ambiguity"), *AMBIGUEDAD_OPCIONES),
            "tipo_impacto": _list(intent, "impact_types"),
        },
        "motor": {
            "fuente_conflicto": _first_option(engine.get("conflict_sources"), FUENTE_CONFLICTO_OPCIONES),
            "mecanismo": _pick_option(engine.get("progression_mechanism"), MECANISMO_OPCIONES)
            or _pick_option(engine.get("dominant_tension"), MECANISMO_OPCIONES),
            "causalidad": _scale3(engine.get("causality"), "suave", "", "estricta")
            or _pick_option(engine.get("causality"), CAUSALIDAD_OPCIONES),
            "agencia": _scale3(engine.get("character_agency"), "baja", "media", "alta")
            or _pick_option(engine.get("character_agency"), AGENCIA_OPCIONES),
            "escalada": _pick_option(engine.get("escalation"), ESCALADA_OPCIONES),
            "cambio_personaje": _pick_option(engine.get("character_change"), CAMBIO_PERSONAJE_OPCIONES),
        },
        "estilo": {
            "tono": _str(tone, "narrative_tone"),
            "realismo": {"low": "bajo", "medium": "medio", "high": "alto"}.get(
                _norm_token(realism.get("realism_level")),
                _pick_option(realism.get("realism_level"), REALISMO_OPCIONES),
            ),
            "grado_especulativo": grado_especulativo if grado_especulativo in GRADO_ESPECULATIVO_OPCIONES else "",
            "estilo_narrativo": _str(cc, "narrative_style"),
            "densidad": _scale3(poetics.get("description_density"), *DENSIDAD_OPCIONES),
            "exposicion": _first_option(poetics.get("exposition_modes"), EXPOSICION_OPCIONES),
        },
        "reglas": {
            "reglas_canon": _list(canon, "hard_rules"),
            "evitar": evitar,
        },
    }
    migrated["creative_config"] = nueva_cc

    # Descartar estructuras eliminadas en PA04.
    for dead in (
        "general", "tone", "genre", "realism", "ai", "visibility", "export",
        "project_metadata", "advanced_config", "novela_config", "import_taxonomy",
    ):
        migrated.pop(dead, None)

    migrated["schema_version"] = 31
    return migrated


# ---------------------------------------------------------------------------
# Migration: v31 → v32
# ---------------------------------------------------------------------------


def _apply_migration_v31_to_v32(data: dict[str, Any]) -> dict[str, Any]:
    """v31 → v32 (I25): rediseño de importación map→reduce — romper compat.

    El nuevo pipeline (extracción a menciones → reconciliación → grafo
    consolidado) usa una forma de candidato incompatible con la anterior. Al
    estar en beta, se descartan los candidatos de importación viejos: por cada
    ``ImportBasket`` se vacían ``import_candidates`` y se resetea el progreso de
    extracción IA (``ai_extraction``/``ai_grouping`` en metadata) para que el
    basket pueda reprocesarse limpio con el pipeline nuevo. Se CONSERVAN los
    ``segments`` (texto ya extraído, sin re-subir el documento), el vínculo a la
    ``Source`` y todo el canon (entidades, relaciones, cronología) intacto.
    """
    migrated = dict(data)

    baskets = migrated.get("import_baskets")
    if isinstance(baskets, list):
        new_baskets: list[dict[str, Any]] = []
        for basket in baskets:
            if not isinstance(basket, dict):
                continue
            nb = dict(basket)
            nb["import_candidates"] = []
            nb["graph"] = None
            nb["review_state"] = "pendiente"
            meta = nb.get("metadata")
            meta = dict(meta) if isinstance(meta, dict) else {}
            # Resetear progreso de extracción/agrupación del formato viejo.
            meta.pop("ai_extraction", None)
            meta.pop("ai_grouping", None)
            meta["schema_v32_reset"] = True
            nb["metadata"] = meta
            new_baskets.append(nb)
        migrated["import_baskets"] = new_baskets

    migrated["schema_version"] = 32
    return migrated


# ---------------------------------------------------------------------------
# Migration: v32 → v33
# ---------------------------------------------------------------------------


def _apply_migration_v32_to_v33(data: dict[str, Any]) -> dict[str, Any]:
    """v32 → v33 (BETA2-FOCO): jardín narrativo — riego de entidades.

    Cambio puramente aditivo: introduce las colecciones de riego a nivel de
    proyecto — ``watering_diagnostics`` (historial de diagnósticos IA por
    entidad) y ``watering_paused_entity_ids`` (entidades "secadas", fuera del
    ciclo de riego). Los proyectos antiguos cargan con ambas vacías; el canon
    (entidades, relaciones, cronología, candidatos) queda intacto.
    """
    migrated = dict(data)
    migrated.setdefault("watering_diagnostics", [])
    migrated.setdefault("watering_paused_entity_ids", [])
    migrated["schema_version"] = 33
    return migrated


# ---------------------------------------------------------------------------
# Migration: v33 → v34
# ---------------------------------------------------------------------------


def _apply_migration_v33_to_v34(data: dict[str, Any]) -> dict[str, Any]:
    """v33 → v34 (BETA2-FOCO-16): canon total.

    Decisión de producto: algo es canon salvo que haya sido declarado fantasma.
    El estado intermedio ``borrador`` desaparece del flujo — las entidades y
    relaciones existentes en ``borrador`` pasan a ``canonico``. El resto de
    estados (fantasma, archivado, hipotesis, ...) queda intacto y no se pierde
    ningún dato.
    """
    migrated = dict(data)
    for collection in ("entities", "relations"):
        items = migrated.get(collection)
        if not isinstance(items, list):
            continue
        upgraded = []
        for item in items:
            if isinstance(item, dict) and item.get("canon_state") == "borrador":
                item = dict(item)
                item["canon_state"] = "canonico"
            upgraded.append(item)
        migrated[collection] = upgraded
    migrated["schema_version"] = 34
    return migrated


def _v35_int(value: Any, default: int) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _v35_has_real_eras(eras: Any) -> bool:
    """Una sola era ABIERTA ("Presente") no cuenta como real (contrato chrono_canvas)."""
    if not isinstance(eras, list) or not eras:
        return False
    if len(eras) > 1:
        return True
    first = eras[0]
    return isinstance(first, dict) and first.get("end_year") is not None


def _v35_durations(metadata: dict[str, Any]) -> list[tuple[str, int]]:
    """Deriva ``[(nombre, duración)]`` ordenado desde era_lengths/past_eras/periods."""
    era_lengths = metadata.get("era_lengths")
    order = metadata.get("past_eras") or metadata.get("eras") or metadata.get("periods")
    names = [str(n).strip() for n in order if str(n).strip()] if isinstance(order, list) else []
    if isinstance(era_lengths, dict) and era_lengths:
        if not names:
            names = [str(n).strip() for n in era_lengths.keys() if str(n).strip()]
        return [(name, max(1, _v35_int(era_lengths.get(name, 1), 1))) for name in names]
    if names:
        return [(name, 1) for name in names]
    return []


def _v35_chain_eras(durations: list[tuple[str, int]]) -> list[dict[str, Any]]:
    """Encadena eras: start = suma previa; todas cerradas salvo la última (abierta)."""
    from packages.domain.era import Era

    eras: list[dict[str, Any]] = []
    cursor = 0
    for index, (name, duration) in enumerate(durations):
        is_last = index == len(durations) - 1
        start = cursor
        end = None if is_last else start + duration - 1
        eras.append(Era(name=name, start_year=start, end_year=end, order=index).to_dict())
        cursor += duration
    return eras


def _v35_present_abs(
    chronology: dict[str, Any],
    metadata: dict[str, Any],
    durations: list[tuple[str, int]],
) -> int:
    """Deriva el present_year absoluto priorizando current_date (era + año regnal)."""
    current_date = metadata.get("current_date")
    if isinstance(current_date, dict):
        era_name = str(current_date.get("era", "")).strip()
        year_within = _v35_int(current_date.get("year"), 1)
        cursor = 0
        for name, duration in durations:
            if name == era_name:
                return cursor + max(0, year_within - 1)
            cursor += duration
    existing = chronology.get("present_year")
    if isinstance(existing, int) and not isinstance(existing, bool) and existing > 0:
        return existing
    current_year = metadata.get("current_year")
    if isinstance(current_year, int) and not isinstance(current_year, bool):
        return current_year
    return existing if isinstance(existing, int) and not isinstance(existing, bool) else 0


def _apply_migration_v34_to_v35(data: dict[str, Any]) -> dict[str, Any]:
    """v34 → v35 (BETA2-CAL): calendario unificado por eras encadenadas.

    - Reconstruye eras CANÓNICAS encadenadas desde ``metadata.era_lengths``/periods cuando
      solo existe la era trivial "Presente" (o ninguna), fijando ``present_year`` coherente.
    - Normaliza la config de meses/semana bajo ``metadata['calendar']`` con ancla por defecto.
    - Deja ``mode`` DERIVADO (full_calendar si hay meses+semana; si no vague_periods/none).

    Aditiva y sin pérdida: los proyectos con eras cerradas reales se conservan intactos.
    """
    from packages.domain.calendar_math import CalendarConfig

    migrated = dict(data)
    chronology = migrated.get("project_chronology")
    if not isinstance(chronology, dict):
        migrated["schema_version"] = 35
        return migrated
    chronology = dict(chronology)
    metadata = dict(chronology.get("metadata") or {})

    mode = str(metadata.get("mode") or metadata.get("calendar_kind") or "").strip()
    mode = {
        "relative": "vague_periods",
        "narrative": "vague_periods",
        "custom_calendar": "full_calendar",
    }.get(mode, mode)

    # 1. Normaliza meses/semana/ancla y deriva el modo.
    cal = CalendarConfig.from_metadata(metadata)
    metadata["calendar"] = cal.to_metadata()
    metadata["week_anchor"] = cal.week_anchor
    metadata["calendar_configured"] = True
    durations = _v35_durations(metadata)
    if cal.supports_exact_dates():
        new_mode = "full_calendar"
    elif mode in {"none", ""} and not durations:
        new_mode = "none"
    else:
        new_mode = "vague_periods"
    metadata["mode"] = new_mode
    metadata["calendar_kind"] = new_mode

    # 2. Reconstruye eras canónicas si solo existe la trivial.
    if durations and not _v35_has_real_eras(chronology.get("eras")):
        chronology["eras"] = _v35_chain_eras(durations)
        chronology["present_year"] = _v35_present_abs(chronology, metadata, durations)

    chronology["metadata"] = metadata
    migrated["project_chronology"] = chronology
    migrated["schema_version"] = 35
    return migrated


def _apply_migration_v35_to_v36(data: dict[str, Any]) -> dict[str, Any]:
    """v35 → v36 (BETA2-SUB-01): subhitos — contención temporal entre hitos.

    Aditiva y sin pérdida: asegura la clave ``parent_milestone_id`` (None) en
    cada hito causal, para que los proyectos antiguos carguen con hitos de
    primer nivel (ningún subhito preexistente).
    """
    migrated = dict(data)
    hitos = migrated.get("causal_milestones")
    if isinstance(hitos, list):
        migrated["causal_milestones"] = [
            {**h, "parent_milestone_id": h.get("parent_milestone_id")}
            if isinstance(h, dict)
            else h
            for h in hitos
        ]
    migrated["schema_version"] = 36
    return migrated


def _apply_migration_v36_to_v37(data: dict[str, Any]) -> dict[str, Any]:
    """v36 → v37 (BETA2-MEM-02): memoria narrativa viva.

    Aditiva y sin pérdida: asegura la colección ``narrative_memories`` (lista
    vacía). **No autogenera memoria** para proyectos existentes — quedan en
    estado *Sin memoria* hasta que el usuario Regue o regenere desde
    Configuración (contrato ``memoria_narrativa.md`` §20).
    """
    migrated = dict(data)
    if not isinstance(migrated.get("narrative_memories"), list):
        migrated["narrative_memories"] = []
    migrated["schema_version"] = 37
    return migrated


def _apply_migration_v37_to_v38(data: dict[str, Any]) -> dict[str, Any]:
    """v37 → v38 (BETA2-MEM-03): @menciones estructuradas.

    Aditiva y sin pérdida: asegura la colección ``structured_references`` (lista
    vacía). Las referencias se derivan de las @menciones al guardar; no se
    generan en migración para proyectos existentes.
    """
    migrated = dict(data)
    if not isinstance(migrated.get("structured_references"), list):
        migrated["structured_references"] = []
    migrated["schema_version"] = 38
    return migrated


def _apply_migration_v38_to_v39(data: dict[str, Any]) -> dict[str, Any]:
    """v38 → v39 (BETA2-WIKI-02): la Memoria pasa a ser página de wiki.

    Aditiva y sin pérdida: ``NarrativeMemory`` gana ``cuerpo``/``wikilinks``/``tags``.
    Los nuevos campos son tolerantes en ``NarrativeMemory.from_dict`` (defaultean a
    cadena/lista vacía), así que basta con bumpear la versión y asegurar la colección.
    **No autogenera** cuerpos para proyectos existentes: las páginas quedan con
    ``cuerpo=""`` hasta el próximo Regar (contrato ``wiki_memoria.md`` §10).
    """
    migrated = dict(data)
    if not isinstance(migrated.get("narrative_memories"), list):
        migrated["narrative_memories"] = []
    migrated["schema_version"] = 39
    return migrated


#: BETA-AUDIT-11 — tope de diagnósticos por entidad que aplica la migración v39→v40.
#: Se duplica aquí a propósito en vez de importar `packages.application`: `persistence`
#: solo puede depender de `domain` (regla de capas, tests/architecture).
_MAX_DIAGNOSTICS_PER_ENTITY_V40 = 5


def _apply_migration_v39_to_v40(data: dict[str, Any]) -> dict[str, Any]:
    """v39 → v40 (BETA-AUDIT-11): poda de ``watering_diagnostics``.

    Los diagnósticos de riego crecían sin techo y nadie los limpiaba: en el proyecto de
    ejemplo eran el **41 % del fichero** frente a un 16 % de canon real, y había 15
    ``entity_id`` distintos con diagnóstico para 10 entidades vivas (borrar una entidad
    no se llevaba los suyos).

    La migración hace dos cosas, ambas sobre datos DERIVADOS —nunca sobre canon—:
    retira los huérfanos y deja los N más recientes por entidad. El estado del jardín
    solo mira el último éxito y el último fallo, así que la poda no cambia nada visible.
    """
    migrated = dict(data)
    diagnosticos = migrated.get("watering_diagnostics")
    if not isinstance(diagnosticos, list):
        migrated["watering_diagnostics"] = []
        migrated["schema_version"] = 40
        return migrated

    vivos = {
        e.get("id")
        for e in (migrated.get("entities") or [])
        if isinstance(e, dict)
    }
    por_entidad: dict[str, list[dict]] = {}
    for entrada in diagnosticos:
        if not isinstance(entrada, dict):
            continue
        eid = entrada.get("entity_id")
        if eid not in vivos:  # huérfano: su entidad ya no existe
            continue
        por_entidad.setdefault(eid, []).append(entrada)

    conservados: list[dict] = []
    for entradas in por_entidad.values():
        entradas.sort(key=lambda d: str(d.get("created_at") or ""))
        conservados.extend(entradas[-_MAX_DIAGNOSTICS_PER_ENTITY_V40:])

    # Se respeta el orden original del fichero para que el diff sea legible.
    guardados = {id(d) for d in conservados}
    migrated["watering_diagnostics"] = [
        d for d in diagnosticos if isinstance(d, dict) and id(d) in guardados
    ]
    migrated["schema_version"] = 40
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

    # Config sections must be dicts when present (PA04: solo creative_config + chronology)
    config_sections = (
        "creative_config",
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
        "domains", "world_layers",
        # import_baskets: colección retirada (subsistema de importación eliminado);
        # se tolera en proyectos antiguos y se descarta al cargar.
        "import_baskets",
        "campaigns", "player_character_profiles", "campaign_clocks",
        "secrets", "clues",
        "factions", "fronts",
        "sessions", "saved_graph_views", "causal_milestones",
        "chronology_walk_sessions", "chronology_walk_reports",
        # Memoria narrativa viva (BETA2-MEM)
        "narrative_memories",
        # @menciones estructuradas (BETA2-MEM-03)
        "structured_references",
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


# --- Causal milestone containment validation (BETA2-SUB-01) ---


def _validate_causal_milestones(hitos):
    """Valida la contención temporal de subhitos (``parent_milestone_id``).

    Reglas: el padre debe existir, sin auto-referencia, sin ciclos y de UN
    solo nivel (el padre de un subhito no puede ser a su vez subhito).
    Devuelve lista de mensajes de error (vacía = OK).
    """
    errors = []
    if not isinstance(hitos, list):
        return [f"causal_milestones must be a list, got {type(hitos).__name__}"]

    parent_of = {}
    for h in hitos:
        if isinstance(h, dict) and h.get("id"):
            pid = h.get("parent_milestone_id")
            parent_of[h["id"]] = pid if isinstance(pid, str) and pid.strip() else None

    for i, h in enumerate(hitos):
        if not isinstance(h, dict):
            continue
        hid = h.get("id")
        pid = parent_of.get(hid)
        if pid is None:
            continue
        if pid == hid:
            errors.append(f"causal_milestones[{i}] parent_milestone_id se refiere a sí mismo")
            continue
        if pid not in parent_of:
            errors.append(f"causal_milestones[{i}] parent_milestone_id '{pid}' no existe")
            continue
        # 1 nivel: el marco no puede ser a su vez subhito.
        if parent_of.get(pid) is not None:
            errors.append(
                f"causal_milestones[{i}] anidamiento de >1 nivel: el marco '{pid}' ya es subhito"
            )

    # Detección de ciclos (defensiva, aunque la regla de 1 nivel ya lo impide).
    for hid in parent_of:
        visited = set()
        current = hid
        while parent_of.get(current) is not None:
            current = parent_of[current]
            if current in visited:
                errors.append(f"causal_milestones ciclo de contención en '{current}'")
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
