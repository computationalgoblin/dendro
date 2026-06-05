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

    Resolution order: Project > Anillo > Rama > Hoja
    Each level can inherit or override specific fields.

    Returns the merged config dict.
    """
    from packages.domain.creative_presets import apply_preset_to_project

    # Start with project-level config
    base = project.creative_config.to_dict()

    # Check for anillo (world layer) overrides
    if hasattr(entity, "layer_ids") and entity.layer_ids:
        for layer_id in entity.layer_ids:
            for layer in project.world_layers:
                if layer.id == layer_id:
                    layer_overrides = layer.custom_data.get("branch_config", {}).get("overrides", {})
                    _deep_merge(base, layer_overrides)

    # Check for rama (entity with entity_type CONTENEDOR) overrides
    if hasattr(entity, "entity_type") and entity.entity_type.value == "CONTENEDOR":
        branch_cfg = get_branch_config(entity)
        _deep_merge(base, branch_cfg.get("overrides", {}))

    # Check if entity is a hoja inside a rama
    if hasattr(entity, "custom_metadata"):
        branch_cfg = entity.custom_metadata.get("branch_config", {})
        if branch_cfg:
            _deep_merge(base, branch_cfg.get("overrides", {}))

    return base


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Merge overrides into base dict in-place. Lists are replaced, not extended."""
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
