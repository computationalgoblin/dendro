"""CampaignService — CRUD, linking, PCs, clocks, visibility, overview (B20-T03)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from packages.domain.campaign_models import (
    Campaign,
    CampaignPlayer,
    CampaignState,
    CampaignClock,
    CampaignClockState,
    PlayerCharacterProfile,
    _now,
)
from packages.domain.project import Project
from packages.domain.result import Error, Ok, Result


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class CampaignService:
    project_service: Any  # ProjectService
    entity_service: Any = None
    history_service: Any = None  # EntityService (optional)

    def _active_project(self) -> Project:
        return self.project_service.active_project

    def _add_history(self, campaign: Campaign, entry: str) -> None:
        campaign.history.append(f"[{_timestamp()}] {entry}")

    # ── CRUD ───────────────────────────────────────────────────────

    def create_campaign(self, data: dict) -> Result[Campaign, str]:
        proj = self._active_project()
        campaign = Campaign.from_dict(data)
        if not campaign.name:
            return Error("Campaign name is required")
        proj.campaigns.append(campaign)
        self._add_history(campaign, f"created campaign '{campaign.name}'")
        proj.touch()
        return Ok(campaign)

    def get_campaign(self, campaign_id: str) -> Result[Campaign, str]:
        proj = self._active_project()
        for c in proj.campaigns:
            if c.id == campaign_id:
                return Ok(c)
        return Error(f"Campaign '{campaign_id}' not found")

    def list_campaigns(self, include_archived: bool = False) -> list[Campaign]:
        proj = self._active_project()
        if include_archived:
            return list(proj.campaigns)
        return [c for c in proj.campaigns if c.state != CampaignState.ARCHIVADA]

    def update_campaign(self, campaign_id: str, data: dict) -> Result[Campaign, str]:
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value

        changed = []
        for field in ("name", "description", "world_entity_id", "game_system", "tone", "genre"):
            if field in data:
                setattr(campaign, field, data[field])
                changed.append(field)
        if "state" in data:
            from packages.domain.campaign_models import _parse_enum
            campaign.state = _parse_enum(CampaignState, data["state"], campaign.state)
            changed.append("state")

        if changed:
            self._add_history(campaign, f"updated campaign fields: {', '.join(changed)}")

        campaign.updated_at = _now()
        self._active_project().touch()
        return Ok(campaign)

    def archive_campaign(self, campaign_id: str) -> Result[Campaign, str]:
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value
        campaign.state = CampaignState.ARCHIVADA
        self._add_history(campaign, "archived campaign")
        campaign.updated_at = _now()
        self._active_project().touch()
        return Ok(campaign)

    def set_state(self, campaign_id: str, state: str) -> Result[Campaign, str]:
        from packages.domain.campaign_models import _parse_enum
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value
        campaign.state = _parse_enum(CampaignState, state, campaign.state)
        self._add_history(campaign, f"set state to {campaign.state.value}")
        campaign.updated_at = _now()
        self._active_project().touch()
        return Ok(campaign)

    # ── Players ────────────────────────────────────────────────────

    def add_player(self, campaign_id: str, player_name: str) -> Result[CampaignPlayer, str]:
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value
        if not player_name or not player_name.strip():
            return Error("Player name is required")

        player = CampaignPlayer(name=player_name.strip())
        campaign.players.append(player)
        self._add_history(campaign, f"added player '{player.name}' ({player.id})")
        campaign.updated_at = _now()
        self._active_project().touch()
        return Ok(player)

    def remove_player(self, campaign_id: str, player_id: str) -> Result[Campaign, str]:
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value

        # Check if player has assigned PCs
        proj = self._active_project()
        assigned = [
            p for p in proj.player_character_profiles
            if p.player_id == player_id
        ]
        if assigned:
            return Error(
                f"Player '{player_id}' has {len(assigned)} assigned player character(s). "
                f"Unassign or archive profiles first."
            )

        for i, p in enumerate(campaign.players):
            if p.id == player_id:
                removed = campaign.players.pop(i)
                self._add_history(campaign, f"removed player '{removed.name}' ({player_id})")
                campaign.updated_at = _now()
                self._active_project().touch()
                return Ok(campaign)

        return Error(f"Player '{player_id}' not found in campaign '{campaign_id}'")

    # ── Player Characters ──────────────────────────────────────────

    def assign_player_character(
        self, campaign_id: str, player_id: str, entity_id: str
    ) -> Result[PlayerCharacterProfile, str]:
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value

        # Validate player_id exists in campaign
        player = None
        for p in campaign.players:
            if p.id == player_id:
                player = p
                break
        if player is None:
            return Error(f"Player '{player_id}' not found in campaign '{campaign_id}'")

        # Validate entity exists
        if self.entity_service is not None:
            entity_result = self.entity_service.get_by_id(entity_id)
            if isinstance(entity_result, Error):
                return Error(f"Entity '{entity_id}' not found")

            # Validate type is PERSONAJE
            entity = entity_result.value
            from packages.domain.entity import EntityType
            if entity.entity_type != EntityType.PERSONAJE:
                return Error(
                    f"Entity '{entity_id}' is type '{entity.entity_type.value}', "
                    f"expected 'personaje'"
                )

        proj = self._active_project()

        # Check if profile already exists for this entity
        for existing in proj.player_character_profiles:
            if existing.entity_id == entity_id:
                return Error(
                    f"Entity '{entity_id}' already has a PlayerCharacterProfile "
                    f"(profile '{existing.id}')"
                )

        profile = PlayerCharacterProfile(
            entity_id=entity_id,
            player_id=player_id,
        )
        proj.player_character_profiles.append(profile)
        campaign.player_character_entity_ids.append(entity_id)

        entity_name = entity_id
        if self.entity_service is not None:
            ent_result = self.entity_service.get_by_id(entity_id)
            if isinstance(ent_result, Ok):
                entity_name = ent_result.value.name

        self._add_history(
            campaign,
            f"assigned PC {entity_name} ({entity_id}) to player {player.name} ({player_id})"
        )
        campaign.updated_at = _now()
        proj.touch()
        return Ok(profile)

    def get_player_character_profile(self, profile_id: str) -> Result[PlayerCharacterProfile, str]:
        proj = self._active_project()
        for p in proj.player_character_profiles:
            if p.id == profile_id:
                return Ok(p)
        return Error(f"PlayerCharacterProfile '{profile_id}' not found")

    def list_player_character_profiles(
        self, campaign_id: str | None = None
    ) -> list[PlayerCharacterProfile]:
        proj = self._active_project()
        profiles = proj.player_character_profiles
        if campaign_id is None:
            return list(profiles)
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return []
        campaign = result.value
        pc_ids = set(campaign.player_character_entity_ids)
        return [
            p for p in profiles
            if p.entity_id in pc_ids
        ]

    def update_player_character_profile(
        self, profile_id: str, data: dict
    ) -> Result[PlayerCharacterProfile, str]:
        proj = self._active_project()
        for i, p in enumerate(proj.player_character_profiles):
            if p.id == profile_id:
                updatable = (
                    "objectives", "backstory", "current_state",
                    "secret_ids", "known_entity_ids", "known_secret_ids",
                    "known_clue_ids", "unknown_entity_ids", "unknown_secret_ids",
                    "unknown_clue_ids", "personal_arc_ids", "debt_ids",
                    "promise_ids", "conflict_ids", "session_ids",
                )
                for field in updatable:
                    if field in data:
                        setattr(p, field, data[field])
                if "metadata" in data and isinstance(data["metadata"], dict):
                    p.metadata.update(data["metadata"])
                p.updated_at = _now()
                proj.touch()
                return Ok(p)
        return Error(f"PlayerCharacterProfile '{profile_id}' not found")

    # ── Entity linking ─────────────────────────────────────────────

    _ROLE_LISTS = {
        "plot": "active_plot_entity_ids",
        "faction": "active_faction_entity_ids",
        "location": "active_location_entity_ids",
        "secret": "secret_entity_ids",
        "clue": "clue_entity_ids",
        "other": "active_plot_entity_ids",  # same bucket as plot
    }

    def link_entity_to_campaign(
        self, campaign_id: str, entity_id: str, role: str
    ) -> Result[Campaign, str]:
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value

        if role not in self._ROLE_LISTS:
            return Error(
                f"Invalid role '{role}'. Valid: plot, faction, location, secret, clue, other"
            )

        # Validate entity exists
        if self.entity_service is not None:
            ent_result = self.entity_service.get_by_id(entity_id)
            if isinstance(ent_result, Error):
                return Error(f"Entity '{entity_id}' not found")

            # Validate entity type for role
            entity = ent_result.value
            from packages.domain.entity import EntityType
            type_map = {
                "plot": (EntityType.TRAMA, EntityType.CONFLICTO, EntityType.EVENTO),
                "faction": (EntityType.FACCION,),
                "location": (EntityType.LOCALIZACION,),
                "secret": (EntityType.SECRETO,),
                "clue": (EntityType.PISTA,),
                "other": (),  # no type restriction
            }
            allowed = type_map.get(role, ())
            if allowed and entity.entity_type not in allowed:
                allowed_str = ", ".join(t.value for t in allowed)
                return Error(
                    f"Entity '{entity_id}' is type '{entity.entity_type.value}'. "
                    f"Role '{role}' requires one of: {allowed_str}"
                )

        list_attr = self._ROLE_LISTS[role]
        current_list = getattr(campaign, list_attr)
        if entity_id not in current_list:
            current_list.append(entity_id)
            setattr(campaign, list_attr, current_list)

        entity_name = entity_id
        if self.entity_service is not None:
            ent2 = self.entity_service.get_by_id(entity_id)
            if isinstance(ent2, Ok):
                entity_name = ent2.value.name

        self._add_history(
            campaign, f"linked {entity_name} ({entity_id}) as {role}"
        )
        campaign.updated_at = _now()
        self._active_project().touch()
        return Ok(campaign)

    def unlink_entity_from_campaign(
        self, campaign_id: str, entity_id: str, role: str
    ) -> Result[Campaign, str]:
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value

        if role not in self._ROLE_LISTS:
            return Error(
                f"Invalid role '{role}'. Valid: plot, faction, location, secret, clue, other"
            )

        list_attr = self._ROLE_LISTS[role]
        current_list = getattr(campaign, list_attr)
        if entity_id in current_list:
            current_list.remove(entity_id)
            setattr(campaign, list_attr, current_list)

        self._add_history(
            campaign, f"unlinked {entity_id} from {role}"
        )
        campaign.updated_at = _now()
        self._active_project().touch()
        return Ok(campaign)

    # ── Clocks ─────────────────────────────────────────────────────

    def create_clock(self, campaign_id: str, data: dict) -> Result[CampaignClock, str]:
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value

        max_value = data.get("max_value", 4)
        if isinstance(max_value, (int, float)) and max_value <= 0:
            return Error("Clock max_value must be > 0")

        clock = CampaignClock(
            name=data.get("name", ""),
            description=data.get("description", ""),
            max_value=int(max_value) if isinstance(max_value, (int, float)) else 4,
        )
        if not clock.name:
            return Error("Clock name is required")

        proj = self._active_project()
        proj.campaign_clocks.append(clock)
        campaign.clock_ids.append(clock.id)

        self._add_history(
            campaign,
            f"created clock '{clock.name}' (max={clock.max_value})"
        )
        campaign.updated_at = _now()
        proj.touch()
        return Ok(clock)

    def advance_clock(self, clock_id: str, by: int = 1) -> Result[CampaignClock, str]:
        proj = self._active_project()

        # Find the clock
        clock = None
        for c in proj.campaign_clocks:
            if c.id == clock_id:
                clock = c
                break
        if clock is None:
            return Error(f"CampaignClock '{clock_id}' not found")

        if by <= 0:
            return Error("Advance amount must be positive")

        remaining = clock.max_value - clock.current_value
        if by > remaining:
            return Error(
                f"Clock advance exceeds max_value: current={clock.current_value}, "
                f"max={clock.max_value}, requested +{by} > remaining {remaining}"
            )

        clock.current_value += by
        if clock.current_value >= clock.max_value:
            clock.state = CampaignClockState.completed

        # Find the campaign that owns this clock and add history
        for camp in proj.campaigns:
            if clock_id in camp.clock_ids:
                self._add_history(
                    camp,
                    f"advanced clock '{clock.name}' by {by} (now {clock.current_value}/{clock.max_value})"
                )
                break

        clock.updated_at = _now()
        proj.touch()
        return Ok(clock)

    def get_clock(self, clock_id: str) -> Result[CampaignClock, str]:
        proj = self._active_project()
        for c in proj.campaign_clocks:
            if c.id == clock_id:
                return Ok(c)
        return Error(f"CampaignClock '{clock_id}' not found")

    def list_clocks(self, campaign_id: str | None = None) -> list[CampaignClock]:
        proj = self._active_project()
        if campaign_id is None:
            return list(proj.campaign_clocks)
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return []
        campaign = result.value
        clock_set = set(campaign.clock_ids)
        return [c for c in proj.campaign_clocks if c.id in clock_set]

    # ── Overview ───────────────────────────────────────────────────

    def get_campaign_overview(self, campaign_id: str) -> Result[dict, str]:
        result = self.get_campaign(campaign_id)
        if isinstance(result, Error):
            return result
        campaign = result.value

        overview: dict[str, Any] = {
            "campaign": campaign.to_dict(),
        }

        # Resolve names via EntityService
        if self.entity_service is not None:
            es = self.entity_service
            # World
            if campaign.world_entity_id:
                wr = es.get_by_id(campaign.world_entity_id)
                if isinstance(wr, Ok):
                    overview["world_name"] = wr.value.name

            # Player characters
            pcs = []
            for eid in campaign.player_character_entity_ids:
                er = es.get_by_id(eid)
                name = er.value.name if isinstance(er, Ok) else eid
                # Find profile
                profile_id = None
                player_name = None
                for p in self._active_project().player_character_profiles:
                    if p.entity_id == eid:
                        profile_id = p.id
                        # Find player name
                        for pl in campaign.players:
                            if pl.id == p.player_id:
                                player_name = pl.name
                                break
                        break
                pcs.append({
                    "entity_id": eid,
                    "entity_name": name,
                    "profile_id": profile_id,
                    "player_name": player_name,
                })
            overview["player_characters"] = pcs

            # Active factions
            factions = []
            for fid in campaign.active_faction_entity_ids:
                fr = es.get_by_id(fid)
                factions.append({
                    "id": fid,
                    "name": fr.value.name if isinstance(fr, Ok) else fid,
                })
            overview["active_factions"] = factions

            # Active locations
            locations = []
            for lid in campaign.active_location_entity_ids:
                lr = es.get_by_id(lid)
                locations.append({
                    "id": lid,
                    "name": lr.value.name if isinstance(lr, Ok) else lid,
                })
            overview["active_locations"] = locations

        # Players
        overview["players"] = [
            {"id": p.id, "name": p.name} for p in campaign.players
        ]

        # Clocks
        proj = self._active_project()
        clocks = []
        for cid in campaign.clock_ids:
            for c in proj.campaign_clocks:
                if c.id == cid:
                    clocks.append({
                        "id": c.id,
                        "name": c.name,
                        "current": c.current_value,
                        "max": c.max_value,
                        "state": c.state.value,
                    })
                    break
        overview["clocks"] = clocks

        return Ok(overview)
