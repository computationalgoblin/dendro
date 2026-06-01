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

# ── Live mode commands (B24-T02) ──

def _get_live_svc(pp):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(pp)
    try:
        from packages.application.campaign_service import CampaignService
        cs = CampaignService(project_service=ps, entity_service=es)
    except: cs = None
    from packages.application.live_mode_service import LiveModeService
    from packages.application.session_service import SessionService
    from packages.application.secrets_service import SecretsService
    ssvc = SessionService(project_service=ps, entity_service=es, campaign_service=cs)
    sec = SecretsService(project_service=ps, entity_service=es)
    lsvc = LiveModeService(project_service=ps, session_service=ssvc, secrets_service=sec, entity_service=es)
    return ps, lsvc

def register_live_commands(subparsers):
    sp = subparsers.add_parser("session", help="Session management")
    ss = sp.add_subparsers(dest="session_command")
    lp = ss.add_parser("live", help="Live mode commands")
    ls = lp.add_subparsers(dest="live_command")

    p = ls.add_parser("open"); p.add_argument("session_id")
    for q in ("npcs","locations","secrets","clues","factions","clocks"):
        p = ls.add_parser(q); p.add_argument("session_id"); p.add_argument("--json", action="store_true")
    p = ls.add_parser("note"); p.add_argument("session_id"); p.add_argument("text")
    p = ls.add_parser("entity"); p.add_argument("session_id"); p.add_argument("name"); p.add_argument("--type", required=True); p.add_argument("--force-canon", action="store_true")
    p = ls.add_parser("relation"); p.add_argument("session_id"); p.add_argument("source_id"); p.add_argument("target_id"); p.add_argument("--type", required=True)
    p = ls.add_parser("clue-deliver"); p.add_argument("session_id"); p.add_argument("clue_id"); p.add_argument("--state", default="entregada", choices=["entregada","perdida","ignorada","malinterpretada"])
    p = ls.add_parser("secret-reveal"); p.add_argument("session_id"); p.add_argument("secret_id"); p.add_argument("--state", default="parcialmente_revelado", choices=["rumoreado","parcialmente_revelado","revelado","malinterpretado"])
    p = ls.add_parser("decide"); p.add_argument("session_id"); p.add_argument("text")
    p = ls.add_parser("event"); p.add_argument("session_id"); p.add_argument("text")
    p = ls.add_parser("consequence"); p.add_argument("session_id"); p.add_argument("text")
    p = ls.add_parser("improvise"); p.add_argument("session_id"); p.add_argument("--hint", default=""); p.add_argument("--save", action="store_true"); p.add_argument("--json", action="store_true")
    p = ls.add_parser("check"); p.add_argument("session_id"); p.add_argument("--json", action="store_true")
    p = ls.add_parser("done"); p.add_argument("session_id"); p.add_argument("--json", action="store_true")

def handle_live(args, session):
    pp = require_project_path(args, session); ps, lsvc = _get_live_svc(pp)
    def _ok(r):
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    cmd = getattr(args, "live_command", None)
    if cmd == "open":
        s = _ok(lsvc.activate_session(args.session_id))
        print(f"Session '{s.name}' activated for live mode")
    elif cmd in ("npcs","locations","secrets","clues","factions","clocks"):
        method = getattr(lsvc, f"query_{cmd}")
        items = method(args.session_id)
        if args.json:
            import json
            data = [{"id": getattr(it, "id", str(it)), "name": getattr(it, "name", ""), "type": getattr(it, "entity_type", type(it).__name__).value if hasattr(getattr(it, "entity_type", None), "value") else str(getattr(it, "entity_type", ""))} for it in items]
            print(json.dumps({"total": len(items), cmd: data}, indent=2, default=str))
        else:
            for it in items: print(f"  {getattr(it, 'id', '?')}: {getattr(it, 'name', str(it))}")
    elif cmd == "note":
        _ok(lsvc.quick_note(args.session_id, args.text))
        print("Note added")
    elif cmd == "entity":
        e = _ok(lsvc.create_provisional_entity(args.session_id, args.name, args.type, force_canon=args.force_canon))
        if args.force_canon: print(f"Created CANONICAL entity '{e.name}' ({e.id}) — bypasses post-session review")
        else: print(f"Created provisional entity '{e.name}' ({e.id}) — borrador")
    elif cmd == "relation":
        r = _ok(lsvc.create_provisional_relation(args.session_id, args.source_id, args.target_id, args.type))
        print(f"Created provisional relation ({r.id}) — borrador")
    elif cmd == "clue-deliver":
        _ok(lsvc.mark_clue_delivered(args.session_id, args.clue_id, state=args.state))
        print(f"Clue '{args.clue_id}' delivered ({args.state})")
    elif cmd == "secret-reveal":
        _ok(lsvc.mark_secret_revealed(args.session_id, args.secret_id, state=args.state))
        print(f"Secret '{args.secret_id}' revealed ({args.state})")
    elif cmd == "decide":
        _ok(lsvc.register_player_decision(args.session_id, args.text)); print("Decision registered")
    elif cmd == "event":
        _ok(lsvc.register_event(args.session_id, args.text)); print("Event registered")
    elif cmd == "consequence":
        _ok(lsvc.register_consequence(args.session_id, args.text)); print("Consequence registered")
    elif cmd == "improvise":
        result = _ok(lsvc.improvise(args.session_id, args.hint, save=args.save))
        if args.json: print(json.dumps(result, indent=2))
        else: print(f"Name: {result['name']}\nDescription: {result['description']}\nComplication: {result['complication']}\nConsequence: {result['consequence']}")
    elif cmd == "check":
        c = _ok(lsvc.check_continuity(args.session_id))
        if args.json: print(json.dumps(c, indent=2, default=str))
        else: print(f"Pending clues: {c.get('pendientes_pistas','?')}\nHidden secrets: {c.get('secretos_ocultos','?')}\nActive clocks: {c.get('relojes_activos','?')}")
    elif cmd == "done":
        data = _ok(lsvc.prepare_post_session(args.session_id))
        if args.json: print(json.dumps(data, indent=2))
        else: print(f"Live session material prepared for post-session review.\nQuick notes: {len(data.get('quick_notes',[]))}\nDecisions: {len(data.get('player_decisions',[]))}\nEvents: {len(data.get('events',[]))}\nClues delivered: {len(data.get('clues_delivered',[]))}\nSecrets revealed: {len(data.get('secrets_revealed',[]))}\nProvisional entities: {len(data.get('provisional_entity_ids',[]))}\nRelations: {len(data.get('provisional_relation_ids',[]))}\nSession state remains activa.")

# ── Post-session commands (B25-T03) ──

def _get_post_svc(pp):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(pp)
    from packages.application.post_session_service import PostSessionService
    from packages.application.session_service import SessionService
    svc = PostSessionService(project_service=ps, session_service=ss, history_service=hs, entity_service=es)
    return ps, svc

def register_post_commands(subparsers):
    sp = subparsers.add_parser("session", help="Session management")
    ss = sp.add_subparsers(dest="session_command")
    p = ss.add_parser("close", help="Close session (post-session)"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("post-summary", help="Post-session summary"); p.add_argument("id"); p.add_argument("--player", action="store_true"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("post-candidates", help="Convert live to candidates"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("post-accept", help="Accept post-session candidate"); p.add_argument("candidate_id")
    p = ss.add_parser("post-reject", help="Reject post-session candidate"); p.add_argument("candidate_id")
    p = ss.add_parser("post-source", help="Create session source"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("post-seeds", help="Next session seeds"); p.add_argument("id"); p.add_argument("--json", action="store_true")

def handle_post(args, session):
    pp = require_project_path(args, session); ps, svc = _get_post_svc(pp)
    def _ok(r):
        from packages.domain.result import Error
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    def _save(): ps.save(Path(pp))
    cmd = getattr(args, "session_command", None)
    if cmd == "close":
        s = _ok(svc.close_session(args.id)); _save()
        print(json.dumps({"state": s.state.value, "post_session_summary": s.post_session_summary}) if args.json else f"Session '{s.name}' closed. State: {s.state.value}")
    elif cmd == "post-summary":
        s = _ok(svc.generate_player_summary(args.id) if args.player else svc.generate_private_summary(args.id))
        print(json.dumps({"summary": s}) if args.json else s)
    elif cmd == "post-candidates":
        cands = _ok(svc.convert_live_to_candidates(args.id)); _save()
        if args.json: print(json.dumps({"total": len(cands), "candidates": [{"title": c.title, "id": c.id, "type": c.candidate_type.value} for c in cands]}, indent=2))
        else: print(f"Generated {len(cands)} candidate(s)"); [print(f"  {c.id}: {c.title}") for c in cands]
    elif cmd == "post-accept":
        svc.candidate_service.accept_candidate(args.candidate_id); _save(); print(f"Candidate '{args.candidate_id}' accepted")
    elif cmd == "post-reject":
        svc.candidate_service.reject_candidate(args.candidate_id); _save(); print(f"Candidate '{args.candidate_id}' rejected")
    elif cmd == "post-source":
        src = _ok(svc.create_session_source(args.id))
        print(json.dumps({"id": src.id, "title": src.title}) if args.json else f"Source: {src.title} ({src.id})")
    elif cmd == "post-seeds":
        seeds = svc.generate_next_session_seeds(args.id)
        print(json.dumps({"seeds": seeds}) if args.json else "\n".join(f"  - {s}" for s in seeds))
