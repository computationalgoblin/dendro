"""CLI candidate commands — list, show, create, edit, accept, reject,
merge, convert, archive, partial-accept (B14-T04)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from packages.application.candidate_service import CandidateService
from packages.domain.result import Error
from packages.ui.cli import _bootstrap_services, require_project_path


def _get_svc(project_path):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    return ps, CandidateService(ps, es, rs, hs)


def register_candidate_commands(subparsers: Any) -> None:
    cp = subparsers.add_parser("candidate", help="Candidate commands")
    cs = cp.add_subparsers(dest="candidate_command", required=True)

    p = cs.add_parser("list", help="List candidates")
    p.add_argument("--state")
    p.add_argument("--type", dest="ctype")

    p = cs.add_parser("show", help="Show candidate detail")
    p.add_argument("id")

    p = cs.add_parser("create", help="Create candidate")
    p.add_argument("title")
    p.add_argument("--type", dest="ctype", required=True)
    p.add_argument("--data", default="{}")
    p.add_argument("--source", default="manual")
    p.add_argument("--confidence", type=float, default=0.5)
    p.add_argument("--justification", default="")
    p.add_argument("--impact", default="")
    p.add_argument("--entity", dest="entity_id")

    p = cs.add_parser("edit", help="Edit candidate")
    p.add_argument("id")
    p.add_argument("--title")
    p.add_argument("--data")
    p.add_argument("--confidence", type=float)
    p.add_argument("--justification")
    p.add_argument("--source")

    p = cs.add_parser("accept", help="Accept candidate -> entity/relation")
    p.add_argument("id")

    p = cs.add_parser("accept-with-changes", help="Accept with modifications")
    p.add_argument("id")
    p.add_argument("--data", required=True)

    p = cs.add_parser("partial-accept", help="Partial acceptance")
    p.add_argument("id")
    p.add_argument("--data", required=True)
    p.add_argument("--note", default="")

    p = cs.add_parser("reject", help="Reject candidate")
    p.add_argument("id")
    p.add_argument("--note", default="")

    p = cs.add_parser("postpone", help="Postpone candidate")
    p.add_argument("id")

    p = cs.add_parser("merge", help="Merge candidate into entity")
    p.add_argument("id")
    p.add_argument("--entity", required=True)

    p = cs.add_parser("convert", help="Convert candidate type")
    p.add_argument("id")
    p.add_argument("--type", dest="new_type", required=True)

    p = cs.add_parser("archive", help="Archive candidate")
    p.add_argument("id")

    p = cs.add_parser("by-source", help="Candidates by source")
    p.add_argument("source")

    p = cs.add_parser("by-entity", help="Candidates by entity")
    p.add_argument("entity_id")


def handle_candidate_command(args, session):
    project_path = require_project_path(args, session)
    cmd = args.candidate_command

    if cmd == "list":
        ps, svc = _get_svc(project_path)
        r = svc.list_candidates(
            state=getattr(args, "state", None),
            ctype=getattr(args, "ctype", None),
        )
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        cands = r.value
        if not cands:
            print("No candidates found")
            return
        print(f"Candidates: {len(cands)}")
        for c in cands:
            print(
                f"  [{c.state.value.upper():12s}] {c.candidate_type.value:<15s} "
                f"{c.title[:30]:30s} conf={c.confidence:.1f}  source={c.source}"
            )

    elif cmd == "show":
        ps, svc = _get_svc(project_path)
        r = svc.get_candidate(args.id)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        c = r.value
        print(f"Candidate: {c.id}")
        print(f"  Type: {c.candidate_type.value}")
        print(f"  State: {c.state.value}")
        print(f"  Title: {c.title}")
        print(f"  Source: {c.source} (source_id: {c.source_id or '—'})")
        print(f"  Confidence: {c.confidence}")
        print(f"  Justification: {c.justification or '—'}")
        print(f"  Expected impact: {c.expected_impact or '—'}")
        if c.affected_entity_ids:
            print(f"  Affected entities: {', '.join(c.affected_entity_ids)}")
        print(f"  Proposed data: {json.dumps(c.proposed_data)}")
        print(f"  Created: {c.created_at.isoformat()}")
        print(f"  Reviewed: {c.reviewed_at.isoformat() if c.reviewed_at else '—'}")
        print(f"  Final action: {c.final_action or '—'}")

    elif cmd == "create":
        ps, svc = _get_svc(project_path)
        data = {"title": args.title, "candidate_type": args.ctype, "source": args.source}
        if args.confidence:
            data["confidence"] = args.confidence
        if args.justification:
            data["justification"] = args.justification
        if args.impact:
            data["expected_impact"] = args.impact
        if args.entity_id:
            data["affected_entity_ids"] = [args.entity_id]
        try:
            data["proposed_data"] = json.loads(args.data)
        except json.JSONDecodeError:
            print("error: --data must be valid JSON", file=sys.stderr); sys.exit(1)
        r = svc.create_candidate(data)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print(f"Candidate '{r.value.title}' ({r.value.id}) created")

    elif cmd in ("edit", "accept", "accept-with-changes", "partial-accept",
                  "reject", "postpone", "merge", "convert", "archive",
                  "by-source", "by-entity"):
        ps, svc = _get_svc(project_path)
        save = True

        if cmd == "edit":
            data = {}
            if args.title: data["title"] = args.title
            if args.data: data["proposed_data"] = json.loads(args.data)
            if args.confidence is not None: data["confidence"] = args.confidence
            if args.justification: data["justification"] = args.justification
            if args.source: data["source"] = args.source
            r = svc.update_candidate(args.id, data)
            msg = f"Candidate '{args.id[:8]}' updated"
        elif cmd == "accept":
            r = svc.accept_candidate(args.id)
            msg = f"Candidate '{args.id[:8]}' accepted"
        elif cmd == "accept-with-changes":
            r = svc.accept_with_changes(args.id, json.loads(args.data))
            msg = f"Candidate '{args.id[:8]}' accepted with changes"
        elif cmd == "partial-accept":
            r = svc.partial_accept_candidate(args.id, json.loads(args.data), args.note)
            msg = f"Candidate '{args.id[:8]}' partially accepted"
        elif cmd == "reject":
            r = svc.reject_candidate(args.id, args.note)
            msg = f"Candidate '{args.id[:8]}' rejected"
        elif cmd == "postpone":
            r = svc.postpone_candidate(args.id)
            msg = f"Candidate '{args.id[:8]}' postponed"
        elif cmd == "merge":
            r = svc.merge_candidate(args.id, args.entity)
            msg = f"Candidate '{args.id[:8]}' merged"
        elif cmd == "convert":
            r = svc.convert_candidate(args.id, args.new_type)
            msg = f"Candidate '{args.id[:8]}' converted"
        elif cmd == "archive":
            r = svc.archive_candidate(args.id)
            msg = f"Candidate '{args.id[:8]}' archived"
        elif cmd == "by-source":
            r = svc.list_candidates_by_source(args.source)
            save = False
        elif cmd == "by-entity":
            r = svc.list_candidates_by_entity(args.entity_id)
            save = False
        else:
            return

        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        if save:
            ps.save(Path(project_path))
        if cmd in ("by-source", "by-entity"):
            for c in r.value:
                print(f"  [{c.state.value}] {c.title} ({c.candidate_type.value})")
        else:
            print(msg)
