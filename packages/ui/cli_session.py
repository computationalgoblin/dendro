"""CLI session commands — B23-T04 + B24-T02 + B25-T03."""

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

def _get_live_svc(pp):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(pp)
    try:
        from packages.application.campaign_service import CampaignService
        cs = CampaignService(project_service=ps, entity_service=es)
    except: cs = None
    from packages.application.session_service import SessionService
    from packages.application.secrets_service import SecretsService
    from packages.application.live_mode_service import LiveModeService
    ssvc = SessionService(project_service=ps, entity_service=es, campaign_service=cs)
    sec = SecretsService(project_service=ps, entity_service=es)
    lsvc = LiveModeService(project_service=ps, session_service=ssvc, secrets_service=sec, entity_service=es)
    return ps, lsvc

def _get_post_svc(pp):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(pp)
    from packages.application.post_session_service import PostSessionService
    from packages.application.session_service import SessionService
    ssvc = SessionService(project_service=ps, entity_service=es)
    svc = PostSessionService(project_service=ps, session_service=ssvc, history_service=hs, entity_service=es)
    return ps, svc

def register_session_commands(subparsers):
    sp = subparsers.add_parser("session", help="Session management")
    ss = sp.add_subparsers(dest="session_command")
    p = ss.add_parser("create"); p.add_argument("name"); p.add_argument("--campaign", required=True); p.add_argument("--number", type=int, default=0); p.add_argument("--real-date"); p.add_argument("--internal-date"); p.add_argument("--entity")
    p = ss.add_parser("list"); p.add_argument("--campaign"); p.add_argument("--state"); p.add_argument("--json", action="store_true")

    # ── Live commands (B24-T02) ──
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

    # ── Post-session commands (B25-T03) ──
    p = ss.add_parser("close"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("post-summary"); p.add_argument("id"); p.add_argument("--player", action="store_true"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("post-candidates"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("post-accept"); p.add_argument("candidate_id")
    p = ss.add_parser("post-reject"); p.add_argument("candidate_id")
    p = ss.add_parser("post-source"); p.add_argument("id"); p.add_argument("--json", action="store_true")
    p = ss.add_parser("post-seeds"); p.add_argument("id"); p.add_argument("--json", action="store_true")
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


# ── Live mode handler (B24-T02) ──────────────────────────────────────

def _handle_live(args, session):
    pp = require_project_path(args, session)
    ps, lsvc = _get_live_svc(pp)

    def _ok(r):
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    def _save(): ps.save(Path(pp))

    lcmd = getattr(args, "live_command", None)
    sid = args.session_id

    if lcmd == "open":
        r = _ok(lsvc.activate_session(sid)); _save()
        print(f"Live session activated: {sid}")
    elif lcmd in ("npcs", "locations", "secrets", "clues", "factions", "clocks"):
        fn = {"npcs": lsvc.query_npcs, "locations": lsvc.query_locations,
              "secrets": lsvc.query_secrets, "clues": lsvc.query_clues,
              "factions": lsvc.query_factions, "clocks": lsvc.query_clocks}[lcmd]
        items = fn(sid)
        if getattr(args, "json", False):
            data = [i.to_dict() if hasattr(i, "to_dict") else str(i) for i in items]
            print(json.dumps({lcmd: data}, indent=2, ensure_ascii=False))
        else:
            for i in items:
                name = getattr(i, "name", None) or getattr(i, "title", None) or str(i)
                iid = getattr(i, "id", "?")
                print(f"  {iid}  {name}")
    elif lcmd == "note":
        _ok(lsvc.quick_note(sid, args.text)); _save()
        print("Note registered")
    elif lcmd == "entity":
        r = _ok(lsvc.create_provisional_entity(sid, args.name, args.type, force_canon=args.force_canon)); _save()
        print(f"Entity '{r.name}' ({r.id}) created [provisional]")
    elif lcmd == "relation":
        r = _ok(lsvc.create_provisional_relation(sid, args.source_id, args.target_id, args.type)); _save()
        print(f"Relation ({r.id}) created [provisional]")
    elif lcmd == "clue-deliver":
        _ok(lsvc.mark_clue_delivered(sid, args.clue_id, state=args.state)); _save()
        print(f"Clue {args.clue_id} delivered [{args.state}]")
    elif lcmd == "secret-reveal":
        _ok(lsvc.mark_secret_revealed(sid, args.secret_id, state=args.state)); _save()
        print(f"Secret {args.secret_id} revealed [{args.state}]")
    elif lcmd == "decide":
        _ok(lsvc.register_player_decision(sid, args.text)); _save()
        print("Decision registered")
    elif lcmd == "event":
        _ok(lsvc.register_event(sid, args.text)); _save()
        print("Event registered")
    elif lcmd == "consequence":
        _ok(lsvc.register_consequence(sid, args.text)); _save()
        print("Consequence registered")
    elif lcmd == "improvise":
        r = _ok(lsvc.improvise(sid, hint=args.hint, save=args.save))
        if getattr(args, "json", False):
            print(json.dumps(r.to_dict() if hasattr(r, "to_dict") else {"result": str(r)}, indent=2, ensure_ascii=False))
        else:
            print(r)
    elif lcmd == "check":
        c = _ok(lsvc.check_continuity(sid))
        if getattr(args, "json", False):
            print(json.dumps(c, indent=2, ensure_ascii=False))
        else:
            for k, v in c.items(): print(f"  {k}: {v}")
    elif lcmd == "done":
        r = _ok(lsvc.prepare_post_session(sid)); _save()
        print(f"Live session closed, post-session prepared")
    else:
        print("Usage: narrative-architect session live <subcommand>", file=sys.stderr)
        sys.exit(1)


# ── Post-session handler (B25-T03) ───────────────────────────────────

def _handle_post(args, session):
    pp = require_project_path(args, session)
    ps, psvc = _get_post_svc(pp)

    def _ok(r):
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    def _save(): ps.save(Path(pp))

    cmd = getattr(args, "session_command", None)

    if cmd == "close":
        _ok(psvc.close_session(args.id)); _save()
        if getattr(args, "json", False):
            print(json.dumps({"status": "closed", "id": args.id}, indent=2, ensure_ascii=False))
        else:
            print(f"Session {args.id} closed")
    elif cmd == "post-summary":
        if getattr(args, "player", False):
            s = _ok(psvc.generate_public_summary(args.id))
        else:
            s = _ok(psvc.generate_private_summary(args.id))
        if getattr(args, "json", False):
            print(json.dumps({"summary": s}, indent=2, ensure_ascii=False))
        else:
            print(s)
    elif cmd == "post-candidates":
        from packages.application.candidate_service import CandidateService
        cs = CandidateService(project_service=ps)
        cands = _ok(cs.list_candidates_by_source("post_session"))
        if getattr(args, "json", False):
            print(json.dumps({"candidates": [c.to_dict() for c in cands]}, indent=2, ensure_ascii=False))
        else:
            for c in cands: print(f"  {c.id}  {c.title:<30}  {c.state.value}")
    elif cmd == "post-accept":
        from packages.application.candidate_service import CandidateService
        cs = CandidateService(project_service=ps)
        _ok(cs.accept_candidate(args.candidate_id)); _save()
        print(f"Candidate {args.candidate_id} accepted")
    elif cmd == "post-reject":
        from packages.application.candidate_service import CandidateService
        cs = CandidateService(project_service=ps)
        _ok(cs.reject_candidate(args.candidate_id)); _save()
        print(f"Candidate {args.candidate_id} rejected")
    elif cmd == "post-source":
        r = _ok(psvc.create_session_source(args.id)); _save()
        if getattr(args, "json", False):
            print(json.dumps({"source_id": getattr(r, "id", str(r))}, indent=2, ensure_ascii=False))
        else:
            print(f"Source created for session {args.id}")
    elif cmd == "post-seeds":
        seeds = psvc.generate_next_session_seeds(args.id); _save()
        if getattr(args, "json", False):
            print(json.dumps({"seeds": seeds}, indent=2, ensure_ascii=False))
        else:
            for s in seeds: print(f"  - {s}")
    else:
        print(f"Unknown post-session command: {cmd}", file=sys.stderr)
        sys.exit(1)


# ── Main session handler ─────────────────────────────────────────────

def handle_session(args, session):
    cmd = getattr(args, "session_command", None)

    # Route live and post-session to their own handlers
    if cmd == "live":
        _handle_live(args, session)
        return
    if cmd in ("close", "post-summary", "post-candidates", "post-accept",
               "post-reject", "post-source", "post-seeds"):
        _handle_post(args, session)
        return

    # ── Preparation commands (B23) ──
    pp = require_project_path(args, session); ps, svc, es = _get_svc(pp)
    def _ok(r):
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    def _save(): ps.save(Path(pp))
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
