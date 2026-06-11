"""Tests for B10-T02: Persistence schema v7 — domains, layers, advanced config.

Covers:
- Schema v7 constants
- Migration v6→v7 (conservative: no inference from legacy fields)
- Validation functions (domains, world_layers, advanced_config, entity_domain_ids)
- Migration chain v1→v7 accumulation test
- ProjectStore v7 roundtrip
- Future version rejection (v9)
"""

import json
from pathlib import Path

from packages.domain.advanced_config import AdvancedProjectConfig
from packages.domain.project import Project
from packages.domain.result import Error, Ok
from packages.domain.world_layer import default_world_layers
from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    MAX_SUPPORTED_VERSION,
    _apply_migration_v6_to_v7,
    validate_advanced_config,
    validate_domains,
    validate_entity_domain_ids,
    validate_project_structure,
    validate_world_layers,
)
from packages.persistence.store import ProjectStore, load_project_data, save_project_data


# ── V6 minimal project fixture ──

def _v6_minimal(**overrides) -> dict:
    """Return a minimal valid v6 project dict."""
    base = {
        "schema_version": 6,
        "id": "proj-001",
        "name": "Test Project",
        "description": "",
        "primary_language": "es",
        "secondary_languages": [],
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "metadata": {},
        "project_metadata": {},
        "general": {},
        "tone": {},
        "genre": {},
        "realism": {},
        "ai": {},
        "visibility": {},
        "export": {},
        "entities": [],
        "relations": [],
        "sources": [],
        "history": [],
        "issues": [],
        "candidates": [],
        "custom_entity_types": [],
        "custom_field_definitions": [],
        "custom_relation_types": [],
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════
# Schema version constants
# ══════════════════════════════════════════════════════════════════

class TestSchemaVersionV7:
    def test_current_schema_is_v9(self):
        assert CURRENT_SCHEMA_VERSION == 20

    def test_max_supported_is_v9(self):
        assert MAX_SUPPORTED_VERSION == 20


# ══════════════════════════════════════════════════════════════════
# Migration v6 → v7
# ══════════════════════════════════════════════════════════════════

class TestMigrationV6ToV7:
    """Conservative migration — adds structure, never infers data."""

    def test_adds_domains_with_5_values(self):
        v6 = _v6_minimal()
        m = _apply_migration_v6_to_v7(v6)
        assert "domains" in m
        assert m["domains"] == [
            "mundo", "historia", "campaña", "compartido", "sin_asignar",
        ]

    def test_adds_world_layers_with_16_capas(self):
        v6 = _v6_minimal()
        m = _apply_migration_v6_to_v7(v6)
        assert "world_layers" in m
        layers = m["world_layers"]
        assert isinstance(layers, list)
        assert len(layers) == 16

        # Verify first and last
        assert layers[0]["id"] == "layer_premisa"
        assert layers[0]["name"] == "Premisa estética y tonal"
        assert layers[0]["is_default"] is True
        assert layers[-1]["id"] == "layer_campaña"
        assert layers[-1]["order"] == 16

        # All IDs are unique
        ids = [wl["id"] for wl in layers]
        assert len(ids) == len(set(ids))

    def test_adds_advanced_config_defaults(self):
        v6 = _v6_minimal()
        m = _apply_migration_v6_to_v7(v6)
        assert "advanced_config" in m
        ac = m["advanced_config"]
        assert ac["primary_genre"] == ""
        assert ac["subgenres"] == []
        assert ac["global_tone"] == "neutral"
        assert ac["secondary_tones"] == []
        assert ac["realism_level"] == "medium"
        assert ac["contradiction_tolerance"] == "media"
        assert ac["naming_conventions"] == ""
        assert ac["internal_languages"] == []
        assert ac["internal_calendar"] == ""
        assert ac["measurement_units"] == ""
        assert ac["visibility_rules"] == ""
        assert ac["creative_restrictions"] == []
        assert ac["future_ai_preferences"] == []

    def test_adds_domain_ids_to_existing_entities(self):
        v6 = _v6_minimal(entities=[
            {"id": "e1", "name": "Entidad 1", "entity_type": "personaje"},
            {"id": "e2", "name": "Entidad 2", "entity_type": "lugar",
             "domain": "fantasia", "layers": ["geografia", "cultura"]},
        ])
        m = _apply_migration_v6_to_v7(v6)
        for e in m["entities"]:
            assert "domain_ids" in e
            assert e["domain_ids"] == []
            assert "layer_ids" in e
            assert e["layer_ids"] == []

    def test_adds_layer_ids_to_existing_relations(self):
        v6 = _v6_minimal(relations=[
            {"id": "r1", "source_id": "e1", "target_id": "e2",
             "relation_type": "pertenece_a"},
        ])
        m = _apply_migration_v6_to_v7(v6)
        for r in m["relations"]:
            assert "layer_ids" in r
            assert r["layer_ids"] == []

    def test_preserves_legacy_domain_field(self):
        v6 = _v6_minimal(entities=[
            {"id": "e1", "name": "Entidad", "entity_type": "lugar",
             "domain": "fantasia"},
        ])
        m = _apply_migration_v6_to_v7(v6)
        assert m["entities"][0]["domain"] == "fantasia"

    def test_preserves_legacy_layers_field(self):
        v6 = _v6_minimal(entities=[
            {"id": "e1", "name": "Entidad", "entity_type": "lugar",
             "layers": ["geografia", "cultura"]},
        ])
        m = _apply_migration_v6_to_v7(v6)
        assert m["entities"][0]["layers"] == ["geografia", "cultura"]

    def test_does_not_infer_domain_ids_from_legacy_domain(self):
        """domain_ids must stay [] even when domain: str has a value."""
        v6 = _v6_minimal(entities=[
            {"id": "e1", "name": "Entidad", "entity_type": "lugar",
             "domain": "mundo"},
        ])
        m = _apply_migration_v6_to_v7(v6)
        assert m["entities"][0]["domain_ids"] == []

    def test_does_not_infer_layer_ids_from_legacy_layers(self):
        """layer_ids must stay [] even when layers: list[str] has values."""
        v6 = _v6_minimal(entities=[
            {"id": "e1", "name": "Entidad", "entity_type": "lugar",
             "layers": ["layer_geografia"]},
        ])
        m = _apply_migration_v6_to_v7(v6)
        assert m["entities"][0]["layer_ids"] == []

    def test_does_not_mutate_original_dict(self):
        v6 = _v6_minimal()
        original_keys = set(v6.keys())
        _apply_migration_v6_to_v7(v6)
        assert "domains" not in v6
        assert "world_layers" not in v6
        assert "advanced_config" not in v6
        assert set(v6.keys()) == original_keys

    def test_empty_entities_and_relations_handled(self):
        v6 = _v6_minimal()  # entities=[], relations=[]
        m = _apply_migration_v6_to_v7(v6)
        assert m["entities"] == []
        assert m["relations"] == []


# ══════════════════════════════════════════════════════════════════
# Validation
# ══════════════════════════════════════════════════════════════════

class TestValidateDomains:
    def test_valid_domains_no_error(self):
        errors = validate_domains(["mundo", "historia", "campaña"])
        assert errors == []

    def test_empty_domains_error(self):
        errors = validate_domains([])
        assert len(errors) > 0
        assert any("empty" in e.lower() or "vac" in e.lower() for e in errors)

    def test_duplicate_domains_error(self):
        errors = validate_domains(["mundo", "historia", "mundo"])
        assert len(errors) > 0
        assert any("mundo" in e and ("duplic" in e.lower() or "dup" in e.lower())
                   for e in errors)

    def test_not_a_list_error(self):
        errors = validate_domains("not_a_list")  # type: ignore[arg-type]
        assert len(errors) > 0


class TestValidateWorldLayers:
    def test_valid_layers_no_error(self):
        layers = [
            {"id": "layer_a", "name": "Layer A", "order": 1},
            {"id": "layer_b", "name": "Layer B", "order": 2},
        ]
        errors = validate_world_layers(layers)
        assert errors == []

    def test_duplicate_id_error(self):
        layers = [
            {"id": "layer_a", "name": "Layer A"},
            {"id": "layer_a", "name": "Layer A Duplicate"},
        ]
        errors = validate_world_layers(layers)
        assert len(errors) > 0
        assert any("layer_a" in e and "duplic" in e.lower() for e in errors)

    def test_missing_id_error(self):
        layers = [{"name": "No ID Layer"}]
        errors = validate_world_layers(layers)
        assert len(errors) > 0
        assert any("id" in e.lower() for e in errors)

    def test_missing_name_error(self):
        layers = [{"id": "layer_x"}]
        errors = validate_world_layers(layers)
        assert len(errors) > 0
        assert any("name" in e.lower() for e in errors)

    def test_not_a_list_error(self):
        errors = validate_world_layers("not_a_list")  # type: ignore[arg-type]
        assert len(errors) > 0


class TestValidateAdvancedConfig:
    def test_valid_config_no_error(self):
        cfg = AdvancedProjectConfig().to_dict()
        errors = validate_advanced_config(cfg)
        assert errors == []

    def test_not_a_dict_error(self):
        errors = validate_advanced_config([])  # type: ignore[arg-type]
        assert len(errors) > 0

    def test_missing_key_fields_ok(self):
        """Missing optional fields is fine — they get defaults on load."""
        errors = validate_advanced_config({})
        assert errors == []


class TestValidateEntityDomainIds:
    def test_all_valid_no_warning(self):
        warnings = validate_entity_domain_ids(
            ["mundo", "historia"],
            valid_domains={"mundo", "historia", "campaña", "compartido", "sin_asignar"},
        )
        assert warnings == []

    def test_unknown_domain_warning(self):
        warnings = validate_entity_domain_ids(
            ["mundo", "no_existe"],
            valid_domains={"mundo", "historia"},
        )
        assert len(warnings) > 0
        assert any("no_existe" in w for w in warnings)

    def test_empty_domain_ids_no_warning(self):
        warnings = validate_entity_domain_ids(
            [],
            valid_domains={"mundo", "historia"},
        )
        assert warnings == []


# ══════════════════════════════════════════════════════════════════
# ProjectStore v7 roundtrip
# ══════════════════════════════════════════════════════════════════

class TestProjectStoreRoundtripV7:
    def test_v7_project_roundtrip_preserves_domains(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "project.json"

        # Create a fresh v7 project
        project = Project(id="proj-r1", name="Roundtrip 1")
        project.domains = ["mundo", "campaña"]
        result = store.save(project, path)
        assert isinstance(result, Ok)

        # Load it back
        result2 = store.load(path)
        assert isinstance(result2, Ok)
        loaded = result2.value
        assert loaded.domains == ["mundo", "campaña"]

    def test_v7_project_roundtrip_preserves_world_layers(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "project.json"

        project = Project(id="proj-r2", name="Roundtrip 2")
        project.world_layers = default_world_layers()
        # Modify a layer
        project.world_layers[0].name = "Custom Premisa"
        project.world_layers[0].description = "Custom description"

        result = store.save(project, path)
        assert isinstance(result, Ok)

        result2 = store.load(path)
        assert isinstance(result2, Ok)
        loaded = result2.value
        assert loaded.world_layers[0].name == "Custom Premisa"
        assert loaded.world_layers[0].description == "Custom description"
        assert len(loaded.world_layers) == 16

    def test_v7_project_roundtrip_preserves_advanced_config(self, tmp_path: Path):
        store = ProjectStore()
        path = tmp_path / "project.json"

        project = Project(id="proj-r3", name="Roundtrip 3")
        project.advanced_config.primary_genre = "fantasía épica"
        project.advanced_config.subgenres = ["alta fantasía", "espada y brujería"]
        project.advanced_config.realism_level = "alto"

        result = store.save(project, path)
        assert isinstance(result, Ok)

        result2 = store.load(path)
        assert isinstance(result2, Ok)
        loaded = result2.value
        assert loaded.advanced_config.primary_genre == "fantasía épica"
        assert "alta fantasía" in loaded.advanced_config.subgenres
        assert loaded.advanced_config.realism_level == "alto"


# ══════════════════════════════════════════════════════════════════
# Migration chain: v1 → v7 (accumulative)
# ══════════════════════════════════════════════════════════════════

class TestMigrationChainV1ToV9:
    """A project that starts at v1 should migrate all the way to v8."""

    def _v1_data(self) -> dict:
        return {
            "schema_version": 1,
            "id": "proj-legacy",
            "name": "Legacy Project",
            "created_at": "2025-01-01T00:00:00+00:00",
            "updated_at": "2025-01-01T00:00:00+00:00",
        }

    def test_v1_migrates_to_v9_via_load_project_data(self, tmp_path: Path):
        path = tmp_path / "legacy.json"
        v1 = self._v1_data()
        path.write_text(json.dumps(v1, indent=2), encoding="utf-8")

        result = load_project_data(path)
        assert isinstance(result, Ok), f"Expected Ok, got {result}"
        data = result.value

        # Verify the result is v7
        assert data["schema_version"] == 20

        # All v7 fields present
        assert data["domains"] == [
            "mundo", "historia", "campaña", "compartido", "sin_asignar",
        ]
        assert len(data["world_layers"]) == 16
        assert "advanced_config" in data

        # All intermediate migration fields present
        assert "description" in data  # v2
        assert "entities" in data  # v2/v3
        assert "relations" in data  # v4
        assert "custom_entity_types" in data  # v6

    def test_v6_migrates_to_v9_via_load_project_data(self, tmp_path: Path):
        path = tmp_path / "v6proj.json"
        v6 = _v6_minimal()
        v6["schema_version"] = 6
        path.write_text(json.dumps(v6, indent=2), encoding="utf-8")

        result = load_project_data(path)
        assert isinstance(result, Ok), f"Expected Ok, got {result}"
        data = result.value
        assert data["schema_version"] == 20

        # Legacy data preserved
        assert data["id"] == "proj-001"
        assert data["name"] == "Test Project"

        # New fields added
        assert len(data["domains"]) == 5

    def test_v9_project_loads_directly_no_migration(self, tmp_path: Path):
        path = tmp_path / "v7proj.json"
        v7 = _v6_minimal()
        v7["schema_version"] = 7
        v7["domains"] = ["mundo", "historia"]
        v7["world_layers"] = [
            {"id": "layer_x", "name": "Custom", "order": 1,
             "is_visible": True, "is_default": False, "description": "",
             "metadata": {}}
        ]
        v7["advanced_config"] = AdvancedProjectConfig().to_dict()
        for e in v7["entities"]:
            e.setdefault("domain_ids", [])
            e.setdefault("layer_ids", [])
        for r in v7["relations"]:
            r.setdefault("layer_ids", [])

        path.write_text(json.dumps(v7, indent=2), encoding="utf-8")

        result = load_project_data(path)
        assert isinstance(result, Ok), f"Expected Ok, got {result}"
        data = result.value
        assert data["schema_version"] == 20
        assert data["domains"] == ["mundo", "historia"]
        assert len(data["world_layers"]) == 1
        assert data["world_layers"][0]["name"] == "Custom"


# ══════════════════════════════════════════════════════════════════
# Future version rejection
# ══════════════════════════════════════════════════════════════════

class TestFutureVersionRejection:
    def test_v20_rejected(self, tmp_path: Path):
        path = tmp_path / "future.json"
        future = {"schema_version": 20, "id": "x", "name": "Future",
                   "created_at": "2026-01-01T00:00:00+00:00",
                   "updated_at": "2026-01-01T00:00:00+00:00"}
        path.write_text(json.dumps(future), encoding="utf-8")

        result = load_project_data(path)
        assert isinstance(result, Error)
        assert "v19" in result.error or "schema" in result.error.lower()

    def test_v7_passes_validation(self, tmp_path: Path):
        path = tmp_path / "v7ok.json"
        v7 = _v6_minimal()
        v7["schema_version"] = 7
        v7["domains"] = ["mundo", "historia", "campaña", "compartido", "sin_asignar"]
        v7["world_layers"] = [
            {"id": "layer_premisa", "name": "Premisa", "order": 1,
             "is_visible": True, "is_default": True, "description": "", "metadata": {}}
        ]
        v7["advanced_config"] = AdvancedProjectConfig().to_dict()
        for e in v7["entities"]:
            e.setdefault("domain_ids", [])
            e.setdefault("layer_ids", [])
        for r in v7["relations"]:
            r.setdefault("layer_ids", [])

        path.write_text(json.dumps(v7, indent=2), encoding="utf-8")

        result = load_project_data(path)
        assert isinstance(result, Ok), f"Expected Ok, got {result}"


# ══════════════════════════════════════════════════════════════════
# validate_project_structure extends to new fields
# ══════════════════════════════════════════════════════════════════

class TestStructureValidationV7:
    def test_valid_v7_passes(self):
        data = _v6_minimal()
        data["schema_version"] = 7
        data["domains"] = ["mundo"]
        data["world_layers"] = [
            {"id": "layer_premisa", "name": "Premisa", "order": 1,
             "is_visible": True, "is_default": True, "description": "", "metadata": {}}
        ]
        data["advanced_config"] = AdvancedProjectConfig().to_dict()
        for e in data["entities"]:
            e.setdefault("domain_ids", [])
            e.setdefault("layer_ids", [])
        for r in data["relations"]:
            r.setdefault("layer_ids", [])
        assert validate_project_structure(data) is None

    def test_domains_not_a_list_fails(self):
        data = _v6_minimal()
        data["domains"] = "not_a_list"
        err = validate_project_structure(data)
        assert err is not None
        assert "domains" in err.lower()

    def test_world_layers_not_a_list_fails(self):
        data = _v6_minimal()
        data["world_layers"] = "not_a_list"
        err = validate_project_structure(data)
        assert err is not None
        assert "world_layers" in err.lower()

    def test_advanced_config_not_a_dict_fails(self):
        data = _v6_minimal()
        data["advanced_config"] = []
        err = validate_project_structure(data)
        assert err is not None
        assert "advanced_config" in err.lower()
