"""
Advanced project configuration — §10.4.

Provides ``AdvancedProjectConfig``, a unified dataclass for the 13 extended
project settings: genre, tone, realism, naming conventions, languages,
calendar, measurement units, visibility rules, creative restrictions,
and future AI preferences.

Pure domain model — stdlib only.  The existing ``project_config.py``
dataclasses (``GenreConfig``, ``ToneConfig``, etc.) are preserved for
backward compatibility; this dataclass is the canonical source for §10.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Whitelist of supported config paths (§B10-T03)
CONFIG_PATH_WHITELIST: set[str] = {
    "primary_genre",
    "subgenres",
    "global_tone",
    "secondary_tones",
    "realism_level",
    "contradiction_tolerance",
    "naming_conventions",
    "internal_languages",
    "internal_calendar",
    "measurement_units",
    "visibility_rules",
    "creative_restrictions",
    "future_ai_preferences",
}

# Paths whose value must be list[str]
CONFIG_ARRAY_PATHS: set[str] = {
    "subgenres",
    "secondary_tones",
    "internal_languages",
    "creative_restrictions",
    "future_ai_preferences",
}


@dataclass
class AdvancedProjectConfig:
    """Extended project configuration (§10.4).

    Unifies the 13 configurable settings of the project contract.
    All fields have sensible defaults for a new empty project.
    """

    # ── Genre (§10.4 #1, #2) ──
    primary_genre: str = ""
    subgenres: list[str] = field(default_factory=list)

    # ── Tone (§10.4 #3, #4) ──
    global_tone: str = "neutral"
    secondary_tones: list[str] = field(default_factory=list)

    # ── Realism (§10.4 #5, #6) ──
    realism_level: str = "medium"
    contradiction_tolerance: str = "media"

    # ── Conventions (§10.4 #7–#10) ──
    naming_conventions: str = ""
    internal_languages: list[str] = field(default_factory=list)
    internal_calendar: str = ""
    measurement_units: str = ""

    # ── Rules (§10.4 #11, #12) ──
    visibility_rules: str = ""
    creative_restrictions: list[str] = field(default_factory=list)

    # ── Future IA (§10.4 #13) ──
    future_ai_preferences: list[str] = field(default_factory=list)

    # ── Extensible metadata ──
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        return {
            "primary_genre": self.primary_genre,
            "subgenres": list(self.subgenres),
            "global_tone": self.global_tone,
            "secondary_tones": list(self.secondary_tones),
            "realism_level": self.realism_level,
            "contradiction_tolerance": self.contradiction_tolerance,
            "naming_conventions": self.naming_conventions,
            "internal_languages": list(self.internal_languages),
            "internal_calendar": self.internal_calendar,
            "measurement_units": self.measurement_units,
            "visibility_rules": self.visibility_rules,
            "creative_restrictions": list(self.creative_restrictions),
            "future_ai_preferences": list(self.future_ai_preferences),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdvancedProjectConfig:
        """Deserialize from a dictionary, tolerating missing keys."""
        return cls(
            primary_genre=data.get("primary_genre", ""),
            subgenres=_safe_list(data.get("subgenres")),
            global_tone=data.get("global_tone", "neutral"),
            secondary_tones=_safe_list(data.get("secondary_tones")),
            realism_level=data.get("realism_level", "medium"),
            contradiction_tolerance=data.get("contradiction_tolerance", "media"),
            naming_conventions=data.get("naming_conventions", ""),
            internal_languages=_safe_list(data.get("internal_languages")),
            internal_calendar=data.get("internal_calendar", ""),
            measurement_units=data.get("measurement_units", ""),
            visibility_rules=data.get("visibility_rules", ""),
            creative_restrictions=_safe_list(data.get("creative_restrictions")),
            future_ai_preferences=_safe_list(data.get("future_ai_preferences")),
            metadata=dict(data.get("metadata", {})),
        )


def _safe_list(value: Any) -> list[str]:
    """Coerce *value* to a list of strings, returning [] for anything else."""
    if isinstance(value, list):
        return [str(v) for v in value]
    return []
