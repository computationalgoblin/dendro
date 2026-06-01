"""CLI secrets and clues commands — B21-T04."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from packages.application.secrets_service import SecretsService
from packages.domain.result import Error
from packages.ui.cli import _bootstrap_services, require_project_path


def _get_svc(project_path: str):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    svc = SecretsService(project_service=ps, entity_service=es, relation_service=rs)
    return ps, svc, es


def register_secrets_commands(subparsers: Any) -> None:
    # secret
    sp = subparsers.add_parser("secret", help="Secret management")
    ss = sp.add_subparsers(dest="secret_command")

    p = ss.add_parser("create", help="Create a secret")
    p.add_argument("content"); p.add_argument("--importance", type=int, default=3)
    p.add_argument("--canon-state", default="borrador"); p.add_argument("--visibility-state", default="privado")
    p.add_argument("--entity")

    p = ss.add_parser("list", help="List secrets")
    p.add_argument("--state"); p.add_argument("--json", action="store_true")

    p = ss.add_parser("show", help="Show secret"); p.add_argument("id"); p.add_argument("--json", action="store_true")

    p = ss.add_parser("edit", help="Edit secret"); p.add_argument("id")
    p.add_argument("--content"); p.add_argument("--importance", type=int)

    p = ss.add_parser("reveal", help="Reveal a secret"); p.add_argument("id")
    p.add_argument("--state", required=True, choices=["rumoreado","parcialmente_revelado","revelado","malinterpretado"])
    p.add_argument("--session"); p.add_argument("--form"); p.add_argument("--force", action="store_true")

    p = ss.add_parser("hidden", help="List hidden secrets"); p.add_argument("--json", action="store_true")

    p = ss.add_parser("knowledge", help="What an entity knows"); p.add_argument("entity_id"); p.add_argument("--json", action="store_true")

    p = ss.add_parser("player-knowledge", help="What a player knows (all PCs)")
    p.add_argument("player_id"); p.add_argument("campaign_id"); p.add_argument("--json", action="store_true")

    p = ss.add_parser("detect-issues", help="Detect secret/clue issues"); p.add_argument("--json", action="store_true")

    # clue
    cp = subparsers.add_parser("clue", help="Clue management")
    cs = cp.add_subparsers(dest="clue_command")

    p = cs.add_parser("create", help="Create a clue"); p.add_argument("content")
    p.add_argument("--secret"); p.add_argument("--source"); p.add_argument("--location"); p.add_argument("--npc")
    p.add_argument("--form", choices=["documento","testimonio","objeto","rastro","rumor","vision","sueño","descubrimiento"])
    p.add_argument("--clarity", type=int); p.add_argument("--redundancy", type=int); p.add_argument("--loss-risk", type=int)
    p.add_argument("--entity")

    p = cs.add_parser("list", help="List clues"); p.add_argument("--state"); p.add_argument("--json", action="store_true")

    p = cs.add_parser("show", help="Show clue"); p.add_argument("id"); p.add_argument("--json", action="store_true")

    p = cs.add_parser("edit", help="Edit clue"); p.add_argument("id")
    p.add_argument("--content"); p.add_argument("--clarity", type=int)

    p = cs.add_parser("deliver", help="Deliver a clue"); p.add_argument("id")
    p.add_argument("--state", default="entregada", choices=["entregada","perdida","ignorada","malinterpretada"])
    p.add_argument("--session"); p.add_argument("--characters")

    p = cs.add_parser("pending", help="List pending clues"); p.add_argument("--json", action="store_true")

    p = cs.add_parser("link", help="Link clue to secret"); p.add_argument("clue_id"); p.add_argument("secret_id")
    p = cs.add_parser("unlink", help="Unlink clue from secret"); p.add_argument("clue_id")


def handle_secret(args, session) -> None:
    project_path = require_project_path(args, session)
    ps, svc, es = _get_svc(project_path)

    def _ok(r): 
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    def _save(): ps.save(Path(project_path))

    cmd = getattr(args, "secret_command", None)

    if cmd == "create":
        data = {"content": args.content, "importance": args.importance,
                "canon_state": args.canon_state, "visibility_state": args.visibility_state}
        if hasattr(args, "entity") and args.entity: data["entity_id"] = args.entity
        s = _ok(svc.create_secret(data)); _save()
        print(f"Secret '{s.content[:50]}' ({s.id}) created")

    elif cmd == "list":
        secrets = svc.list_secrets(state=args.state)
        if args.json: print(json.dumps({"total": len(secrets), "secrets": [s.to_dict() for s in secrets]}, indent=2))
        else:
            for s in secrets: print(f"  {s.id}  {s.revelation_state.value:<25}  imp={s.importance}  {s.content[:60]}")

    elif cmd == "show":
        s = _ok(svc.get_secret(args.id))
        if args.json: print(json.dumps(s.to_dict(), indent=2))
        else: print(f"ID: {s.id}\nContent: {s.content}\nState: {s.revelation_state.value}\nImportance: {s.importance}\nClues: {s.associated_clue_ids}")

    elif cmd == "edit":
        data = {}; 
        if args.content: data["content"] = args.content
        if args.importance: data["importance"] = args.importance
        s = _ok(svc.update_secret(args.id, data)); _save()
        print(f"Secret '{s.id}' updated")

    elif cmd == "reveal":
        s = _ok(svc.reveal_secret(args.id, args.state, session_id=args.session, form=args.form, force=args.force)); _save()
        print(f"Secret '{s.id}' revealed ({s.revelation_state.value})")

    elif cmd == "hidden":
        secrets = svc.get_hidden_secrets()
        if args.json: print(json.dumps({"total": len(secrets), "secrets": [s.to_dict() for s in secrets]}, indent=2))
        else:
            for s in secrets: print(f"  {s.id}  {s.revelation_state.value}  {s.content[:60]}")

    elif cmd == "knowledge":
        k = svc.get_knowledge_for_character(args.entity_id)
        print(json.dumps(k, indent=2) if args.json else f"Entity {args.entity_id}: {len(k['secrets_known'])} secrets, {len(k['clues_received'])} clues")

    elif cmd == "player-knowledge":
        k = svc.get_knowledge_for_player(args.player_id, args.campaign_id)
        print(json.dumps(k, indent=2))

    elif cmd == "detect-issues":
        issues = svc.run_secret_validation()
        if args.json: print(json.dumps({"total": len(issues), "issues": [i.to_dict() for i in issues]}, indent=2))
        else:
            print(f"Detected {len(issues)} issue(s)")
            for i in issues: print(f"  - [{i.metadata.get('subtype', '?')}] {i.description[:80]}")
        if issues: _save()


def handle_clue(args, session) -> None:
    project_path = require_project_path(args, session)
    ps, svc, es = _get_svc(project_path)

    def _ok(r): 
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        return r.value
    def _save(): ps.save(Path(project_path))

    cmd = getattr(args, "clue_command", None)

    if cmd == "create":
        data = {"content": args.content}
        for f in ("secret", "source", "location", "npc", "entity"):
            val = getattr(args, f, None)
            if val:
                key = {"secret": "associated_secret_id", "source": "source_entity_id",
                       "location": "location_entity_id", "npc": "associated_npc_entity_id", "entity": "entity_id"}[f]
                data[key] = val
        if args.form: data["delivery_form"] = args.form
        if args.clarity: data["clarity"] = args.clarity
        if args.redundancy: data["redundancy"] = args.redundancy
        if args.loss_risk: data["loss_risk"] = args.loss_risk
        c = _ok(svc.create_clue(data)); _save()
        print(f"Clue '{c.content[:50]}' ({c.id}) created")

    elif cmd == "list":
        clues = svc.list_clues(state=args.state)
        if args.json: print(json.dumps({"total": len(clues), "clues": [c.to_dict() for c in clues]}, indent=2))
        else:
            for c in clues: print(f"  {c.id}  {c.delivery_state.value:<15}  cla={c.clarity}  {c.content[:60]}")

    elif cmd == "show":
        c = _ok(svc.get_clue(args.id))
        if args.json: print(json.dumps(c.to_dict(), indent=2))
        else: print(f"ID: {c.id}\nContent: {c.content}\nSecret: {c.associated_secret_id or '(none)'}\nState: {c.delivery_state.value}")

    elif cmd == "edit":
        data = {}; 
        if args.content: data["content"] = args.content
        if args.clarity: data["clarity"] = args.clarity
        c = _ok(svc.update_clue(args.id, data)); _save()
        print(f"Clue '{c.id}' updated")

    elif cmd == "deliver":
        chars = args.characters.split(",") if args.characters else None
        c = _ok(svc.deliver_clue(args.id, state=args.state, session_id=args.session, character_ids=chars)); _save()
        print(f"Clue '{c.id}' delivered ({c.delivery_state.value})")

    elif cmd == "pending":
        clues = svc.get_pending_clues()
        if args.json: print(json.dumps({"total": len(clues), "clues": [c.to_dict() for c in clues]}, indent=2))
        else:
            for c in clues: print(f"  {c.id}  {c.delivery_state.value}  {c.content[:60]}")

    elif cmd == "link":
        c = _ok(svc.link_clue_to_secret(args.clue_id, args.secret_id)); _save()
        print(f"Clue '{c.id}' linked to secret '{args.secret_id}'")

    elif cmd == "unlink":
        c = _ok(svc.unlink_clue_from_secret(args.clue_id)); _save()
        print(f"Clue '{c.id}' unlinked from secret")
