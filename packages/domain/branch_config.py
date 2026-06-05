"""
Branch configuration helper (B40).

Manages per-branch overrides stored in entity.custom_metadata["branch_config"].
Does NOT create a parallel model — reads/writes from the existing metadata dict.
"""

from __future__ import annotations

from typing import Any


# Default branch config structure
_DEFAULT_BRANCH_CONFIG: dict[str, Any] = {
    "inherits_from_project": True,
    "local_narrative_function": "",
    "local_motifs": [],
    "local_tone_override": "",
    "local_ai_role": "",
    "local_rules": [],
    "overrides": {},  # dict of dotted-path → value for specific config overrides
}

# Valid narrative functions for branches
NARRATIVE_FUNCTIONS = [
    "revelar",
    "ocultar",
    "decidir",
    "mostrar_coste",
    "contrastar",
    "presagiar",
    "romper_expectativa",
    "confirmar_regla",
    "desviar_atencion",
    "sintetizar_tramas",
    "presentar_personaje",
    "expandir_mundo",
    "intensificar_conflicto",
    "resolver_consecuencia",
]


def get_branch_config(entity) -> dict[str, Any]:
    """Get branch config from an entity's custom_metadata.

    Returns a full config dict with defaults for missing keys.
    """
    raw = entity.custom_metadata.get("branch_config", {})
    cfg = dict(_DEFAULT_BRANCH_CONFIG)
    for k, v in raw.items():
        cfg[k] = v
    return cfg


def set_branch_config(entity, config: dict[str, Any]) -> None:
    """Set branch config on an entity's custom_metadata."""
    entity.custom_metadata["branch_config"] = {
        k: v for k, v in config.items()
        if k in _DEFAULT_BRANCH_CONFIG
    }


def update_branch_override(entity, key: str, value: Any) -> None:
    """Set a single override value in branch config."""
    cfg = get_branch_config(entity)
    cfg["overrides"][key] = value
    cfg["inherits_from_project"] = False
    set_branch_config(entity, cfg)


def clear_branch_override(entity, key: str) -> None:
    """Remove a single override, reverting to project-level config."""
    cfg = get_branch_config(entity)
    cfg["overrides"].pop(key, None)
    if not cfg["overrides"]:
        cfg["inherits_from_project"] = True
    set_branch_config(entity, cfg)


def clear_all_branch_overrides(entity) -> None:
    """Remove all overrides, reverting fully to project-level config."""
    fresh = {
        "inherits_from_project": True,
        "local_narrative_function": "",
        "local_motifs": [],
        "local_tone_override": "",
        "local_ai_role": "",
        "local_rules": [],
        "overrides": {},
    }
    set_branch_config(entity, fresh)


def resolve_effective_config(project, entity) -> dict[str, Any]:
    """Resolve the effective creative config for an entity.

    Resolution order: Project > Anillo > Rama padre > Rama/Hoja local.
    Each level can inherit or override specific fields. Overrides may be nested
    dictionaries or dotted-path keys such as ``poetics.description_density``.

    Returns the merged config dict. Does not mutate project or entity.
    """
    if project is None or entity is None:
        return {}

    # Start with project-level config
    base = project.creative_config.to_dict()

    # Anillo/world-layer overrides. WorldLayer stores extensibility in metadata.
    for layer_id in list(getattr(entity, "layer_ids", []) or []):
        for layer in list(getattr(project, "world_layers", []) or []):
            if getattr(layer, "id", "") != layer_id:
                continue
            metadata = dict(getattr(layer, "metadata", {}) or {})
            layer_cfg = metadata.get("branch_config") or metadata.get("creative_config") or {}
            if isinstance(layer_cfg, dict):
                _deep_merge(base, layer_cfg.get("overrides", layer_cfg))

    # Parent ramas via structural CONTIENE relations.
    for parent in _parent_branches(project, entity):
        branch_cfg = get_branch_config(parent)
        if not branch_cfg.get("inherits_from_project", True) or branch_cfg.get("overrides"):
            _deep_merge(base, branch_cfg.get("overrides", {}))

    # Local rama/hoja overrides.
    if hasattr(entity, "custom_metadata"):
        branch_cfg = get_branch_config(entity)
        if not branch_cfg.get("inherits_from_project", True) or branch_cfg.get("overrides"):
            _deep_merge(base, branch_cfg.get("overrides", {}))

    return base


def _parent_branches(project, entity) -> list[Any]:
    """Return direct/ancestor parent ramas ordered from root-ish to immediate."""
    entity_id = str(getattr(entity, "id", ""))
    if not entity_id:
        return []
    entities = {str(getattr(e, "id", "")): e for e in list(getattr(project, "entities", []) or [])}
    relations = list(getattr(project, "relations", []) or [])
    parents: list[Any] = []
    visited: set[str] = set()
    frontier = [entity_id]
    while frontier:
        current = frontier.pop(0)
        for rel in relations:
            rtype = _enum_value(getattr(rel, "relation_type", ""))
            if rtype != "contiene" or str(getattr(rel, "target_id", "")) != current:
                continue
            parent_id = str(getattr(rel, "source_id", ""))
            if not parent_id or parent_id in visited:
                continue
            visited.add(parent_id)
            parent = entities.get(parent_id)
            if parent is None:
                continue
            if _enum_value(getattr(parent, "entity_type", "")) == "contenedor":
                parents.insert(0, parent)
            frontier.append(parent_id)
    return parents


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Merge overrides into base dict in-place. Lists are replaced, not extended."""
    for k, v in (overrides or {}).items():
        if "." in str(k):
            _set_dotted(base, str(k), v)
        elif isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _set_dotted(base: dict, path: str, value: Any) -> None:
    """Set dotted path inside a nested dict."""
    parts = [p for p in path.split(".") if p]
    if not parts:
        return
    cursor = base
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value
