"""Tests for CampaignService (B20-T03)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from packages.application.campaign_service import CampaignService
from packages.application.project_service import ProjectService
from packages.persistence.store import ProjectStore
from packages.domain.project import Project
from packages.domain.entity import NarrativeEntity, EntityType, CanonState, VisibilityState
from packages.domain.campaign_models import (
    Campaign,
    CampaignPlayer,
    CampaignState,
    CampaignClock,
    CampaignClockState,
    PlayerCharacterProfile,
)
from packages.domain.result import Ok, Error


# ── Fixture helpers ─────────────────────────────────────────────────


def _make_project_with_entities() -> tuple[Project, CampaignService]:
    """Create a project with some entities and a CampaignService."""
    project = Project(name="Test Project")

    # Add test entities
    entity_types = {
        "Gandalf": EntityType.PERSONAJE,
        "La Compañía": EntityType.FACCION,
        "Rivendel": EntityType.LOCALIZACION,
        "El Anillo": EntityType.SECRETO,
        "Mapa antiguo": EntityType.PISTA,
        "Destruir el Anillo": EntityType.TRAMA,
        "Tierra Media": EntityType.LOCALIZACION,
    }
    for name, etype in entity_types.items():
        entity = NarrativeEntity(
            name=name,
            entity_type=etype,
            canon_state=CanonState.CANONICO,
            visibility_state=VisibilityState.VISIBLE_USUARIO,
        )
        project.entities.append(entity)

    # Setup ProjectService + CampaignService
    ps = MagicMock(spec=ProjectService)
    ps.active_project = project
    ps.save.return_value = Ok(None)

    # Create a real EntityService mock
    es = MagicMock()
    def get_entity(eid):
        for e in project.entities:
            if e.id == eid:
                return Ok(e)
        return Error(f"Entity '{eid}' not found")
    es.get_by_id = get_entity

    svc = CampaignService(project_service=ps, entity_service=es)
    return project, svc


def _create_test_campaign(svc: CampaignService) -> Campaign:
    result = svc.create_campaign({
        "name": "La Sombra",
        "game_system": "D&D 5e",
        "tone": "épico",
        "genre": "fantasía",
    })
    assert isinstance(result, Ok)
    return result.value


# ── CRUD ───────────────────────────────────────────────────────────


class TestCampaignCRUD:
    def test_create_campaign(self):
        _, svc = _make_project_with_entities()
        result = svc.create_campaign({"name": "Test"})
        assert isinstance(result, Ok)
        c = result.value
        assert c.name == "Test"
        assert len(c.id) == 12
        assert c.state == CampaignState.ACTIVA
        assert len(c.history) == 1

    def test_create_campaign_no_name_errors(self):
        _, svc = _make_project_with_entities()
        result = svc.create_campaign({"game_system": "D&D"})
        assert isinstance(result, Error)

    def test_get_campaign(self):
        _, svc = _make_project_with_entities()
        created = _create_test_campaign(svc)
        result = svc.get_campaign(created.id)
        assert isinstance(result, Ok)
        assert result.value.name == "La Sombra"

    def test_get_campaign_not_found(self):
        _, svc = _make_project_with_entities()
        result = svc.get_campaign("nonexistent")
        assert isinstance(result, Error)

    def test_list_campaigns(self):
        _, svc = _make_project_with_entities()
        _create_test_campaign(svc)
        svc.create_campaign({"name": "Second"})
        campaigns = svc.list_campaigns()
        assert len(campaigns) == 2

    def test_list_campaigns_excludes_archived(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        svc.archive_campaign(c.id)
        campaigns = svc.list_campaigns()
        assert len(campaigns) == 0  # archived excluded by default

    def test_list_campaigns_includes_archived(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        svc.archive_campaign(c.id)
        campaigns = svc.list_campaigns(include_archived=True)
        assert len(campaigns) == 1

    def test_update_campaign(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        result = svc.update_campaign(c.id, {"name": "Renamed", "tone": "sombrío"})
        assert isinstance(result, Ok)
        assert result.value.name == "Renamed"
        assert result.value.tone == "sombrío"
        assert len(result.value.history) == 2  # create + update

    def test_archive_campaign(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        result = svc.archive_campaign(c.id)
        assert isinstance(result, Ok)
        assert result.value.state == CampaignState.ARCHIVADA
        assert len(result.value.history) == 2

    def test_set_state(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        result = svc.set_state(c.id, "pausada")
        assert isinstance(result, Ok)
        assert result.value.state == CampaignState.PAUSADA

    def test_archive_does_not_delete(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        campaign_id = c.id
        svc.archive_campaign(campaign_id)
        # Campaign still in project
        archived = svc.get_campaign(campaign_id)
        assert isinstance(archived, Ok)
        assert archived.value.state == CampaignState.ARCHIVADA


# ── Players ────────────────────────────────────────────────────────


class TestPlayers:
    def test_add_player(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        result = svc.add_player(c.id, "Juan")
        assert isinstance(result, Ok)
        player = result.value
        assert player.name == "Juan"
        assert player.id.startswith("plr_")

        # Verify player is in campaign
        campaign = svc.get_campaign(c.id).value
        assert len(campaign.players) == 1
        assert campaign.players[0].name == "Juan"

    def test_add_player_empty_name(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        result = svc.add_player(c.id, "")
        assert isinstance(result, Error)

    def test_remove_player(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value
        result = svc.remove_player(c.id, player.id)
        assert isinstance(result, Ok)
        campaign = svc.get_campaign(c.id).value
        assert len(campaign.players) == 0

    def test_remove_player_with_assigned_pc(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value

        # Assign a PC first
        gandalf = next(e for e in project.entities if e.name == "Gandalf")
        svc.assign_player_character(c.id, player.id, gandalf.id)

        # Now try to remove player — should fail
        result = svc.remove_player(c.id, player.id)
        assert isinstance(result, Error)
        assert "assigned" in result.error.lower()

    def test_remove_player_not_found(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        result = svc.remove_player(c.id, "plr_nonexistent")
        assert isinstance(result, Error)


# ── Player Characters ──────────────────────────────────────────────


class TestPlayerCharacters:
    def test_assign_pc(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value
        gandalf = next(e for e in project.entities if e.name == "Gandalf")

        result = svc.assign_player_character(c.id, player.id, gandalf.id)
        assert isinstance(result, Ok)
        profile = result.value
        assert profile.entity_id == gandalf.id
        assert profile.player_id == player.id
        assert profile.id.startswith("prof_")

        # Verify campaign has the PC
        campaign = svc.get_campaign(c.id).value
        assert gandalf.id in campaign.player_character_entity_ids

    def test_assign_pc_invalid_player_id(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        gandalf = next(e for e in project.entities if e.name == "Gandalf")

        result = svc.assign_player_character(c.id, "plr_fake", gandalf.id)
        assert isinstance(result, Error)
        assert "player" in result.error.lower()

    def test_assign_pc_invalid_entity(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value

        result = svc.assign_player_character(c.id, player.id, "ent_fake")
        assert isinstance(result, Error)

    def test_assign_pc_wrong_entity_type(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value
        rivendel = next(e for e in project.entities if e.name == "Rivendel")

        result = svc.assign_player_character(c.id, player.id, rivendel.id)
        assert isinstance(result, Error)
        assert "personaje" in result.error.lower()

    def test_get_player_character_profile(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value
        gandalf = next(e for e in project.entities if e.name == "Gandalf")
        profile = svc.assign_player_character(c.id, player.id, gandalf.id).value

        result = svc.get_player_character_profile(profile.id)
        assert isinstance(result, Ok)
        assert result.value.entity_id == gandalf.id

    def test_list_player_character_profiles(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value
        gandalf = next(e for e in project.entities if e.name == "Gandalf")
        svc.assign_player_character(c.id, player.id, gandalf.id)

        profiles = svc.list_player_character_profiles()
        assert len(profiles) == 1

    def test_list_pc_by_campaign(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value
        gandalf = next(e for e in project.entities if e.name == "Gandalf")
        svc.assign_player_character(c.id, player.id, gandalf.id)

        profiles = svc.list_player_character_profiles(campaign_id=c.id)
        assert len(profiles) == 1

    def test_update_player_character_profile(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value
        gandalf = next(e for e in project.entities if e.name == "Gandalf")
        profile = svc.assign_player_character(c.id, player.id, gandalf.id).value

        result = svc.update_player_character_profile(profile.id, {
            "backstory": "Un mago sabio",
            "objectives": ["Ayudar a los hobbits"],
        })
        assert isinstance(result, Ok)
        assert result.value.backstory == "Un mago sabio"
        assert result.value.objectives == ["Ayudar a los hobbits"]


# ── Entity Linking ─────────────────────────────────────────────────


class TestEntityLinking:
    def test_link_faction(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        compania = next(e for e in project.entities if e.name == "La Compañía")

        result = svc.link_entity_to_campaign(c.id, compania.id, "faction")
        assert isinstance(result, Ok)
        campaign = svc.get_campaign(c.id).value
        assert compania.id in campaign.active_faction_entity_ids

    def test_link_location(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        rivendel = next(e for e in project.entities if e.name == "Rivendel")

        result = svc.link_entity_to_campaign(c.id, rivendel.id, "location")
        assert isinstance(result, Ok)
        campaign = svc.get_campaign(c.id).value
        assert rivendel.id in campaign.active_location_entity_ids

    def test_link_secret(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        anillo = next(e for e in project.entities if e.name == "El Anillo")

        result = svc.link_entity_to_campaign(c.id, anillo.id, "secret")
        assert isinstance(result, Ok)
        campaign = svc.get_campaign(c.id).value
        assert anillo.id in campaign.secret_entity_ids

    def test_link_clue(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        mapa = next(e for e in project.entities if e.name == "Mapa antiguo")

        result = svc.link_entity_to_campaign(c.id, mapa.id, "clue")
        assert isinstance(result, Ok)
        campaign = svc.get_campaign(c.id).value
        assert mapa.id in campaign.clue_entity_ids

    def test_link_plot(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        trama = next(e for e in project.entities if e.name == "Destruir el Anillo")

        result = svc.link_entity_to_campaign(c.id, trama.id, "plot")
        assert isinstance(result, Ok)
        campaign = svc.get_campaign(c.id).value
        assert trama.id in campaign.active_plot_entity_ids

    def test_link_other_accepts_any_type(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        rivendel = next(e for e in project.entities if e.name == "Rivendel")

        # Other accepts LOCATION (any type)
        result = svc.link_entity_to_campaign(c.id, rivendel.id, "other")
        assert isinstance(result, Ok)

    def test_link_invalid_role(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        compania = next(e for e in project.entities if e.name == "La Compañía")

        result = svc.link_entity_to_campaign(c.id, compania.id, "invalid_role")
        assert isinstance(result, Error)

    def test_link_wrong_type_for_role(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        rivendel = next(e for e in project.entities if e.name == "Rivendel")

        # LOCATION can't be linked as faction
        result = svc.link_entity_to_campaign(c.id, rivendel.id, "faction")
        assert isinstance(result, Error)

    def test_unlink(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        compania = next(e for e in project.entities if e.name == "La Compañía")
        svc.link_entity_to_campaign(c.id, compania.id, "faction")

        result = svc.unlink_entity_from_campaign(c.id, compania.id, "faction")
        assert isinstance(result, Ok)
        campaign = svc.get_campaign(c.id).value
        assert compania.id not in campaign.active_faction_entity_ids


# ── Clocks ─────────────────────────────────────────────────────────


class TestClocks:
    def test_create_clock(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)

        result = svc.create_clock(c.id, {"name": "El Culto avanza", "max_value": 6})
        assert isinstance(result, Ok)
        clock = result.value
        assert clock.name == "El Culto avanza"
        assert clock.max_value == 6
        assert clock.current_value == 0
        assert clock.state == CampaignClockState.active

        # Clock is in project
        campaign = svc.get_campaign(c.id).value
        assert clock.id in campaign.clock_ids

    def test_create_clock_no_name(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        result = svc.create_clock(c.id, {"max_value": 4})
        assert isinstance(result, Error)

    def test_advance_clock(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        clock = svc.create_clock(c.id, {"name": "Test", "max_value": 6}).value

        result = svc.advance_clock(clock.id, by=2)
        assert isinstance(result, Ok)
        assert result.value.current_value == 2

    def test_advance_clock_overflow_error(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        clock = svc.create_clock(c.id, {"name": "Test", "max_value": 4}).value

        # Advance past max
        result = svc.advance_clock(clock.id, by=5)
        assert isinstance(result, Error)
        assert "exceeds" in result.error.lower() or "max" in result.error.lower()

    def test_advance_clock_by_zero_or_negative(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        clock = svc.create_clock(c.id, {"name": "Test", "max_value": 4}).value

        result = svc.advance_clock(clock.id, by=0)
        assert isinstance(result, Error)

        result = svc.advance_clock(clock.id, by=-1)
        assert isinstance(result, Error)

    def test_advance_clock_to_max_completes(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        clock = svc.create_clock(c.id, {"name": "Test", "max_value": 4}).value

        result = svc.advance_clock(clock.id, by=4)
        assert isinstance(result, Ok)
        assert result.value.current_value == 4
        assert result.value.state == CampaignClockState.completed

    def test_list_clocks(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        svc.create_clock(c.id, {"name": "Clock A", "max_value": 4})
        svc.create_clock(c.id, {"name": "Clock B", "max_value": 6})

        clocks = svc.list_clocks()
        assert len(clocks) == 2

    def test_list_clocks_by_campaign(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        svc.create_clock(c.id, {"name": "Clock A", "max_value": 4})

        # Create second campaign with its own clock
        c2 = svc.create_campaign({"name": "Second"}).value
        svc.create_clock(c2.id, {"name": "Clock B", "max_value": 6})

        clocks = svc.list_clocks(campaign_id=c.id)
        assert len(clocks) == 1
        assert clocks[0].name == "Clock A"

    def test_get_clock(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        clock = svc.create_clock(c.id, {"name": "Test", "max_value": 4}).value

        result = svc.get_clock(clock.id)
        assert isinstance(result, Ok)
        assert result.value.name == "Test"


# ── History ────────────────────────────────────────────────────────


class TestHistory:
    def test_create_adds_history(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        assert len(c.history) == 1
        assert "created campaign" in c.history[0]

    def test_update_adds_history(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        svc.update_campaign(c.id, {"name": "New"})
        campaign = svc.get_campaign(c.id).value
        assert len(campaign.history) == 2

    def test_add_player_adds_history(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        svc.add_player(c.id, "Juan")
        campaign = svc.get_campaign(c.id).value
        assert len(campaign.history) == 2  # create + add player
        assert "added player" in campaign.history[1]

    def test_assign_pc_adds_history(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value
        gandalf = next(e for e in project.entities if e.name == "Gandalf")
        svc.assign_player_character(c.id, player.id, gandalf.id)
        campaign = svc.get_campaign(c.id).value
        assert len(campaign.history) == 3  # create + add player + assign PC

    def test_link_adds_history(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        compania = next(e for e in project.entities if e.name == "La Compañía")
        svc.link_entity_to_campaign(c.id, compania.id, "faction")
        campaign = svc.get_campaign(c.id).value
        assert len(campaign.history) == 2
        assert "linked" in campaign.history[1]

    def test_create_clock_adds_history(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        svc.create_clock(c.id, {"name": "Test", "max_value": 4})
        campaign = svc.get_campaign(c.id).value
        assert len(campaign.history) == 2
        assert "created clock" in campaign.history[1]

    def test_advance_clock_adds_history(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        clock = svc.create_clock(c.id, {"name": "Test", "max_value": 4}).value
        svc.advance_clock(clock.id, by=2)
        campaign = svc.get_campaign(c.id).value
        assert len(campaign.history) == 3  # create + create clock + advance

    def test_archive_adds_history(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        svc.archive_campaign(c.id)
        campaign = svc.get_campaign(c.id).value
        assert len(campaign.history) == 2
        assert "archived" in campaign.history[1]


# ── Overview ───────────────────────────────────────────────────────


class TestOverview:
    def test_overview_basic(self):
        _, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        result = svc.get_campaign_overview(c.id)
        assert isinstance(result, Ok)
        overview = result.value
        assert "campaign" in overview
        assert overview["campaign"]["name"] == "La Sombra"
        assert "players" in overview
        assert "clocks" in overview

    def test_overview_with_data(self):
        project, svc = _make_project_with_entities()
        c = _create_test_campaign(svc)
        player = svc.add_player(c.id, "Juan").value
        gandalf = next(e for e in project.entities if e.name == "Gandalf")
        compania = next(e for e in project.entities if e.name == "La Compañía")
        tierra_media = next(e for e in project.entities if e.name == "Tierra Media")

        svc.assign_player_character(c.id, player.id, gandalf.id)
        svc.link_entity_to_campaign(c.id, compania.id, "faction")
        svc.create_clock(c.id, {"name": "Reloj", "max_value": 4})

        # Set world
        svc.update_campaign(c.id, {"world_entity_id": tierra_media.id})

        result = svc.get_campaign_overview(c.id)
        assert isinstance(result, Ok)
        overview = result.value
        assert overview.get("world_name") == "Tierra Media"
        assert len(overview["player_characters"]) == 1
        assert overview["player_characters"][0]["entity_name"] == "Gandalf"
        assert len(overview["active_factions"]) == 1
        assert len(overview["clocks"]) == 1


# ── Project.touch integration ──────────────────────────────────────


class TestProjectTouch:
    def test_mutations_update_project_timestamp(self):
        import time
        project, svc = _make_project_with_entities()
        old_ts = project.updated_at
        time.sleep(0.001)  # ensure timestamp advances
        _create_test_campaign(svc)
        assert project.updated_at > old_ts
