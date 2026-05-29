"""
Tests for B10-T01 domain models: NarrativeDomain, WorldLayer,
AdvancedProjectConfig, and extensions to NarrativeEntity,
NarrativeRelation, and Project.
"""

from __future__ import annotations

import pytest

from packages.domain.narrative_domain import NarrativeDomain, NARRATIVE_DOMAIN_ORDER
from packages.domain.world_layer import WorldLayer, default_world_layers
from packages.domain.advanced_config import (
    AdvancedProjectConfig,
    CONFIG_PATH_WHITELIST,
    CONFIG_ARRAY_PATHS,
)
from packages.domain.entity import NarrativeEntity, EntityType
from packages.domain.relation import NarrativeRelation
from packages.domain.project import Project


# ═══════════════════════════════════════════════════════════════════════
# NarrativeDomain
# ═══════════════════════════════════════════════════════════════════════


class TestNarrativeDomain:
    def test_enum_has_five_values(self) -> None:
        values = list(NarrativeDomain)
        assert len(values) == 5

    def test_enum_values_are_strings(self) -> None:
        for member in NarrativeDomain:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()

    def test_all_expected_values_present(self) -> None:
        expected = {"mundo", "historia", "campaña", "compartido", "sin_asignar"}
        actual = {m.value for m in NarrativeDomain}
        assert actual == expected

    def test_str_enum_parsing(self) -> None:
        assert NarrativeDomain("mundo") == NarrativeDomain.MUNDO
        assert NarrativeDomain("historia") == NarrativeDomain.HISTORIA

    def test_domain_order(self) -> None:
        assert len(NARRATIVE_DOMAIN_ORDER) == 5
        assert NARRATIVE_DOMAIN_ORDER[0] == "mundo"
        assert NARRATIVE_DOMAIN_ORDER[-1] == "sin_asignar"


# ═══════════════════════════════════════════════════════════════════════
# WorldLayer
# ═══════════════════════════════════════════════════════════════════════


class TestWorldLayer:
    def test_create_minimal(self) -> None:
        layer = WorldLayer(id="test", name="Test Layer")
        assert layer.id == "test"
        assert layer.name == "Test Layer"
        assert layer.description == ""
        assert layer.order == 0
        assert layer.is_visible is True
        assert layer.is_default is False
        assert layer.metadata == {}

    def test_to_dict_roundtrip(self) -> None:
        layer = WorldLayer(
            id="layer_geo",
            name="Geografía",
            description="Relieve y clima",
            order=5,
            is_visible=False,
            is_default=True,
            metadata={"color": "green"},
        )
        d = layer.to_dict()
        assert d["id"] == "layer_geo"
        assert d["name"] == "Geografía"
        assert d["order"] == 5
        assert d["is_visible"] is False
        assert d["is_default"] is True
        assert d["metadata"] == {"color": "green"}

        restored = WorldLayer.from_dict(d)
        assert restored.id == layer.id
        assert restored.name == layer.name
        assert restored.order == layer.order
        assert restored.is_visible == layer.is_visible
        assert restored.is_default == layer.is_default

    def test_from_dict_partial(self) -> None:
        layer = WorldLayer.from_dict({"id": "x", "name": "X"})
        assert layer.id == "x"
        assert layer.name == "X"
        assert layer.is_visible is True  # default
        assert layer.is_default is False  # default

    def test_from_dict_empty(self) -> None:
        layer = WorldLayer.from_dict({})
        assert layer.id == ""
        assert layer.name == ""
        assert layer.is_visible is True


class TestDefaultWorldLayers:
    def test_returns_16_layers(self) -> None:
        layers = default_world_layers()
        assert len(layers) == 16

    def test_all_are_default(self) -> None:
        for layer in default_world_layers():
            assert layer.is_default is True

    def test_all_have_semantic_ids(self) -> None:
        for layer in default_world_layers():
            assert layer.id.startswith("layer_")
            assert len(layer.id) > 6

    def test_ids_are_unique(self) -> None:
        ids = [layer.id for layer in default_world_layers()]
        assert len(ids) == len(set(ids))

    def test_orders_are_sequential(self) -> None:
        orders = [layer.order for layer in default_world_layers()]
        assert orders == list(range(1, 17))

    def test_all_have_names(self) -> None:
        for layer in default_world_layers():
            assert layer.name
            assert len(layer.name) > 2


# ═══════════════════════════════════════════════════════════════════════
# AdvancedProjectConfig
# ═══════════════════════════════════════════════════════════════════════


class TestAdvancedProjectConfig:
    def test_defaults(self) -> None:
        cfg = AdvancedProjectConfig()
        assert cfg.primary_genre == ""
        assert cfg.subgenres == []
        assert cfg.global_tone == "neutral"
        assert cfg.secondary_tones == []
        assert cfg.realism_level == "medium"
        assert cfg.contradiction_tolerance == "media"
        assert cfg.naming_conventions == ""
        assert cfg.internal_languages == []
        assert cfg.internal_calendar == ""
        assert cfg.measurement_units == ""
        assert cfg.visibility_rules == ""
        assert cfg.creative_restrictions == []
        assert cfg.future_ai_preferences == []

    def test_to_dict_roundtrip(self) -> None:
        cfg = AdvancedProjectConfig(
            primary_genre="fantasía",
            subgenres=["épica", "oscura"],
            global_tone="serio",
            secondary_tones=["irónico"],
            realism_level="alto",
            contradiction_tolerance="baja",
            naming_conventions="nombres élficos",
            internal_languages=["quenya", "sindarin"],
            internal_calendar="calendario imperial",
            measurement_units="leguas",
            visibility_rules="secretos solo DM",
            creative_restrictions=["sin pistolas"],
            future_ai_preferences=["evitar clichés"],
            metadata={"version": "1"},
        )
        d = cfg.to_dict()
        assert d["primary_genre"] == "fantasía"
        assert d["subgenres"] == ["épica", "oscura"]
        assert d["internal_languages"] == ["quenya", "sindarin"]
        assert d["metadata"] == {"version": "1"}

        restored = AdvancedProjectConfig.from_dict(d)
        assert restored.primary_genre == cfg.primary_genre
        assert restored.subgenres == cfg.subgenres
        assert restored.global_tone == cfg.global_tone
        assert restored.internal_languages == cfg.internal_languages

    def test_from_dict_partial(self) -> None:
        cfg = AdvancedProjectConfig.from_dict({"primary_genre": "ciencia ficción"})
        assert cfg.primary_genre == "ciencia ficción"
        assert cfg.global_tone == "neutral"  # default

    def test_from_dict_empty(self) -> None:
        cfg = AdvancedProjectConfig.from_dict({})
        assert cfg.primary_genre == ""
        assert cfg.subgenres == []

    def test_from_dict_coerces_non_list(self) -> None:
        cfg = AdvancedProjectConfig.from_dict({"subgenres": "not_a_list"})
        assert cfg.subgenres == []

    def test_whitelist_has_expected_paths(self) -> None:
        assert len(CONFIG_PATH_WHITELIST) == 13
        assert "primary_genre" in CONFIG_PATH_WHITELIST
        assert "future_ai_preferences" in CONFIG_PATH_WHITELIST

    def test_array_paths_match_contract(self) -> None:
        assert CONFIG_ARRAY_PATHS == {
            "subgenres", "secondary_tones", "internal_languages",
            "creative_restrictions", "future_ai_preferences",
        }


# ═══════════════════════════════════════════════════════════════════════
# NarrativeEntity extensions
# ═══════════════════════════════════════════════════════════════════════


class TestNarrativeEntityExtensions:
    def test_default_domain_ids_is_empty(self) -> None:
        e = NarrativeEntity(name="X", entity_type=EntityType.PERSONAJE)
        assert e.domain_ids == []

    def test_default_layer_ids_is_empty(self) -> None:
        e = NarrativeEntity(name="X", entity_type=EntityType.PERSONAJE)
        assert e.layer_ids == []

    def test_can_assign_domain_ids(self) -> None:
        e = NarrativeEntity(name="X", entity_type=EntityType.PERSONAJE)
        e.domain_ids = ["mundo", "historia"]
        assert len(e.domain_ids) == 2
        assert "mundo" in e.domain_ids

    def test_can_assign_layer_ids(self) -> None:
        e = NarrativeEntity(name="X", entity_type=EntityType.PERSONAJE)
        e.layer_ids = ["layer_geografia", "layer_historia"]
        assert len(e.layer_ids) == 2
        assert "layer_geografia" in e.layer_ids

    def test_domain_ids_serialization_roundtrip(self) -> None:
        e = NarrativeEntity(
            name="X", entity_type=EntityType.PERSONAJE,
            domain_ids=["mundo"],
        )
        d = e.to_dict()
        assert d["domain_ids"] == ["mundo"]
        e2 = NarrativeEntity.from_dict(d)
        assert e2.domain_ids == ["mundo"]

    def test_layer_ids_serialization_roundtrip(self) -> None:
        e = NarrativeEntity(
            name="X", entity_type=EntityType.PERSONAJE,
            layer_ids=["layer_geografia"],
        )
        d = e.to_dict()
        assert d["layer_ids"] == ["layer_geografia"]
        e2 = NarrativeEntity.from_dict(d)
        assert e2.layer_ids == ["layer_geografia"]

    def test_legacy_domain_preserved(self) -> None:
        """domain: str legacy field must not be affected by domain_ids."""
        e = NarrativeEntity(
            name="X", entity_type=EntityType.PERSONAJE,
            domain="tierra_media",
            domain_ids=["mundo"],
        )
        d = e.to_dict()
        assert d["domain"] == "tierra_media"
        assert d["domain_ids"] == ["mundo"]
        e2 = NarrativeEntity.from_dict(d)
        assert e2.domain == "tierra_media"
        assert e2.domain_ids == ["mundo"]

    def test_legacy_layers_preserved(self) -> None:
        """layers: list[str] legacy field must not be affected by layer_ids."""
        e = NarrativeEntity(
            name="X", entity_type=EntityType.PERSONAJE,
            layers=["geografia", "politica"],
            layer_ids=["layer_geografia"],
        )
        d = e.to_dict()
        assert d["layers"] == ["geografia", "politica"]
        assert d["layer_ids"] == ["layer_geografia"]
        e2 = NarrativeEntity.from_dict(d)
        assert e2.layers == ["geografia", "politica"]
        assert e2.layer_ids == ["layer_geografia"]

    def test_from_dict_without_domain_ids_gets_empty(self) -> None:
        d = NarrativeEntity(name="X", entity_type=EntityType.NOTA).to_dict()
        del d["domain_ids"]
        del d["layer_ids"]
        e = NarrativeEntity.from_dict(d)
        assert e.domain_ids == []
        assert e.layer_ids == []


# ═══════════════════════════════════════════════════════════════════════
# NarrativeRelation extensions
# ═══════════════════════════════════════════════════════════════════════


class TestNarrativeRelationExtensions:
    def test_default_layer_ids_is_empty(self) -> None:
        r = NarrativeRelation(source_id="a", target_id="b")
        assert r.layer_ids == []

    def test_layer_ids_serialization_roundtrip(self) -> None:
        r = NarrativeRelation(
            source_id="a", target_id="b",
            layer_ids=["layer_geografia", "layer_historia"],
        )
        d = r.to_dict()
        assert d["layer_ids"] == ["layer_geografia", "layer_historia"]
        r2 = NarrativeRelation.from_dict(d)
        assert r2.layer_ids == ["layer_geografia", "layer_historia"]

    def test_from_dict_without_layer_ids_gets_empty(self) -> None:
        d = NarrativeRelation(source_id="a", target_id="b").to_dict()
        del d["layer_ids"]
        r = NarrativeRelation.from_dict(d)
        assert r.layer_ids == []


# ═══════════════════════════════════════════════════════════════════════
# Project extensions
# ═══════════════════════════════════════════════════════════════════════


class TestProjectExtensions:
    def test_default_domains_are_five(self) -> None:
        p = Project()
        assert len(p.domains) == 5
        assert "mundo" in p.domains
        assert "historia" in p.domains
        assert "campaña" in p.domains
        assert "compartido" in p.domains
        assert "sin_asignar" in p.domains

    def test_domains_are_strings_not_enums(self) -> None:
        p = Project()
        for d in p.domains:
            assert isinstance(d, str)

    def test_default_world_layers_are_sixteen(self) -> None:
        p = Project()
        assert len(p.world_layers) == 16
        for wl in p.world_layers:
            assert isinstance(wl, WorldLayer)
            assert wl.is_default is True

    def test_advanced_config_is_present(self) -> None:
        p = Project()
        assert isinstance(p.advanced_config, AdvancedProjectConfig)
        assert p.advanced_config.primary_genre == ""

    def test_project_to_dict_includes_new_fields(self) -> None:
        p = Project()
        d = p.to_dict()
        assert "domains" in d
        assert "world_layers" in d
        assert "advanced_config" in d
        assert len(d["domains"]) == 5
        assert len(d["world_layers"]) == 16

    def test_project_roundtrip_preserves_domains(self) -> None:
        p = Project()
        p.domains = ["mundo", "campaña"]
        d = p.to_dict()
        p2 = Project.from_dict(d)
        assert p2.domains == ["mundo", "campaña"]

    def test_project_roundtrip_preserves_world_layers(self) -> None:
        p = Project()
        p.world_layers = [
            WorldLayer(id="custom_1", name="Custom", is_default=False)
        ]
        d = p.to_dict()
        p2 = Project.from_dict(d)
        assert len(p2.world_layers) == 1
        assert p2.world_layers[0].id == "custom_1"
        assert p2.world_layers[0].is_default is False

    def test_project_roundtrip_preserves_advanced_config(self) -> None:
        p = Project()
        p.advanced_config.primary_genre = "fantasía oscura"
        d = p.to_dict()
        p2 = Project.from_dict(d)
        assert p2.advanced_config.primary_genre == "fantasía oscura"

    def test_from_dict_without_new_fields_uses_defaults(self) -> None:
        """Old projects without domains/world_layers/advanced_config
        should load with defaults."""
        p = Project()
        d = p.to_dict()
        del d["domains"]
        del d["world_layers"]
        del d["advanced_config"]
        p2 = Project.from_dict(d)
        assert p2.domains == ["mundo", "historia", "campaña", "compartido", "sin_asignar"]
        assert len(p2.world_layers) == 16
        assert isinstance(p2.advanced_config, AdvancedProjectConfig)
