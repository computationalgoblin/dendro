"""B20-T05 QA tests — campaign layer integration, regression and smoke."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from packages.application.campaign_service import CampaignService
from packages.application.project_service import ProjectService
from packages.application.entity_service import EntityService
from packages.persistence.store import ProjectStore
from packages.domain.campaign_models import (
    Campaign, CampaignPlayer, CampaignState, CampaignClock, CampaignClockState,
    PlayerCharacterProfile,
)
from packages.domain.entity import EntityType
from packages.domain.result import Error, Ok
from packages.persistence.schema import CURRENT_SCHEMA_VERSION

WORKSPACE = Path(__file__).resolve().parent.parent.parent


# ── Helpers ──────────────────────────────────────────────────────────


def _bootstrap(path: Path):
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.open(path)
    es = EntityService(project_service=ps, store=store)
    cs = CampaignService(project_service=ps, entity_service=es)
    return ps, es, cs


@pytest.fixture
def svc(tmp_path):
    path = tmp_path / "test.json"
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Test")
    ps.save(path)
    # Re-open with a fresh bootstrap so ps, cs share the same store
    ps2, es2, cs2 = _bootstrap(path)
    return ps2, es2, cs2, path


def _add_entity(es, name: str, etype: EntityType):
    r = es.create_entity({"name": name, "entity_type": etype.value})
    assert isinstance(r, Ok)
    return r.value.id


# ── Integration: CampaignService ─────────────────────────────────────


class TestCampaignIntegration:
    def test_create_and_list(self, svc):
        ps, es, cs, path = svc
        r = cs.create_campaign({"name": "C1"})
        assert isinstance(r, Ok)
        c1 = r.value

        r = cs.create_campaign({"name": "C2"})
        assert isinstance(r, Ok)

        campaigns = cs.list_campaigns()
        assert len(campaigns) == 2

    def test_full_workflow(self, svc):
        ps, es, cs, path = svc

        # Create campaign
        c = cs.create_campaign({
            "name": "Epic Quest",
            "game_system": "Pathfinder",
            "tone": "épico",
        }).value

        # Add entities
        gandalf_id = _add_entity(es, "Gandalf", EntityType.PERSONAJE)
        frodo_id = _add_entity(es, "Frodo", EntityType.PERSONAJE)
        compania_id = _add_entity(es, "La Compañía", EntityType.FACCION)
        rivendel_id = _add_entity(es, "Rivendel", EntityType.LOCALIZACION)
        anillo_id = _add_entity(es, "El Anillo", EntityType.SECRETO)

        # Add players
        juan = cs.add_player(c.id, "Juan").value
        maria = cs.add_player(c.id, "María").value
        assert juan.id.startswith("plr_")
        assert maria.id != juan.id

        # Assign PCs
        p1 = cs.assign_player_character(c.id, juan.id, gandalf_id).value
        p2 = cs.assign_player_character(c.id, maria.id, frodo_id).value
        assert p1.id.startswith("prof_")

        # Link entities
        cs.link_entity_to_campaign(c.id, compania_id, "faction")
        cs.link_entity_to_campaign(c.id, rivendel_id, "location")
        cs.link_entity_to_campaign(c.id, anillo_id, "secret")

        # Create clock
        clock = cs.create_clock(c.id, {"name": "El Culto avanza", "max_value": 6}).value
        cs.advance_clock(clock.id, by=3)

        # History
        campaign = cs.get_campaign(c.id).value
        assert len(campaign.history) >= 8  # create + 2 players + 2 PCs + 3 links + clock + advance

        # Persistence roundtrip
        ps.save(path)
        ps2, es2, cs2 = _bootstrap(path)
        c2 = cs2.get_campaign(c.id).value
        assert c2.name == "Epic Quest"
        assert len(c2.players) == 2
        assert len(c2.player_character_entity_ids) == 2
        assert len(c2.active_faction_entity_ids) == 1
        assert len(c2.clock_ids) == 1

        # Archive
        cs.archive_campaign(c.id)
        archived = cs.get_campaign(c.id).value
        assert archived.state == CampaignState.ARCHIVADA

        # Not in active list
        active = cs.list_campaigns()
        assert len(active) == 0

        # In full list
        full = cs.list_campaigns(include_archived=True)
        assert len(full) == 1


class TestCampaignValidations:
    def test_assign_pc_invalid_player(self, svc):
        ps, es, cs, path = svc
        c = cs.create_campaign({"name": "Test"}).value
        entity_id = _add_entity(es, "TestChar", EntityType.PERSONAJE)
        r = cs.assign_player_character(c.id, "plr_fake", entity_id)
        assert isinstance(r, Error)

    def test_assign_pc_wrong_type(self, svc):
        ps, es, cs, path = svc
        c = cs.create_campaign({"name": "Test"}).value
        player = cs.add_player(c.id, "Juan").value
        loc_id = _add_entity(es, "TestLoc", EntityType.LOCALIZACION)
        r = cs.assign_player_character(c.id, player.id, loc_id)
        assert isinstance(r, Error)

    def test_advance_clock_overflow(self, svc):
        ps, es, cs, path = svc
        c = cs.create_campaign({"name": "Test"}).value
        clock = cs.create_clock(c.id, {"name": "Reloj", "max_value": 3}).value
        r = cs.advance_clock(clock.id, by=5)
        assert isinstance(r, Error)

    def test_advance_clock_zero(self, svc):
        ps, es, cs, path = svc
        c = cs.create_campaign({"name": "Test"}).value
        clock = cs.create_clock(c.id, {"name": "Reloj", "max_value": 3}).value
        r = cs.advance_clock(clock.id, by=0)
        assert isinstance(r, Error)

    def test_remove_player_with_pcs(self, svc):
        ps, es, cs, path = svc
        c = cs.create_campaign({"name": "Test"}).value
        player = cs.add_player(c.id, "Juan").value
        entity_id = _add_entity(es, "PC", EntityType.PERSONAJE)
        cs.assign_player_character(c.id, player.id, entity_id)
        r = cs.remove_player(c.id, player.id)
        assert isinstance(r, Error)


class TestCampaignOverview:
    def test_overview_resolves_all(self, svc):
        ps, es, cs, path = svc
        c = cs.create_campaign({"name": "Overview Test"}).value

        gandalf_id = _add_entity(es, "Gandalf", EntityType.PERSONAJE)
        compania_id = _add_entity(es, "La Compañía", EntityType.FACCION)

        player = cs.add_player(c.id, "Juan").value
        cs.assign_player_character(c.id, player.id, gandalf_id)
        cs.link_entity_to_campaign(c.id, compania_id, "faction")
        cs.create_clock(c.id, {"name": "Clock1", "max_value": 4})

        overview = cs.get_campaign_overview(c.id).value
        assert overview["campaign"]["name"] == "Overview Test"
        assert len(overview["players"]) == 1
        assert overview["players"][0]["name"] == "Juan"
        assert len(overview["player_characters"]) == 1
        assert overview["player_characters"][0]["entity_name"] == "Gandalf"
        assert len(overview["active_factions"]) == 1
        assert overview["active_factions"][0]["name"] == "La Compañía"
        assert len(overview["clocks"]) == 1


class TestCampaignSchema:
    def test_schema_is_v14(self):
        assert CURRENT_SCHEMA_VERSION == 18

    def test_migration_roundtrip(self, tmp_path):
        """v13 data migrates to v14 with empty campaign collections."""
        from packages.persistence.schema import _apply_migration_v13_to_v14
        v13 = {"schema_version": 13, "id": "p", "name": "Old",
               "created_at": "2026-01-01T00:00:00+00:00",
               "updated_at": "2026-01-01T00:00:00+00:00",
               "writing_units": [], "entities": []}
        v14 = _apply_migration_v13_to_v14(v13)
        assert v14["schema_version"] == 14
        assert v14["campaigns"] == []
        assert v14["player_character_profiles"] == []
        assert v14["campaign_clocks"] == []


# ── Regression ───────────────────────────────────────────────────────


class TestRegression:
    """Verify B1-B19 features still work after B20 changes."""

    def test_entities_still_work(self, svc):
        ps, es, cs, path = svc
        eid = _add_entity(es, "Entity1", EntityType.PERSONAJE)
        r = es.get_by_id(eid)
        assert isinstance(r, Ok)
        assert r.value.name == "Entity1"

    def test_project_schema_version(self, svc):
        ps, es, cs, path = svc
        data = ps.active_project.to_dict()
        ps.save(path)
        raw = json.loads(path.read_text())
        assert raw["schema_version"] == 14

    def test_writing_units_unaffected(self, svc):
        ps, es, cs, path = svc
        assert ps.active_project.writing_units == []
        assert ps.active_project.campaigns == []

    def test_campaigns_collection_serialized(self, svc):
        ps, es, cs, path = svc
        cs.create_campaign({"name": "Test"})
        ps.save(path)
        raw = json.loads(path.read_text())
        assert "campaigns" in raw
        assert len(raw["campaigns"]) == 1
        assert raw["campaigns"][0]["name"] == "Test"


# ── CLI integration tests ───────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_session():
    session_file = WORKSPACE / ".narrative-session.json"
    try:
        session_file.unlink()
    except FileNotFoundError:
        pass


def _cli(args_str: str, cwd: str | None = None):
    """Run narrative-architect CLI as subprocess."""
    args = shlex.split(args_str)
    env = {**os.environ, "PYTHONPATH": str(WORKSPACE)}
    result = subprocess.run(
        [sys.executable, "-m", "narrative_architect"] + args,
        capture_output=True, text=True,
        cwd=cwd or str(WORKSPACE),
        env=env,
    )
    return result


class TestCLICampaign:
    def test_help(self):
        r = _cli("campaign --help")
        assert r.returncode == 0
        assert "create" in r.stdout

    def test_create_and_list(self, tmp_path):
        proj = tmp_path / "cli_test.json"
        _cli(f"project create Test --path {proj}")

        r = _cli(f"campaign create 'MyCampaign' --system D&D")
        assert "created" in r.stdout

        r = _cli("campaign list")
        assert "MyCampaign" in r.stdout
        assert r.returncode == 0

        r = _cli("campaign list --json")
        data = json.loads(r.stdout)
        assert data["total"] == 1

    def test_full_cli_flow(self, tmp_path):
        proj = tmp_path / "full_test.json"
        _cli(f"project create 'FullTest' --path {proj}")

        # Create entities
        _cli("entity create Gandalf --type personaje")
        _cli("entity create 'La Compañía' --type faccion")

        # Create campaign
        r = _cli("campaign create 'Epic' --system 'D&D 5e' --tone épico")
        assert "created" in r.stdout
        assert r.returncode == 0

        # Get campaign ID from output
        camp_id = r.stdout.split("(")[1].split(")")[0]

        # List campaigns
        r = _cli("campaign list --json")
        data = json.loads(r.stdout)
        assert data["total"] == 1

        # Add player
        r = _cli(f"campaign player-add {camp_id} Juan")
        assert "Player 'Juan'" in r.stdout
        player_id = r.stdout.split("(")[1].split(")")[0]

        # Get entity IDs from list --json output
        r = _cli("entity list --json")
        data = json.loads(r.stdout)
        entities = data.get("entities", [])
        gandalf_id = None
        compania_id = None
        for e in entities:
            if e.get("name") == "Gandalf":
                gandalf_id = e["id"]
            if e.get("name") == "La Compañía":
                compania_id = e["id"]
        assert gandalf_id is not None

        # Assign PC
        r = _cli(f"campaign pc-assign {camp_id} {player_id} {gandalf_id}")
        assert "created" in r.stdout
        assert r.returncode == 0

        # Link
        r = _cli(f"campaign link {camp_id} {compania_id} --role faction")
        assert "linked" in r.stdout

        # PC list
        r = _cli(f"campaign pc-list --campaign {camp_id} --json")
        data = json.loads(r.stdout)
        assert data["total"] == 1

        # Clock
        r = _cli(f"campaign clock-create {camp_id} 'Reloj' --max 4")
        assert "created" in r.stdout
        clock_id = r.stdout.split("(")[1].split(")")[0]

        r = _cli(f"campaign clock-advance {clock_id} --by 2")
        assert "advanced" in r.stdout

        r = _cli(f"campaign clock-list --campaign {camp_id} --json")
        data = json.loads(r.stdout)
        assert data["total"] == 1
        assert data["clocks"][0]["current_value"] == 2

        # Overview
        r = _cli(f"campaign overview {camp_id} --json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert "players" in data

        # Save and verify persistence
        _cli("project save")
        _cli("project close")
        r = _cli(f"project open {proj}")
        assert "opened" in r.stdout.lower() or "open" in r.stdout.lower()

        r = _cli(f"campaign overview {camp_id} --json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["campaign"]["name"] == "Epic"

        # Archive
        r = _cli(f"campaign archive {camp_id}")
        assert r.returncode == 0 or "archived" in r.stdout.lower()

        # Verify archived not in list
        r = _cli("campaign list --json")
        data = json.loads(r.stdout)
        assert data["total"] == 0  # archived excluded

    def test_edit_command(self, tmp_path):
        proj = tmp_path / "edit_test.json"
        _cli(f"project create 'EditTest' --path {proj}")
        r = _cli("campaign create 'Original' --system D&D")
        camp_id = r.stdout.split("(")[1].split(")")[0]

        r = _cli(f"campaign edit {camp_id} --name 'Renamed' --tone sombrío")
        assert r.returncode == 0
        assert "updated" in r.stdout.lower()

        r = _cli(f"campaign show {camp_id}")
        assert "Renamed" in r.stdout
