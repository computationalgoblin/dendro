"""Tests for Bloque 20 schema v14 — campaign collections (B20-T02)."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from packages.persistence.schema import (
    CURRENT_SCHEMA_VERSION,
    _apply_migration_v13_to_v14,
    _validate_campaigns,
    _validate_player_character_profiles,
    _validate_campaign_clocks,
)
from packages.persistence.store import load_project_data, save_project_data
from packages.domain.project import Project
from packages.domain.result import Ok, Error
from packages.domain.campaign_models import Campaign, CampaignPlayer, PlayerCharacterProfile, CampaignClock


# ═══════════════════════════════════════════════════════════════════════
# Schema version
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaV14Basics:
    def test_current_version_is_14(self):
        assert CURRENT_SCHEMA_VERSION == 15

    def test_migration_adds_empty_lists(self):
        data = {"schema_version": 13, "writing_units": [], "entities": []}
        result = _apply_migration_v13_to_v14(data)
        assert result["schema_version"] == 14
        assert result["campaigns"] == []
        assert result["player_character_profiles"] == []
        assert result["campaign_clocks"] == []

    def test_migration_preserves_existing_data(self):
        data = {
            "schema_version": 13,
            "writing_units": [{"id": "wu1", "name": "test"}],
            "entities": [{"id": "e1", "name": "Test", "entity_type": "personaje"}],
        }
        result = _apply_migration_v13_to_v14(data)
        assert len(result["writing_units"]) == 1
        assert result["writing_units"][0]["id"] == "wu1"
        assert len(result["entities"]) == 1


# ═══════════════════════════════════════════════════════════════════════
# Campaign validation
# ═══════════════════════════════════════════════════════════════════════


class TestValidateCampaigns:
    def test_empty_list_valid(self):
        assert _validate_campaigns([]) == []

    def test_non_list_errors(self):
        assert len(_validate_campaigns("not a list")) > 0

    def test_single_campaign_valid(self):
        campaigns = [{"id": "cam1", "name": "Test"}]
        assert _validate_campaigns(campaigns) == []

    def test_duplicate_ids_error(self):
        campaigns = [
            {"id": "cam1", "name": "A"},
            {"id": "cam1", "name": "B"},
        ]
        errors = _validate_campaigns(campaigns)
        assert len(errors) > 0
        assert "duplicate" in errors[0].lower()

    def test_missing_id_error(self):
        campaigns = [{"name": "No ID"}]
        errors = _validate_campaigns(campaigns)
        assert len(errors) > 0
        assert "missing id" in errors[0].lower()

    def test_non_dict_item_error(self):
        campaigns = ["not a dict"]
        errors = _validate_campaigns(campaigns)
        assert len(errors) > 0


# ═══════════════════════════════════════════════════════════════════════
# PlayerCharacterProfile validation
# ═══════════════════════════════════════════════════════════════════════


class TestValidatePlayerCharacterProfiles:
    def test_empty_list_valid(self):
        assert _validate_player_character_profiles([]) == []

    def test_valid_profile(self):
        profiles = [{"id": "prof1", "entity_id": "ent_gandalf", "player_id": "plr_juan"}]
        assert _validate_player_character_profiles(profiles) == []

    def test_entity_id_mandatory(self):
        profiles = [{"id": "prof1"}]
        errors = _validate_player_character_profiles(profiles)
        assert len(errors) > 0
        assert "entity_id" in errors[0].lower()

    def test_entity_id_empty_string(self):
        profiles = [{"id": "prof1", "entity_id": ""}]
        errors = _validate_player_character_profiles(profiles)
        assert len(errors) > 0
        assert "entity_id" in errors[0].lower()

    def test_entity_id_whitespace_only(self):
        profiles = [{"id": "prof1", "entity_id": "   "}]
        errors = _validate_player_character_profiles(profiles)
        assert len(errors) > 0

    def test_duplicate_ids(self):
        profiles = [
            {"id": "prof1", "entity_id": "e1"},
            {"id": "prof1", "entity_id": "e2"},
        ]
        errors = _validate_player_character_profiles(profiles)
        assert len(errors) > 0


# ═══════════════════════════════════════════════════════════════════════
# CampaignClock validation
# ═══════════════════════════════════════════════════════════════════════


class TestValidateCampaignClocks:
    def test_empty_list_valid(self):
        assert _validate_campaign_clocks([]) == []

    def test_valid_clock(self):
        clocks = [{"id": "clk1", "name": "Test", "current_value": 0, "max_value": 4}]
        assert _validate_campaign_clocks(clocks) == []

    def test_duplicate_ids(self):
        clocks = [
            {"id": "clk1", "name": "A"},
            {"id": "clk1", "name": "B"},
        ]
        errors = _validate_campaign_clocks(clocks)
        assert len(errors) > 0

    def test_cross_reference_missing_clock(self):
        """Campaign references a clock that doesn't exist."""
        clocks = [{"id": "clk1", "name": "A"}]
        all_clock_ids = {"clk1", "clk2"}
        errors = _validate_campaign_clocks(clocks, all_campaign_clock_ids=all_clock_ids)
        assert len(errors) > 0
        assert "clk2" in errors[0]

    def test_cross_reference_all_exist(self):
        clocks = [{"id": "clk1", "name": "A"}, {"id": "clk2", "name": "B"}]
        all_clock_ids = {"clk1", "clk2"}
        errors = _validate_campaign_clocks(clocks, all_campaign_clock_ids=all_clock_ids)
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════
# Persistence roundtrip
# ═══════════════════════════════════════════════════════════════════════


class TestCampaignPersistenceRoundtrip:
    def test_project_save_load_with_campaigns(self, tmp_path: Path):
        """Campaign data survives save/load roundtrip."""
        path = tmp_path / "campaign_project.json"

        # Create project with campaign data
        player = CampaignPlayer(name="Juan")
        campaign = Campaign(
            name="La Sombra",
            game_system="D&D 5e",
            tone="épico",
            players=[player],
            active_faction_entity_ids=["ent_fac1"],
        )
        profile = PlayerCharacterProfile(
            entity_id="ent_gandalf",
            player_id=player.id,
            objectives=["Destruir el anillo"],
        )
        clock = CampaignClock(
            name="El Culto avanza",
            max_value=6,
            current_value=2,
        )

        p = Project(name="Test Campaign")
        p.campaigns.append(campaign)
        p.player_character_profiles.append(profile)
        p.campaign_clocks.append(clock)

        # Save
        save_result = save_project_data(p.to_dict(), path)
        assert isinstance(save_result, Ok), f"Save failed: {save_result}"

        # Load
        load_result = load_project_data(path)
        assert isinstance(load_result, Ok), f"Load failed: {load_result}"
        data = load_result.value

        assert data["schema_version"] == 15
        assert len(data["campaigns"]) == 1
        assert data["campaigns"][0]["name"] == "La Sombra"
        assert len(data["campaigns"][0]["players"]) == 1
        assert data["campaigns"][0]["players"][0]["name"] == "Juan"

        assert len(data["player_character_profiles"]) == 1
        assert data["player_character_profiles"][0]["entity_id"] == "ent_gandalf"

        assert len(data["campaign_clocks"]) == 1
        assert data["campaign_clocks"][0]["name"] == "El Culto avanza"
        assert data["campaign_clocks"][0]["current_value"] == 2

    def test_project_from_dict_with_campaign_data(self):
        """Project.from_dict loads campaign collections correctly."""
        data = {
            "id": "proj1",
            "name": "Test",
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "campaigns": [
                {
                    "id": "cam1",
                    "name": "Test Campaign",
                    "state": "activa",
                    "game_system": "Pathfinder",
                    "players": [{"id": "plr_01", "name": "Ana"}],
                }
            ],
            "player_character_profiles": [
                {
                    "id": "prof1",
                    "entity_id": "ent_pc1",
                    "player_id": "plr_01",
                    "objectives": ["obj1"],
                }
            ],
            "campaign_clocks": [
                {
                    "id": "clk1",
                    "name": "Reloj",
                    "current_value": 1,
                    "max_value": 4,
                    "state": "active",
                }
            ],
        }
        p = Project.from_dict(data)
        assert len(p.campaigns) == 1
        assert p.campaigns[0].name == "Test Campaign"
        assert len(p.campaigns[0].players) == 1
        assert p.campaigns[0].players[0].name == "Ana"

        assert len(p.player_character_profiles) == 1
        assert p.player_character_profiles[0].entity_id == "ent_pc1"
        assert p.player_character_profiles[0].player_id == "plr_01"

        assert len(p.campaign_clocks) == 1
        assert p.campaign_clocks[0].name == "Reloj"

    def test_v13_project_migrates_to_v14(self, tmp_path: Path):
        """A v13 project loads as v14 with empty campaign collections."""
        path = tmp_path / "v13_project.json"
        v13_data = {
            "schema_version": 13,
            "id": "proj_old",
            "name": "Old Project",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "writing_units": [],
            "entities": [
                {"id": "e1", "name": "Gandalf", "entity_type": "personaje",
                 "created_at": "2026-01-01T00:00:00+00:00",
                 "updated_at": "2026-01-01T00:00:00+00:00"}
            ],
        }
        # Write directly to disk — don't use save_project_data which upgrades version
        path.write_text(json.dumps(v13_data, indent=2), encoding="utf-8")

        load_result = load_project_data(path)
        assert isinstance(load_result, Ok), f"Load failed: {load_result}"
        data = load_result.value

        assert data["schema_version"] == 15
        assert "entities" in data
        assert len(data["entities"]) == 1
        # Migration v13→v14 adds the three campaign collections
        assert data.get("campaigns") == []
        assert data.get("player_character_profiles") == []
        assert data.get("campaign_clocks") == []

    def test_entity_id_mandatory_rejected(self, tmp_path: Path):
        """Schema validation rejects player_character_profile without entity_id."""
        path = tmp_path / "bad_profile.json"
        data = {
            "schema_version": 14,
            "id": "proj1",
            "name": "Test",
            "created_at": "2026-06-01T00:00:00+00:00",
            "updated_at": "2026-06-01T00:00:00+00:00",
            "player_character_profiles": [
                {"id": "prof1", "player_id": "plr_x"}
                # missing entity_id
            ],
        }
        save_result = save_project_data(data, path)
        assert isinstance(save_result, Ok)

        load_result = load_project_data(path)
        assert isinstance(load_result, Error), f"Should reject missing entity_id, got: {load_result}"
        assert "entity_id" in str(load_result.error).lower()
