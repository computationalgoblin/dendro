"""CLI timeline commands — list, show, create, edit, check (B18-T04)."""

from __future__ import annotations

import argparse, json, sys
from pathlib import Path
from typing import Any

from packages.application.timeline_service import TimelineService
from packages.domain.result import Error
from packages.ui.cli import _bootstrap_services, require_project_path


def _get_svc(project_path):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    return ps, TimelineService(ps, ts)


def register_timeline_commands(subparsers: Any) -> None:
    tp = subparsers.add_parser("timeline", help="Timeline commands")
    ts = tp.add_subparsers(dest="timeline_command", required=True)

    p = ts.add_parser("list", help="List timeline events")
    p.add_argument("--layer-id")
    p.add_argument("--domain-id")
    p.add_argument("--entity")
    p.add_argument("--canon")
    p.add_argument("--json", action="store_true")

    p = ts.add_parser("show", help="Show event detail")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")

    p = ts.add_parser("create", help="Create timeline event")
    p.add_argument("name")
    p.add_argument("--date")
    p.add_argument("--world-date")
    p.add_argument("--precision", default="unknown")
    p.add_argument("--desc", default="")

    p = ts.add_parser("edit", help="Edit timeline event")
    p.add_argument("id")
    p.add_argument("--name")
    p.add_argument("--desc")
    p.add_argument("--date")

    p = ts.add_parser("add-participant", help="Add participant to event")
    p.add_argument("event_id")
    p.add_argument("entity_id")

    p = ts.add_parser("add-location", help="Add location to event")
    p.add_argument("event_id")
    p.add_argument("location_id")

    p = ts.add_parser("add-cause", help="Add cause event")
    p.add_argument("event_id")
    p.add_argument("cause_id")

    p = ts.add_parser("add-consequence", help="Add consequence event")
    p.add_argument("event_id")
    p.add_argument("consequence_id")

    p = ts.add_parser("check", help="Detect temporal inconsistencies")
    p.add_argument("--json", action="store_true")


def handle_timeline_command(args, session):
    project_path = require_project_path(args, session)
    cmd = args.timeline_command
    ps, svc = _get_svc(project_path)

    if cmd == "list":
        filters = {}
        if getattr(args, "layer_id", None): filters["layer_id"] = args.layer_id
        if getattr(args, "domain_id", None): filters["domain_id"] = args.domain_id
        if getattr(args, "entity", None): filters["entity_id"] = args.entity
        if getattr(args, "canon", None): filters["canon_state"] = args.canon
        r = svc.get_ordered_events(filters or None)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        if args.json:
            print(json.dumps([e.to_dict() for e in r.value], indent=2))
        else:
            if not r.value: print("No timeline events"); return
            for e in r.value:
                d = e.temporality.absolute_date or e.temporality.world_date or e.temporality.era or "unknown"
                print(f"  {e.id}  {e.name:<30s} {e.temporality.precision.value:<12s} {d}")

    elif cmd == "show":
        r = svc.get_event(args.id)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        e = r.value
        if args.json:
            print(json.dumps(e.to_dict(), indent=2))
        else:
            print(f"Event: {e.name} ({e.temporality.precision.value})")
            print(f"  ID: {e.id}"); print(f"  Date: {e.temporality.absolute_date or '—'}")
            print(f"  World: {e.temporality.world_date or '—'}"); print(f"  Era: {e.temporality.era or '—'}")
            print(f"  Participants: {len(e.participant_ids)}"); print(f"  Causes: {len(e.cause_ids)}")
            print(f"  Consequences: {len(e.consequence_ids)}")

    elif cmd == "create":
        temp_data = {"absolute_date": args.date, "world_date": getattr(args, "world_date", None)}
        try: temp_data["precision"] = args.precision
        except ValueError: pass
        r = svc.create_event({"name": args.name, "description": args.desc, "temporality": temp_data})
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print(f"Event '{r.value.name}' ({r.value.id}) created")

    elif cmd == "edit":
        data = {}
        if args.name: data["name"] = args.name
        if args.desc: data["description"] = args.desc
        if args.date: data["temporality"] = {"absolute_date": args.date}
        r = svc.update_event(args.id, data)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print(f"Event '{args.id[:8]}' updated")

    elif cmd in ("add-participant", "add-location", "add-cause", "add-consequence"):
        if cmd == "add-participant":
            r = svc.add_participant(args.event_id, args.entity_id)
        elif cmd == "add-location":
            r = svc.add_location(args.event_id, args.location_id)
        elif cmd == "add-cause":
            r = svc.add_cause(args.event_id, args.cause_id)
        else:
            r = svc.add_consequence(args.event_id, args.consequence_id)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print("OK")

    elif cmd == "check":
        issues = svc.detect_temporal_inconsistencies()
        if args.json:
            print(json.dumps([{"description": i.description} for i in issues], indent=2))
        elif not issues:
            print("No temporal inconsistencies found")
        else:
            for i in issues:
                print(f"  - {i.description}")
        if issues:
            proj = svc._proj()
            if not isinstance(proj, Error):
                for i in issues:
                    proj.value.issues.append(i)
                ps.save(Path(project_path))
                print(f"{len(issues)} issue(s) created and saved")
