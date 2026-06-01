"""CLI export commands — B26-T02."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from packages.application.export_service import ExportService
from packages.domain.result import Error
from packages.ui.cli import _bootstrap_services, require_project_path

def _get_svc(pp):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(pp)
    return ps, ExportService(project_service=ps, entity_service=es, session_service=ss)

def register_export_commands(subparsers):
    sp = subparsers.add_parser("export", help="Export commands"); es = sp.add_subparsers(dest="export_command")
    p = es.add_parser("public-summary"); p.add_argument("--audience", choices=["public","player","gm"], default="public"); p.add_argument("--json", action="store_true")
    p = es.add_parser("session"); p.add_argument("session_id"); p.add_argument("--audience", choices=["player","gm"], default="player"); p.add_argument("--json", action="store_true")
    p = es.add_parser("campaign"); p.add_argument("campaign_id"); p.add_argument("--audience", choices=["gm","player","public"], default="gm"); p.add_argument("--json", action="store_true")
    p = es.add_parser("entity"); p.add_argument("entity_id"); p.add_argument("--audience", choices=["gm","player","public"], default="gm"); p.add_argument("--json", action="store_true")
    p = es.add_parser("relation"); p.add_argument("relation_id"); p.add_argument("--audience", choices=["gm","player","public"], default="gm"); p.add_argument("--json", action="store_true")
    p = es.add_parser("all"); p.add_argument("--audience", choices=["gm","player","public"], default="gm"); p.add_argument("--json", action="store_true")

def handle_export(args, session):
    pp = require_project_path(args, session); ps, svc = _get_svc(pp)
    def _ok(r):
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    aud = args.audience if hasattr(args, "audience") else "gm"
    cmd = getattr(args, "export_command", None)
    if cmd == "public-summary": r = _ok(svc.export_public_summary(aud))
    elif cmd == "session": r = _ok(svc.export_session_player_summary(args.session_id))
    elif cmd == "campaign": r = _ok(svc.export_campaign_report(args.campaign_id, aud))
    elif cmd == "entity": r = _ok(svc.export_entity_profile(args.entity_id, aud))
    elif cmd == "relation": r = _ok(svc.export_relation_profile(args.relation_id, aud))
    elif cmd == "all": r = _ok(svc.export_all(aud))
    else: print("error: unknown export command", file=sys.stderr); sys.exit(1)
    print(json.dumps(r, indent=2) if isinstance(r, dict) and args.json else r)
