"""CLI campaign commands — create, list, show, edit, archive, link, player, pc, clock, overview (B20-T04)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from packages.application.campaign_service import CampaignService
from packages.domain.result import Error
from packages.ui.cli import _bootstrap_services, require_project_path


def _get_svc(project_path: str):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    cs = CampaignService(project_service=ps, entity_service=es)
    return ps, cs, es


def register_campaign_commands(subparsers: Any) -> None:
    cp = subparsers.add_parser("campaign", help="Campaign management")
    cs = cp.add_subparsers(dest="campaign_command", required=True)

    # campaign create
    p = cs.add_parser("create", help="Create a campaign")
    p.add_argument("name")
    p.add_argument("--world")
    p.add_argument("--system")
    p.add_argument("--tone")
    p.add_argument("--genre")
    p.add_argument("--description", default="")

    # campaign list
    p = cs.add_parser("list", help="List campaigns")
    p.add_argument("--json", action="store_true")
    p.add_argument("--include-archived", action="store_true")

    # campaign show
    p = cs.add_parser("show", help="Show campaign details")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")

    # campaign edit
    p = cs.add_parser("edit", help="Edit campaign")
    p.add_argument("id")
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--system")
    p.add_argument("--tone")
    p.add_argument("--genre")
    p.add_argument("--state")

    # campaign archive
    p = cs.add_parser("archive", help="Archive a campaign")
    p.add_argument("id")

    # campaign link
    p = cs.add_parser("link", help="Link entity to campaign")
    p.add_argument("campaign_id")
    p.add_argument("entity_id")
    p.add_argument("--role", required=True, choices=["plot", "faction", "location", "secret", "clue", "other"])

    # campaign unlink
    p = cs.add_parser("unlink", help="Unlink entity from campaign")
    p.add_argument("campaign_id")
    p.add_argument("entity_id")
    p.add_argument("--role", required=True, choices=["plot", "faction", "location", "secret", "clue", "other"])

    # campaign player add
    p = cs.add_parser("player-add", help="Add player to campaign")
    p.add_argument("campaign_id")
    p.add_argument("name")

    # campaign player remove
    p = cs.add_parser("player-remove", help="Remove player from campaign")
    p.add_argument("campaign_id")
    p.add_argument("player_id")

    # campaign pc assign
    p = cs.add_parser("pc-assign", help="Assign player character")
    p.add_argument("campaign_id")
    p.add_argument("player_id")
    p.add_argument("entity_id")

    # campaign pc show
    p = cs.add_parser("pc-show", help="Show player character profile")
    p.add_argument("profile_id")
    p.add_argument("--json", action="store_true")

    # campaign pc edit
    p = cs.add_parser("pc-edit", help="Edit player character profile")
    p.add_argument("profile_id")
    p.add_argument("--objectives", nargs="*")
    p.add_argument("--backstory")
    p.add_argument("--current-state")

    # campaign pc list
    p = cs.add_parser("pc-list", help="List player character profiles")
    p.add_argument("--campaign")
    p.add_argument("--json", action="store_true")

    # campaign clock create
    p = cs.add_parser("clock-create", help="Create campaign clock")
    p.add_argument("campaign_id")
    p.add_argument("name")
    p.add_argument("--max", type=int, default=4)
    p.add_argument("--description", default="")

    # campaign clock advance
    p = cs.add_parser("clock-advance", help="Advance campaign clock")
    p.add_argument("clock_id")
    p.add_argument("--by", type=int, default=1)

    # campaign clock show
    p = cs.add_parser("clock-show", help="Show campaign clock")
    p.add_argument("clock_id")
    p.add_argument("--json", action="store_true")

    # campaign clock list
    p = cs.add_parser("clock-list", help="List campaign clocks")
    p.add_argument("--campaign")
    p.add_argument("--json", action="store_true")

    # campaign overview
    p = cs.add_parser("overview", help="Show campaign overview")
    p.add_argument("campaign_id")
    p.add_argument("--json", action="store_true")


def handle_campaign(args: Any, session) -> None:
    project_path = require_project_path(args, session)
    ps, cs, es = _get_svc(project_path)
    cmd = args.campaign_command

    def _ok(result):
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr)
            sys.exit(1)
        return result.value

    def _save():
        r = ps.save(Path(project_path))
        if isinstance(r, Error):
            print(f"error: save failed: {r.error}", file=sys.stderr)
            sys.exit(1)

    # ── CRUD ──
    if cmd == "create":
        data = {"name": args.name}
        if args.world: data["world_entity_id"] = args.world
        if args.system: data["game_system"] = args.system
        if args.tone: data["tone"] = args.tone
        if args.genre: data["genre"] = args.genre
        if args.description: data["description"] = args.description
        c = _ok(cs.create_campaign(data))
        _save()
        print(f"Campaign '{c.name}' ({c.id}) created")

    elif cmd == "list":
        campaigns = cs.list_campaigns(include_archived=args.include_archived)
        if args.json:
            print(json.dumps({"total": len(campaigns), "campaigns": [c.to_dict() for c in campaigns]}, indent=2))
        else:
            for c in campaigns:
                state = c.state.value
                players = f"{len(c.players)} player(s)"
                print(f"  {c.id}  {c.name:<30}  {state:<12}  {c.game_system:<15}  {players}")

    elif cmd == "show":
        c = _ok(cs.get_campaign(args.id))
        if args.json:
            print(json.dumps(c.to_dict(), indent=2))
        else:
            print(f"  ID:           {c.id}")
            print(f"  Name:         {c.name}")
            print(f"  Description:  {c.description}")
            print(f"  World:        {c.world_entity_id or '(none)'}")
            print(f"  System:       {c.game_system or '(none)'}")
            print(f"  Tone:         {c.tone or '(none)'}")
            print(f"  Genre:        {c.genre or '(none)'}")
            print(f"  State:        {c.state.value}")
            print(f"  Players:      {len(c.players)}")
            for p in c.players:
                print(f"    - {p.name} ({p.id})")
            print(f"  PCs:          {len(c.player_character_entity_ids)}")
            print(f"  Factions:     {len(c.active_faction_entity_ids)}")
            print(f"  Locations:    {len(c.active_location_entity_ids)}")
            print(f"  Secrets:      {len(c.secret_entity_ids)}")
            print(f"  Clues:        {len(c.clue_entity_ids)}")
            print(f"  Clocks:       {len(c.clock_ids)}")

    elif cmd == "edit":
        data = {}
        for field in ("name", "description", "game_system", "tone", "genre", "state"):
            val = getattr(args, field, None) or getattr(args, "system" if field == "game_system" else field, None)
            key = "game_system" if field == "system" else field
            if val:
                data[field] = val
        if not data:
            print("error: no fields to update", file=sys.stderr)
            sys.exit(1)
        c = _ok(cs.update_campaign(args.id, data))
        _save()
        print(f"Campaign '{c.name}' updated")

    elif cmd == "archive":
        c = _ok(cs.archive_campaign(args.id))
        _save()
        print(f"Campaign '{c.name}' archived")

    # ── Linking ──
    elif cmd == "link":
        c = _ok(cs.link_entity_to_campaign(args.campaign_id, args.entity_id, args.role))
        _save()
        print(f"Entity {args.entity_id} linked to campaign {args.campaign_id} as {args.role}")

    elif cmd == "unlink":
        c = _ok(cs.unlink_entity_from_campaign(args.campaign_id, args.entity_id, args.role))
        _save()
        print(f"Entity {args.entity_id} unlinked from campaign {args.campaign_id} ({args.role})")

    # ── Players ──
    elif cmd == "player-add":
        player = _ok(cs.add_player(args.campaign_id, args.name))
        _save()
        print(f"Player '{player.name}' ({player.id}) added to campaign {args.campaign_id}")

    elif cmd == "player-remove":
        c = _ok(cs.remove_player(args.campaign_id, args.player_id))
        _save()
        print(f"Player '{args.player_id}' removed from campaign {args.campaign_id}")

    # ── Player Characters ──
    elif cmd == "pc-assign":
        profile = _ok(cs.assign_player_character(args.campaign_id, args.player_id, args.entity_id))
        _save()
        print(f"PlayerCharacterProfile ({profile.id}) created: entity {args.entity_id} assigned to player {args.player_id}")

    elif cmd == "pc-show":
        profile = _ok(cs.get_player_character_profile(args.profile_id))
        if args.json:
            print(json.dumps(profile.to_dict(), indent=2))
        else:
            print(f"  Profile ID:   {profile.id}")
            print(f"  Entity ID:    {profile.entity_id}")
            print(f"  Player ID:    {profile.player_id}")
            print(f"  Backstory:    {profile.backstory or '(none)'}")
            print(f"  Current:      {profile.current_state or '(none)'}")
            print(f"  Objectives:   {profile.objectives}")

    elif cmd == "pc-edit":
        data = {}
        if args.objectives is not None:
            data["objectives"] = args.objectives
        if args.backstory is not None:
            data["backstory"] = args.backstory
        if hasattr(args, "current_state") and args.current_state is not None:
            data["current_state"] = args.current_state
        if not data:
            print("error: no fields to update", file=sys.stderr)
            sys.exit(1)
        profile = _ok(cs.update_player_character_profile(args.profile_id, data))
        _save()
        print(f"PlayerCharacterProfile '{profile.id}' updated")

    elif cmd == "pc-list":
        profiles = cs.list_player_character_profiles(campaign_id=args.campaign)
        if args.json:
            print(json.dumps({"total": len(profiles), "profiles": [p.to_dict() for p in profiles]}, indent=2))
        else:
            for p in profiles:
                print(f"  {p.id}  entity={p.entity_id}  player={p.player_id}  state={p.current_state or '(none)'}")

    # ── Clocks ──
    elif cmd == "clock-create":
        data = {"name": args.name, "max_value": args.max}
        if args.description:
            data["description"] = args.description
        clock = _ok(cs.create_clock(args.campaign_id, data))
        _save()
        print(f"Clock '{clock.name}' ({clock.id}) created [{clock.current_value}/{clock.max_value}]")

    elif cmd == "clock-advance":
        clock = _ok(cs.advance_clock(args.clock_id, by=args.by))
        _save()
        print(f"Clock '{clock.name}' advanced to {clock.current_value}/{clock.max_value} ({clock.state.value})")

    elif cmd == "clock-show":
        clock = _ok(cs.get_clock(args.clock_id))
        if args.json:
            print(json.dumps(clock.to_dict(), indent=2))
        else:
            print(f"  ID:          {clock.id}")
            print(f"  Name:        {clock.name}")
            print(f"  Description: {clock.description or '(none)'}")
            print(f"  Progress:    {clock.current_value}/{clock.max_value}")
            print(f"  State:       {clock.state.value}")

    elif cmd == "clock-list":
        clocks = cs.list_clocks(campaign_id=args.campaign)
        if args.json:
            print(json.dumps({"total": len(clocks), "clocks": [c.to_dict() for c in clocks]}, indent=2))
        else:
            for c in clocks:
                print(f"  {c.id}  {c.name:<25}  {c.current_value}/{c.max_value}  {c.state.value}")

    # ── Overview ──
    elif cmd == "overview":
        overview = _ok(cs.get_campaign_overview(args.campaign_id))
        if args.json:
            print(json.dumps(overview, indent=2, default=str))
        else:
            camp = overview["campaign"]
            print(f"Campaign: {camp['name']} ({camp['id']})")
            print(f"  State:    {camp['state']}")
            print(f"  System:   {camp.get('game_system', '(none)')}")
            world = overview.get("world_name")
            if world:
                print(f"  World:    {world}")
            print(f"  Players:  {len(overview.get('players', []))}")
            for pl in overview.get("players", []):
                print(f"    - {pl['name']} ({pl['id']})")
            print(f"  PCs:      {len(overview.get('player_characters', []))}")
            for pc in overview.get("player_characters", []):
                print(f"    - {pc.get('entity_name', pc['entity_id'])} (player: {pc.get('player_name', '?')})")
            print(f"  Factions: {len(overview.get('active_factions', []))}")
            for f in overview.get("active_factions", []):
                print(f"    - {f['name']} ({f['id']})")
            print(f"  Clocks:   {len(overview.get('clocks', []))}")
            for c in overview.get("clocks", []):
                print(f"    - {c['name']} ({c['current']}/{c['max']} {c['state']})")
