"""
Project configuration dataclasses.

Pure domain model — stdlib only. These are the 8 configuration
dataclasses that compose the extended Project model (B02-T01).

All fields have sensible defaults for a new empty project.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# General project configuration
# ---------------------------------------------------------------------------


@dataclass
class GeneralProjectConfig:
    """General project settings.

    Attributes:
        theme: Overall project theme or concept.
        tags: Freeform tags for categorization.
        default_entity_visibility: Default visibility for new entities.
    """

    theme: str = ""
    tags: list[str] = field(default_factory=list)
    default_entity_visibility: str = "visible_usuario"


# ---------------------------------------------------------------------------
# Tone configuration
# ---------------------------------------------------------------------------


@dataclass
class ToneConfig:
    """Narrative tone settings.

    Attributes:
        narrative_tone: Overall narrative voice (e.g. "serious", "humorous", "dark").
        language_formality: Formality level of language.
        humor_level: Amount of humor in the narrative.
        dark_tone_level: Darkness/intensity of themes.
    """

    narrative_tone: str = "neutral"
    language_formality: str = "neutral"
    humor_level: str = "none"
    dark_tone_level: str = "none"


# ---------------------------------------------------------------------------
# Genre configuration
# ---------------------------------------------------------------------------


@dataclass
class GenreConfig:
    """Genre classification.

    Attributes:
        primary_genre: Main genre.
        secondary_genres: Additional genres.
        subgenres: Specific subgenres.
        genre_mix_notes: Freeform notes about genre combination.
    """

    primary_genre: str = ""
    secondary_genres: list[str] = field(default_factory=list)
    subgenres: list[str] = field(default_factory=list)
    genre_mix_notes: str = ""


# ---------------------------------------------------------------------------
# Realism configuration
# ---------------------------------------------------------------------------


@dataclass
class RealismConfig:
    """Realism and world-building parameters.

    Attributes:
        realism_level: How grounded the world is (low/medium/high).
        magic_level: Prevalence of magic or supernatural elements.
        technology_level: Technology level of the setting.
        fantasy_scale: Scale of fantastical elements.
    """

    realism_level: str = "medium"
    magic_level: str = "none"
    technology_level: str = "medium"
    fantasy_scale: str = "medium"


# ---------------------------------------------------------------------------
# AI configuration (placeholder)
# ---------------------------------------------------------------------------


@dataclass
class AIConfig:
    """AI assistance configuration.

    Placeholder — IA is not operational yet (Bloque 7).
    Defaults reflect disabled state.

    Attributes:
        enabled: Whether AI assistance is active.
        model_preference: Preferred model identifier.
        creativity_level: Creativity / temperature setting.
    """

    enabled: bool = False
    model_preference: str = "default"
    creativity_level: str = "medium"


# ---------------------------------------------------------------------------
# Visibility configuration
# ---------------------------------------------------------------------------


@dataclass
class VisibilityConfig:
    """Default visibility rules for entities and relations.

    Attributes:
        default_entity_visibility: Default visibility for new entities.
        default_relation_visibility: Default visibility for new relations.
    """

    default_entity_visibility: str = "visible_usuario"
    default_relation_visibility: str = "visible_usuario"


# ---------------------------------------------------------------------------
# Export configuration
# ---------------------------------------------------------------------------


@dataclass
class ExportConfig:
    """Export preferences.

    Placeholder — export is not yet operational.

    Attributes:
        export_format_preference: Preferred export format.
        include_private_notes: Whether to export private notes.
        watermark_level: Watermark/DRM level for exports.
    """

    export_format_preference: str = "markdown"
    include_private_notes: bool = False
    watermark_level: str = "none"


# ---------------------------------------------------------------------------
# Project metadata (structured)
# ---------------------------------------------------------------------------


@dataclass
class ProjectMetadata:
    """Structured project metadata.

    Complements the flat `metadata` dict on Project with typed fields.
    The flat `metadata: dict[str, str]` field on Project remains for
    backward compatibility and ad-hoc key-value pairs.

    Attributes:
        version: Project version string.
        author: Primary author name.
        tags: Structured tag list.
        custom_fields: Additional extensible fields.
    """

    version: str = "0.1.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    custom_fields: dict[str, str] = field(default_factory=dict)
