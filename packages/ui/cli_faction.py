"""CLI faction and front commands — B22-T04."""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
from packages.application.faction_service import FactionService
from packages.domain.result import Error
from packages.ui.cli import _bootstrap_services, require_project_path

def _get_svc(project_path):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    try:
        from packages.application.campaign_service import CampaignService
        cs = CampaignService(project_service=ps, entity_service=es)
    except Exception: cs = None
    fs = FactionService(project_service=ps, entity_service=es, campaign_service=cs)
    return ps, fs, es

def register_faction_commands(subparsers: Any) -> None:
    fp = subparsers.add_parser("faction", help="Faction management")
    fs = fp.add_subparsers(dest="faction_command")
    p = fs.add_parser("create", help="Create faction"); p.add_argument("name"); p.add_argument("--entity", required=True); p.add_argument("--ideology"); p.add_argument("--methods"); p.add_argument("--json", action="store_true")
    p = fs.add_parser("list", help="List factions"); p.add_argument("--state"); p.add_argument("--json", action="store_true")
    p = fs.add_parser("show", help="Show faction"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = fs.add_parser("edit", help="Edit faction"); p.add_argument("id"); p.add_argument("--name"); p.add_argument("--ideology"); p.add_argument("--methods"); p.add_argument("--state")
    p = fs.add_parser("member", help="Manage members"); ms = p.add_subparsers(dest="member_cmd")
    for cmd in ("add", "remove"): p2 = ms.add_parser(cmd); p2.add_argument("faction_id"); p2.add_argument("entity_id")
    p = fs.add_parser("leader", help="Manage leaders"); ls = p.add_subparsers(dest="leader_cmd")
    for cmd in ("add", "remove"): p2 = ls.add_parser(cmd); p2.add_argument("faction_id"); p2.add_argument("entity_id")
    p = fs.add_parser("ally", help="Manage allies"); als = p.add_subparsers(dest="ally_cmd")
    for cmd in ("add", "remove"): p2 = als.add_parser(cmd); p2.add_argument("faction_id"); p2.add_argument("other_id")
    p = fs.add_parser("enemy", help="Manage enemies"); es = p.add_subparsers(dest="enemy_cmd")
    for cmd in ("add", "remove"): p2 = es.add_parser(cmd); p2.add_argument("faction_id"); p2.add_argument("other_id")
    p = fs.add_parser("clock", help="Manage faction clocks"); cs2 = p.add_subparsers(dest="clock_cmd")
    p2 = cs2.add_parser("assign"); p2.add_argument("faction_id"); p2.add_argument("clock_id")
    p2 = cs2.add_parser("unassign"); p2.add_argument("faction_id"); p2.add_argument("clock_id")
    p2 = cs2.add_parser("advance"); p2.add_argument("clock_id"); p2.add_argument("--by", type=int, default=1); p2.add_argument("--reason", default="")
    p = fs.add_parser("overview", help="Faction overview"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = fs.add_parser("detect-issues", help="Detect faction issues"); p.add_argument("--json", action="store_true")

    # front
    frp = subparsers.add_parser("front", help="Front management")
    frs = frp.add_subparsers(dest="front_command")
    p = frs.add_parser("create", help="Create front"); p.add_argument("name"); p.add_argument("--type", dest="front_type", choices=["frente","amenaza","inminente"], default="frente"); p.add_argument("--faction"); p.add_argument("--clock"); p.add_argument("--desc", default="")
    p = frs.add_parser("list", help="List fronts"); p.add_argument("--state"); p.add_argument("--json", action="store_true")
    p = frs.add_parser("show", help="Show front"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = frs.add_parser("edit", help="Edit front"); p.add_argument("id"); p.add_argument("--name"); p.add_argument("--desc"); p.add_argument("--state", choices=["latente","activo","contenido","resuelto"])
    p = frs.add_parser("stage", help="Manage stages"); ss2 = p.add_subparsers(dest="stage_cmd")
    p2 = ss2.add_parser("add"); p2.add_argument("front_id"); p2.add_argument("name"); p2.add_argument("--threshold", type=int, default=0); p2.add_argument("--desc", default=""); p2.add_argument("--terminal", action="store_true")
    p = frs.add_parser("advance", help="Advance front"); p.add_argument("id")
    p = frs.add_parser("retreat", help="Retreat front"); p.add_argument("id")
    p = frs.add_parser("link-clock", help="Link front to clock"); p.add_argument("front_id"); p.add_argument("clock_id")
    p = frs.add_parser("unlink-clock", help="Unlink front from clock"); p.add_argument("front_id")

def handle_faction(args, session):
    pp = require_project_path(args, session); ps, fs, es = _get_svc(pp)
    def _ok(r):
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    def _save(): ps.save(Path(pp))
    cmd = getattr(args, "faction_command", None)
    if cmd == "create":
        data = {"name": args.name, "entity_id": args.entity}
        if args.ideology: data["ideology"] = args.ideology
        if args.methods: data["methods"] = [m.strip() for m in args.methods.split(",")]
        f = _ok(fs.create_faction(data)); _save()
        print(f"Faction '{f.name}' ({f.id}) created")
        if args.json: print(json.dumps(f.to_dict(), indent=2))
    elif cmd == "list":
        factions = fs.list_factions(state=args.state)
        if args.json: print(json.dumps({"total": len(factions), "factions": [f.to_dict() for f in factions]}, indent=2))
        else:
            for f in factions: print(f"  {f.id}  {f.name:<25}  {f.state.value:<12}")
    elif cmd == "show":
        f = _ok(fs.get_faction(args.id))
        if args.json: print(json.dumps(f.to_dict(), indent=2))
        else: print(f"ID: {f.id}\nName: {f.name}\nEntity: {f.entity_id}\nState: {f.state.value}\nMembers: {len(f.member_entity_ids)}\nAllies: {len(f.ally_faction_ids)}\nEnemies: {len(f.enemy_faction_ids)}")
    elif cmd == "edit":
        data = {}
        for field in ("name", "ideology", "methods", "state"):
            val = getattr(args, field, None)
            if val:
                if field == "methods": val = [m.strip() for m in val.split(",")]
                data[field] = val
        f = _ok(fs.update_faction(args.id, data)); _save()
        print(f"Faction '{f.id}' updated")
    elif hasattr(args, "member_cmd") and args.member_cmd:
        if args.member_cmd == "add": f = _ok(fs.add_member(args.faction_id, args.entity_id))
        else: f = _ok(fs.remove_member(args.faction_id, args.entity_id))
        _save(); print(f"Member {args.member_cmd}ed")
    elif hasattr(args, "leader_cmd") and args.leader_cmd:
        if args.leader_cmd == "add": f = _ok(fs.add_leader(args.faction_id, args.entity_id))
        else: f = _ok(fs.remove_leader(args.faction_id, args.entity_id))
        _save(); print(f"Leader {args.leader_cmd}ed")
    elif hasattr(args, "ally_cmd") and args.ally_cmd:
        if args.ally_cmd == "add": f = _ok(fs.add_ally(args.faction_id, args.other_id))
        else: f = _ok(fs.remove_ally(args.faction_id, args.other_id))
        _save(); print(f"Ally {args.ally_cmd}ed")
    elif hasattr(args, "enemy_cmd") and args.enemy_cmd:
        if args.enemy_cmd == "add": f = _ok(fs.add_enemy(args.faction_id, args.other_id))
        else: f = _ok(fs.remove_enemy(args.faction_id, args.other_id))
        _save(); print(f"Enemy {args.enemy_cmd}ed")
    elif hasattr(args, "clock_cmd") and args.clock_cmd:
        if args.clock_cmd == "assign": c = _ok(fs.assign_clock_to_faction(args.clock_id, args.faction_id)); _save(); print(f"Clock '{args.clock_id}' assigned to faction '{args.faction_id}'")
        elif args.clock_cmd == "unassign": c = _ok(fs.unassign_clock_from_faction(args.clock_id, args.faction_id)); _save(); print(f"Clock unassigned")
        elif args.clock_cmd == "advance": c = _ok(fs.advance_faction_clock(args.clock_id, args.by, args.reason)); _save(); print(f"Clock advanced to {c.current_value}/{c.max_value}")
    elif cmd == "overview":
        ov = _ok(fs.get_faction_overview(args.id))
        print(json.dumps(ov, indent=2, default=str) if args.json else f"Faction: {ov['faction']['name']} ({len(ov.get('members',[]))} members, {len(ov.get('leaders',[]))} leaders)")
    elif cmd == "detect-issues":
        issues = fs.run_faction_validation()
        if args.json: print(json.dumps({"total": len(issues), "issues": [i.to_dict() for i in issues]}, indent=2))
        else:
            print(f"Detected {len(issues)} issue(s)")
            for i in issues: print(f"  - [{i.metadata.get('subtype','?')}] {i.description[:80]}")
        if issues: _save()

def handle_front(args, session):
    pp = require_project_path(args, session); ps, fs, es = _get_svc(pp)
    def _ok(r):
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    def _save(): ps.save(Path(pp))
    cmd = getattr(args, "front_command", None)
    if cmd == "create":
        data = {"name": args.name, "front_type": args.front_type, "description": args.desc}
        if args.faction: data["faction_id"] = args.faction
        if args.clock: data["clock_id"] = args.clock
        f = _ok(fs.create_front(data)); _save()
        print(f"Front '{f.name}' ({f.id}) created")
    elif cmd == "list":
        fronts = fs.list_fronts(state=args.state)
        if args.json: print(json.dumps({"total": len(fronts), "fronts": [f.to_dict() for f in fronts]}, indent=2))
        else:
            for f in fronts: print(f"  {f.id}  {f.name:<25}  {f.state.value:<12}  stages={len(f.stages)}")
    elif cmd == "show":
        f = _ok(fs.get_front(args.id))
        if args.json: print(json.dumps(f.to_dict(), indent=2))
        else: print(f"ID: {f.id}\nName: {f.name}\nType: {f.front_type.value}\nState: {f.state.value}\nFaction: {f.faction_id or '(none)'}\nClock: {f.clock_id or '(none)'}\nStages: {len(f.stages)} Stage: {f.current_stage_index}")
    elif cmd == "edit":
        data = {}
        if args.name: data["name"] = args.name
        if args.desc: data["description"] = args.desc
        if args.state: data["state"] = args.state
        f = _ok(fs.update_front(args.id, data)); _save()
        print(f"Front '{f.id}' updated")
    elif hasattr(args, "stage_cmd") and args.stage_cmd == "add":
        f = _ok(fs.add_stage(args.front_id, {"name": args.name, "threshold": args.threshold, "description": args.desc, "is_terminal": args.terminal}))
        _save(); print(f"Stage '{args.name}' added to front '{args.front_id}'")
    elif cmd == "advance":
        f = _ok(fs.advance_front(args.id)); _save()
        print(f"Front '{f.name}' advanced to stage {f.current_stage_index}/{len(f.stages)-1}")
    elif cmd == "retreat":
        f = _ok(fs.retreat_front(args.id)); _save()
        print(f"Front '{f.name}' retreated to stage {f.current_stage_index}/{len(f.stages)-1}")
    elif cmd == "link-clock":
        f = _ok(fs.link_front_to_clock(args.front_id, args.clock_id)); _save()
        print(f"Front '{args.front_id}' linked to clock '{args.clock_id}'")
    elif cmd == "unlink-clock":
        f = _ok(fs.unlink_front_from_clock(args.front_id)); _save()
        print(f"Front '{args.front_id}' unlinked from clock")
