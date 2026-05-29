"""Tests for the extended Project domain model (B02-T01).

Covers:
- Default creation with all 20 contract fields
- 8 config dataclasses with sensible defaults
- 5 prepared collections (mutable empty lists)
- to_dict / from_dict roundtrip
- Backward compatibility with v1 data
- touch() unchanged behavior
"""

from packages.domain.project import Project
from packages.domain.project_config import (
    AIConfig,
    ExportConfig,
    GeneralProjectConfig,
    GenreConfig,
    ProjectMetadata,
    RealismConfig,
    ToneConfig,
    VisibilityConfig,
)


# ---------------------------------------------------------------------------
# 1. Default creation
# ---------------------------------------------------------------------------


class TestProjectDefaults:
    """Project created with no arguments has sensible defaults."""

    def test_project_has_auto_generated_id(self):
        p = Project()
        assert isinstance(p.id, str)
        assert len(p.id) == 12

    def test_project_has_unique_ids(self):
        p1 = Project()
        p2 = Project()
        assert p1.id != p2.id

    def test_default_name_is_empty(self):
        p = Project()
        assert p.name == ""

    def test_default_description_is_empty(self):
        p = Project()
        assert p.description == ""

    def test_default_primary_language_is_es(self):
        p = Project()
        assert p.primary_language == "es"

    def test_default_secondary_languages_is_empty_list(self):
        p = Project()
        assert p.secondary_languages == []

    def test_default_created_at_is_utc(self):
        p = Project()
        assert str(p.created_at.tzinfo) == "UTC"

    def test_default_updated_at_is_utc(self):
        p = Project()
        assert str(p.updated_at.tzinfo) == "UTC"

    def test_default_metadata_is_empty_dict(self):
        p = Project()
        assert p.metadata == {}


# ---------------------------------------------------------------------------
# 2. Config dataclasses — defaults
# ---------------------------------------------------------------------------


class TestGeneralProjectConfigDefaults:
    def test_default_theme_empty(self):
        assert GeneralProjectConfig().theme == ""

    def test_default_tags_empty(self):
        assert GeneralProjectConfig().tags == []

    def test_default_entity_visibility(self):
        assert GeneralProjectConfig().default_entity_visibility == "visible_usuario"


class TestToneConfigDefaults:
    def test_defaults_are_neutral(self):
        c = ToneConfig()
        assert c.narrative_tone == "neutral"
        assert c.language_formality == "neutral"
        assert c.humor_level == "none"
        assert c.dark_tone_level == "none"


class TestGenreConfigDefaults:
    def test_defaults_are_empty(self):
        c = GenreConfig()
        assert c.primary_genre == ""
        assert c.secondary_genres == []
        assert c.subgenres == []
        assert c.genre_mix_notes == ""


class TestRealismConfigDefaults:
    def test_defaults_are_medium(self):
        c = RealismConfig()
        assert c.realism_level == "medium"
        assert c.magic_level == "none"
        assert c.technology_level == "medium"
        assert c.fantasy_scale == "medium"


class TestAIConfigDefaults:
    def test_ai_disabled_by_default(self):
        c = AIConfig()
        assert c.enabled is False

    def test_ai_default_model(self):
        c = AIConfig()
        assert c.model_preference == "default"
        assert c.creativity_level == "medium"


class TestVisibilityConfigDefaults:
    def test_defaults(self):
        c = VisibilityConfig()
        assert c.default_entity_visibility == "visible_usuario"
        assert c.default_relation_visibility == "visible_usuario"


class TestExportConfigDefaults:
    def test_defaults(self):
        c = ExportConfig()
        assert c.export_format_preference == "markdown"
        assert c.include_private_notes is False
        assert c.watermark_level == "none"


class TestProjectMetadataDefaults:
    def test_defaults(self):
        m = ProjectMetadata()
        assert m.version == "0.1.0"
        assert m.author == ""
        assert m.tags == []
        assert m.custom_fields == {}


# ---------------------------------------------------------------------------
# 3. 8 config dataclasses are attached to Project
# ---------------------------------------------------------------------------


class TestProjectConfigsAttached:
    def test_project_has_all_8_configs(self):
        p = Project()
        assert isinstance(p.general, GeneralProjectConfig)
        assert isinstance(p.tone, ToneConfig)
        assert isinstance(p.genre, GenreConfig)
        assert isinstance(p.realism, RealismConfig)
        assert isinstance(p.ai, AIConfig)
        assert isinstance(p.visibility, VisibilityConfig)
        assert isinstance(p.export, ExportConfig)
        assert isinstance(p.project_metadata, ProjectMetadata)


# ---------------------------------------------------------------------------
# 4. 5 prepared collections
# ---------------------------------------------------------------------------


class TestProjectCollections:
    def test_five_collections_exist(self):
        p = Project()
        assert p.entities == []
        assert p.relations == []
        assert p.sources == []
        assert p.history == []
        assert p.issues == []

    def test_collections_are_mutable_lists(self):
        p = Project()
        p.entities.append({"name": "test"})
        assert len(p.entities) == 1
        assert p.entities[0]["name"] == "test"

        p.relations.append("rel1")
        assert len(p.relations) == 1

        p.sources.append("src1")
        assert len(p.sources) == 1

        p.history.append("hist1")
        assert len(p.history) == 1

        p.issues.append("issue1")
        assert len(p.issues) == 1

    def test_collections_are_independent_instances(self):
        p1 = Project()
        p2 = Project()
        p1.entities.append("e1")
        assert p2.entities == []
        assert p1.entities != p2.entities


# ---------------------------------------------------------------------------
# 5. Custom configuration serialization
# ---------------------------------------------------------------------------


class TestProjectCustomConfig:
    def test_custom_config_to_dict_roundtrip(self):
        p = Project(name="Fantasy World")
        p.description = "A vast fantasy world"
        p.primary_language = "en"
        p.secondary_languages = ["fr", "de"]
        p.general = GeneralProjectConfig(
            theme="Epic fantasy",
            tags=["elves", "dragons"],
        )
        p.tone = ToneConfig(narrative_tone="serious")
        p.genre = GenreConfig(primary_genre="Fantasy")
        p.realism = RealismConfig(realism_level="low", magic_level="high")
        p.ai = AIConfig(enabled=True, model_preference="gpt-4")
        p.visibility = VisibilityConfig(default_entity_visibility="privado")
        p.export = ExportConfig(export_format_preference="pdf")
        p.project_metadata = ProjectMetadata(version="1.0.0", author="Alice")

        d = p.to_dict()
        p2 = Project.from_dict(d)

        assert p2.name == "Fantasy World"
        assert p2.description == "A vast fantasy world"
        assert p2.primary_language == "en"
        assert p2.secondary_languages == ["fr", "de"]
        assert p2.general.theme == "Epic fantasy"
        assert p2.general.tags == ["elves", "dragons"]
        assert p2.tone.narrative_tone == "serious"
        assert p2.genre.primary_genre == "Fantasy"
        assert p2.realism.realism_level == "low"
        assert p2.realism.magic_level == "high"
        assert p2.ai.enabled is True
        assert p2.ai.model_preference == "gpt-4"
        assert p2.visibility.default_entity_visibility == "privado"
        assert p2.export.export_format_preference == "pdf"
        assert p2.project_metadata.version == "1.0.0"
        assert p2.project_metadata.author == "Alice"


# ---------------------------------------------------------------------------
# 6. to_dict produces all expected sections
# ---------------------------------------------------------------------------


class TestToDict:
    def test_to_dict_has_all_20_contract_keys(self):
        p = Project()
        d = p.to_dict()
        expected_keys = {
            "id", "name", "description", "primary_language",
            "secondary_languages", "created_at", "updated_at",
            "metadata", "project_metadata",
            "general", "tone", "genre", "realism", "ai",
            "visibility", "export",
            "entities", "relations", "sources", "history", "issues",
            "candidates",
            "custom_entity_types", "custom_field_definitions", "custom_relation_types",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_serializes_config_sections(self):
        p = Project()
        d = p.to_dict()
        assert isinstance(d["general"], dict)
        assert "theme" in d["general"]
        assert isinstance(d["ai"], dict)
        assert d["ai"]["enabled"] is False

    def test_to_dict_serializes_empty_collections(self):
        p = Project()
        d = p.to_dict()
        assert d["entities"] == []
        assert d["relations"] == []
        assert d["sources"] == []
        assert d["history"] == []
        assert d["issues"] == []

    def test_to_dict_preserves_custom_metadata(self):
        p = Project(metadata={"key": "value"})
        d = p.to_dict()
        assert d["metadata"] == {"key": "value"}

    def test_to_dict_isoformat_timestamps(self):
        p = Project()
        d = p.to_dict()
        assert "T" in d["created_at"]
        assert "T" in d["updated_at"]


# ---------------------------------------------------------------------------
# 7. from_dict reconstructs all fields
# ---------------------------------------------------------------------------


class TestFromDict:
    def test_from_dict_full_roundtrip(self):
        p1 = Project(name="Test", description="Desc")
        p1.general = GeneralProjectConfig(theme="horror")
        d = p1.to_dict()
        p2 = Project.from_dict(d)
        assert p2.id == p1.id
        assert p2.name == p1.name
        assert p2.description == p1.description
        assert p2.general.theme == "horror"

    def test_from_dict_v1_compatibility(self):
        """V1 data (Bloque 1 minimal format) should load with defaults."""
        v1_data = {
            "id": "aaa111bbb222",
            "name": "old_project",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
            "metadata": {"legacy_key": "legacy_val"},
        }
        p = Project.from_dict(v1_data)

        # Core fields preserved
        assert p.id == "aaa111bbb222"
        assert p.name == "old_project"

        # New fields get defaults
        assert p.description == ""
        assert p.primary_language == "es"
        assert p.secondary_languages == []

        # Configs get defaults
        assert p.general.theme == ""
        assert isinstance(p.general, GeneralProjectConfig)
        assert p.ai.enabled is False

        # Collections get empty defaults
        assert p.entities == []
        assert p.relations == []
        assert p.sources == []
        assert p.history == []
        assert p.issues == []

        # Metadata preserved
        assert p.metadata == {"legacy_key": "legacy_val"}


# ---------------------------------------------------------------------------
# 8. touch() unchanged
# ---------------------------------------------------------------------------


class TestTouch:
    def test_touch_updates_updated_at(self):
        import time
        p = Project()
        before = p.updated_at
        time.sleep(0.001)
        p.touch()
        assert p.updated_at > before

    def test_touch_does_not_affect_other_fields(self):
        p = Project(name="DoNotChange", description="Original")
        p.touch()
        assert p.name == "DoNotChange"
        assert p.description == "Original"
        assert len(p.entities) == 0
