"""Creative context helpers for B40.

Application-layer utilities that convert project creative configuration into
small, provider-safe dictionaries for AI prompts. They never mutate canon or
persistence and they avoid exposing technical JSON/metadata to normal UI.
"""
from __future__ import annotations

from typing import Any, Iterable

from packages.domain.branch_config import get_branch_config, resolve_effective_config


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _compact_dict(data: dict[str, Any], allowed: Iterable[str]) -> dict[str, Any]:
    """Keep allowed keys whose values are not empty."""
    result: dict[str, Any] = {}
    for key in allowed:
        value = data.get(key)
        if value in (None, "", [], {}):
            continue
        result[key] = value
    return result


def project_creative_brief(project) -> dict[str, Any]:
    """Return the B40 creative profile used by IA.

    This is intentionally compact but includes the fields that change model
    behaviour: identity, genre/tone, creative direction, canon, negative space,
    taste memory and IA preferences.
    """
    if project is None:
        return {}
    cc = getattr(project, "creative_config", None)
    ai = getattr(project, "ai", None)
    genre = getattr(project, "genre", None)
    tone = getattr(project, "tone", None)
    realism = getattr(project, "realism", None)
    cc_to_dict = getattr(cc, "to_dict", None)
    ai_to_dict = getattr(ai, "to_dict", None)
    cc_data_raw = cc_to_dict() if callable(cc_to_dict) else {}
    ai_data_raw = ai_to_dict() if callable(ai_to_dict) else {}
    cc_data = cc_data_raw if isinstance(cc_data_raw, dict) else {}
    ai_data = ai_data_raw if isinstance(ai_data_raw, dict) else {}
    if not ai_data and ai is not None:
        ai_data = {
            "enabled": getattr(ai, "enabled", False),
            "model_preference": getattr(ai, "model_preference", "default"),
            "creativity_level": getattr(ai, "creativity_level", "medium"),
            "default_role": getattr(ai, "default_role", "coauthor"),
            "change_aggressiveness": getattr(ai, "change_aggressiveness", 5),
            "default_num_options": getattr(ai, "default_num_options", 3),
            "output_mode": getattr(ai, "output_mode", "contrastive_options"),
            "uncertainty_policy": getattr(ai, "uncertainty_policy", "conservative_proposal"),
            "default_strategy": getattr(ai, "default_strategy", "profundizar"),
            "context_depth": getattr(ai, "context_depth", "balanced"),
        }

    return {
        "project_name": getattr(project, "name", ""),
        "primary_language": getattr(project, "primary_language", "es"),
        "project_type": getattr(project, "project_type", ""),
        "worldbuilding_active": bool(getattr(project, "worldbuilding_active", False)),
        "identity": _compact_dict(cc_data, [
            "core_premise",
            "short_summary",
            "development_status",
            "format",
            "narrative_style",
            "target_audience",
            "main_themes",
            "creative_rules",
            "presets_applied",
        ]),
        "genre": {
            "primary_genre": getattr(genre, "primary_genre", ""),
            "secondary_genres": _list(getattr(genre, "secondary_genres", [])),
            "subgenres": _list(getattr(genre, "subgenres", [])),
        },
        "tone": {
            "narrative_tone": getattr(tone, "narrative_tone", ""),
            "formality_level": getattr(tone, "formality_level", ""),
            "humor_level": getattr(tone, "humor_level", ""),
            "dark_level": getattr(tone, "dark_level", ""),
        },
        "realism": {
            "realism_level": getattr(realism, "realism_level", ""),
            "fantasy_level": getattr(realism, "fantasy_level", ""),
            "science_level": getattr(realism, "science_level", ""),
            "magic_level": getattr(realism, "magic_level", ""),
        },
        "creative_intent": dict(getattr(cc, "creative_intent", {}) or {}),
        "narrative_engine": dict(getattr(cc, "narrative_engine", {}) or {}),
        "poetics": dict(getattr(cc, "poetics", {}) or {}),
        "canon": dict(getattr(cc, "canon", {}) or {}),
        "negative_space": dict(getattr(cc, "negative_space", {}) or {}),
        "taste_memory": dict(getattr(cc, "taste_memory", {}) or {}),
        "ai_preferences": _compact_dict(ai_data, [
            "enabled",
            "model_preference",
            "creativity_level",
            "default_role",
            "change_aggressiveness",
            "default_num_options",
            "output_mode",
            "uncertainty_policy",
            "default_strategy",
            "context_depth",
        ]),
    }


def selected_branch_creative_context(project, selected_entity_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Return effective creative config summaries for selected ramas.

    Only ramas (EntityType.CONTENEDOR) with local branch config or effective
    inheritance matter here. The output is compact and serializable.
    """
    if project is None:
        return []
    selected = {str(eid) for eid in (selected_entity_ids or []) if eid}
    result: list[dict[str, Any]] = []
    for entity in _list(getattr(project, "entities", [])):
        entity_id = str(getattr(entity, "id", ""))
        if selected and entity_id not in selected:
            continue
        if str(_value(getattr(entity, "entity_type", ""))) != "contenedor":
            continue
        branch_cfg = get_branch_config(entity)
        effective = resolve_effective_config(project, entity)
        result.append({
            "id": entity_id,
            "name": getattr(entity, "name", ""),
            "display_type": "rama",
            "branch_config": branch_cfg,
            "effective_config": _compact_effective_config(effective),
        })
    return result


def selected_entity_creative_context(project, selected_entity_ids: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Return compact effective creative context for selected hojas/ramas."""
    if project is None:
        return []
    selected = {str(eid) for eid in (selected_entity_ids or []) if eid}
    if not selected:
        return []
    result: list[dict[str, Any]] = []
    for entity in _list(getattr(project, "entities", [])):
        entity_id = str(getattr(entity, "id", ""))
        if entity_id not in selected:
            continue
        effective = resolve_effective_config(project, entity)
        result.append({
            "id": entity_id,
            "name": getattr(entity, "name", ""),
            "type": str(_value(getattr(entity, "entity_type", ""))),
            "effective_config": _compact_effective_config(effective),
        })
    return result


def _compact_effective_config(config: dict[str, Any]) -> dict[str, Any]:
    """Keep only behaviour-driving fields from an effective config."""
    if not isinstance(config, dict):
        return {}
    return {
        "identity": _compact_dict(config, [
            "core_premise",
            "short_summary",
            "narrative_style",
            "target_audience",
            "main_themes",
            "creative_rules",
            "presets_applied",
        ]),
        "creative_intent": dict(config.get("creative_intent") or {}),
        "narrative_engine": dict(config.get("narrative_engine") or {}),
        "poetics": dict(config.get("poetics") or {}),
        "canon": dict(config.get("canon") or {}),
        "negative_space": dict(config.get("negative_space") or {}),
        "taste_memory": dict(config.get("taste_memory") or {}),
    }
