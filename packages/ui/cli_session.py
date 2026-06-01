"""CLI session commands — B23-T04."""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
from packages.application.session_service import SessionService
from packages.domain.result import Error
from packages.ui.cli import _bootstrap_services, require_project_path

def _get_svc(pp):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(pp)
    try:
        from packages.application.campaign_service import CampaignService
        cs = CampaignService(project_service=ps, entity_service=es)
    except: cs = None
    svc = SessionService(project_service=ps, entity_service=es, campaign_service=cs)
    return ps, svc, es

def register_session_commands(subparsers):
    sp = subparsers.add_parser("session", help="Session management")
    ss = sp.add_subparsers(dest="session_command")
    p = ss.add_parser("create"); p.add_argument("name"); p.add_argument("--campaign", required=True); p.add_argument("--number", type=int, default=0); p.add_argument("--real-date"); p.add_argument("--internal-date"); p.add_argument("--entity")
    ss.add_parser("list", help="List sessions").add_argument("--campaign"); p = ss.add_parser("list"); p.add_argument("--campaign"); p.add_argument("--state"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("show"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("edit"); p.add_argument("id"); p.add_argument("--name"); p.add_argument("--context"); p.add_argument("--state")
    p = ss.add_parser("duplicate"); p.add_argument("id"); p.add_argument("--name")
    p = ss.add_parser("scene", help="Manage scenes"); sc = p.add_subparsers(dest="scene_cmd")
    for cmd in ("add", "remove", "reorder"):
        p2 = sc.add_parser(cmd)
        if cmd == "add": p2.add_argument("session_id"); p2.add_argument("name"); p2.add_argument("--type", choices=["prevista","opcional","improvisada"], default="prevista"); p2.add_argument("--order", type=int, default=0); p2.add_argument("--location"); p2.add_argument("--npcs"); p2.add_argument("--notes"); p2.add_argument("--target", choices=["planned","optional"], default="planned")
        elif cmd == "remove": p2.add_argument("session_id"); p2.add_argument("scene_id"); p2.add_argument("--target", choices=["planned","optional"], default="planned")
        elif cmd == "reorder": p2.add_argument("session_id"); p2.add_argument("scene_id"); p2.add_argument("new_order", type=int); p2.add_argument("--target", choices=["planned","optional"], default="planned")
    p = ss.add_parser("link", help="Link to session"); lk = p.add_subparsers(dest="link_cmd")
    for t in ("clue","secret","faction","clock"): p2 = lk.add_parser(t); p2.add_argument("session_id"); p2.add_argument(f"{t}_id")
    p2 = lk.add_parser("entity"); p2.add_argument("session_id"); p2.add_argument("entity_id"); p2.add_argument("--role", choices=["location","npc","conflict"], required=True)
    p = ss.add_parser("summary"); p.add_argument("id"); p.add_argument("--player", action="store_true"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("check"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("suggest"); p.add_argument("id"); p.add_argument("--hint", default=""); p.add_argument("--audience", default="author")
    p = ss.add_parser("issues"); p.add_argument("id"); p.add_argument("--json", action="store_true")

def handle_session(args, session):
    pp = require_project_path(args, session); ps, svc, es = _get_svc(pp)
    def _ok(r):
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    def _save(): ps.save(Path(pp))
    cmd = getattr(args, "session_command", None)
    if cmd == "create":
        data = {"name": args.name, "campaign_id": args.campaign, "session_number": args.number}
        if args.real_date: data["real_date"] = args.real_date
        if args.internal_date: data["internal_date"] = args.internal_date
        if hasattr(args, "entity") and args.entity: data["entity_id"] = args.entity
        s = _ok(svc.create_session(data)); _save(); print(f"Session '{s.name}' ({s.id}) created")
    elif cmd == "list":
        sessions = svc.list_sessions(campaign_id=args.campaign, state=args.state)
        if args.json: print(json.dumps({"total": len(sessions), "sessions": [s.to_dict() for s in sessions]}, indent=2))
        else:
            for s in sessions: print(f"  {s.id}  {s.name:<25}  {s.state.value:<14}  #{s.session_number}")
    elif cmd == "show":
        s = _ok(svc.get_session(args.id))
        print(json.dumps(s.to_dict(), indent=2) if args.json else f"ID: {s.id}\nName: {s.name}\nCampaign: {s.campaign_id}\nState: {s.state.value}\nScenes: {len(s.planned_scenes)} planned + {len(s.optional_scenes)} optional")
    elif cmd == "edit":
        data = {}; 
        for f in ("name", "context_summary", "state"): 
            val = getattr(args, f, None) or (getattr(args, "context", None) if f == "context_summary" else None)
            if val: data[f] = val
        s = _ok(svc.update_session(args.id, data)); _save(); print(f"Session updated")
    elif cmd == "duplicate":
        s = _ok(svc.duplicate_session(args.id, new_name=args.name)); _save(); print(f"Duplicated: {s.name} ({s.id})")
    elif hasattr(args, "scene_cmd") and args.scene_cmd:
        target = getattr(args, "target", "planned")
        if args.scene_cmd == "add":
            data = {"name": args.name, "scene_type": getattr(args, "type", "prevista"), "order": args.order}
            if args.location: data["location_id"] = args.location
            if args.npcs: data["npc_ids"] = [n.strip() for n in args.npcs.split(",")]
            if args.notes: data["notes"] = args.notes
            sc = _ok(svc.add_scene(args.session_id, data, target)); _save(); print(f"Scene '{sc.name}' ({sc.id}) added")
        elif args.scene_cmd == "remove":
            _ok(svc.remove_scene(args.session_id, args.scene_id, target)); _save(); print("Scene removed")
        elif args.scene_cmd == "reorder":
            _ok(svc.reorder_scene(args.session_id, args.scene_id, args.new_order, target)); _save(); print("Scene reordered")
    elif hasattr(args, "link_cmd") and args.link_cmd:
        lc = args.link_cmd
        if lc == "entity": _ok(svc.link_entity(args.session_id, args.entity_id, args.role))
        else:
            eid = getattr(args, f"{lc}_id"); {"clue": svc.link_clue, "secret": svc.link_secret, "faction": svc.link_faction, "clock": svc.link_clock}[lc](args.session_id, eid)
        _save(); print(f"{lc.capitalize()} linked")
    elif cmd == "summary":
        s = _ok(svc.generate_player_summary(args.id) if args.player else svc.generate_private_summary(args.id))
        print(json.dumps({"summary": s}) if args.json else s)
    elif cmd == "check":
        c = _ok(svc.check_continuity(args.id))
        print(json.dumps(c, indent=2) if args.json else f"Pending clues: {c['pendientes_pistas']}\nHidden secrets: {c['secretos_ocultos']}\nActive clocks: {c['relojes_activos']}\nActive factions: {c['facciones_activas']}")
    elif cmd == "suggest":
        c = _ok(svc.suggest_material(args.id, args.hint, args.audience))
        print(f"Candidate '{c.title}' ({c.id}) created")
    elif cmd == "issues":
        issues = svc.get_relevant_issues(args.id)
        print(json.dumps({"total": len(issues), "issues": [i.to_dict() for i in issues]}, indent=2) if args.json else f"Relevant issues: {len(issues)}")
