
"""CLI framework commands — list, show, create, edit, activate, associate,
coverage, mark-absent, duplicate, add-component, template (B13-T04)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from packages.application.framework_service import FrameworkService
from packages.domain.narrative_framework import FrameworkType
from packages.domain.result import Error
from packages.ui.cli import _bootstrap_services, require_project_path


def _get_svc(project_path):
    ps, *_ = _bootstrap_services(project_path)
    return ps, FrameworkService(project_service=ps)


def register_framework_commands(subparsers: Any) -> None:
    fp = subparsers.add_parser("framework", help="Framework commands")
    fs = fp.add_subparsers(dest="framework_command", required=True)

    p = fs.add_parser("list", help="List frameworks")
    p.add_argument("--json", action="store_true")
    p.add_argument("--active", action="store_true")

    p = fs.add_parser("show", help="Show framework detail")
    p.add_argument("id", help="Framework ID")

    p = fs.add_parser("create", help="Create framework")
    p.add_argument("name", help="Framework name")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--type", help="Framework type (builtin template)")
    group.add_argument("--template", help="Template ID (builtin or custom)")

    p = fs.add_parser("edit", help="Edit framework metadata")
    p.add_argument("id", help="Framework ID")
    p.add_argument("--name", help="New name")
    p.add_argument("--desc", help="New description")

    p = fs.add_parser("toggle", help="Toggle active/inactive")
    p.add_argument("id", help="Framework ID")

    p = fs.add_parser("activate", help="Activate framework")
    p.add_argument("id", help="Framework ID")

    p = fs.add_parser("deactivate", help="Deactivate framework")
    p.add_argument("id", help="Framework ID")

    p = fs.add_parser("associate-entity", help="Associate entity to component")
    p.add_argument("fw_id", help="Framework ID")
    p.add_argument("comp_id", help="Component ID")
    p.add_argument("entity_id", help="Entity ID")

    p = fs.add_parser("associate-relation", help="Associate relation to component")
    p.add_argument("fw_id", help="Framework ID")
    p.add_argument("comp_id", help="Component ID")
    p.add_argument("rel_id", help="Relation ID")

    p = fs.add_parser("coverage", help="Show framework coverage")
    p.add_argument("id", help="Framework ID")

    p = fs.add_parser("mark-absent", help="Mark component absence as deliberate")
    p.add_argument("fw_id", help="Framework ID")
    p.add_argument("comp_id", help="Component ID")

    p = fs.add_parser("duplicate", help="Duplicate framework")
    p.add_argument("id", help="Framework ID")
    p.add_argument("--name", required=True, help="New name")

    p = fs.add_parser("add-component", help="Add component to framework")
    p.add_argument("fw_id", help="Framework ID")
    p.add_argument("name", help="Component name")
    p.add_argument("--desc", default="")
    p.add_argument("--optional", action="store_true")

    tp = fs.add_parser("template", help="Template commands")
    ts = tp.add_subparsers(dest="template_command", required=True)
    ts.add_parser("list", help="List available templates")
    p = ts.add_parser("save", help="Save framework as template")
    p.add_argument("fw_id", help="Framework ID")
    p.add_argument("--name", required=True, help="Template name")


def handle_framework_command(args, session):
    project_path = require_project_path(args, session)
    cmd = args.framework_command

    if cmd == "list":
        ps, svc = _get_svc(project_path)
        result = svc.list_frameworks(active_only=args.active)
        if isinstance(result, Error):
            print(f"error: {result.error}", file=sys.stderr); sys.exit(1)
        fws = result.value
        if not fws:
            print("No frameworks found")
            return
        for fw in fws:
            active = "[*]" if fw.is_active else "[ ]"
            print(f"  {active} {fw.id}  {fw.name:<30s} {fw.framework_type.value}")

    elif cmd == "show":
        ps, svc = _get_svc(project_path)
        r = svc.get_framework(args.id)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        fw = r.value
        print(f"Framework: {fw.name} ({fw.framework_type.value}) {'ACTIVE' if fw.is_active else 'inactive'}")
        print(f"  ID: {fw.id}")
        for c in fw.components:
            ents = len(c.associated_entity_ids)
            rels = len(c.associated_relation_ids)
            mark = "·" if c.absence_deliberate else ("✓" if ents + rels > 0 else " ")
            print(f"  [{mark}] {c.id}  {c.name}  ({ents}e, {rels}r)")

    elif cmd == "create":
        ps, svc = _get_svc(project_path)
        if args.template:
            r = svc.create_from_template(args.name, args.template)
        else:
            try:
                ft = FrameworkType(args.type)
            except ValueError:
                print(f"error: Invalid type '{args.type}'", file=sys.stderr); sys.exit(1)
            r = svc.create_framework(args.name, ft)
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print(f"Framework '{r.value.name}' ({r.value.id}) created")

    elif cmd in ("edit", "toggle", "activate", "deactivate", "mark-absent",
                  "associate-entity", "associate-relation", "duplicate",
                  "add-component", "coverage"):
        ps, svc = _get_svc(project_path)
        save = True
        if cmd == "edit":
            data = {}
            if args.name: data["name"] = args.name
            if args.desc: data["description"] = args.desc
            r = svc.update_framework(args.id, data)
            msg = f"Framework '{args.id[:8]}' updated"
        elif cmd == "toggle":
            r = svc.toggle_active(args.id)
            msg = f"Framework '{args.id[:8]}' toggled"
        elif cmd == "activate":
            r = svc.activate(args.id)
            msg = f"Framework '{args.id[:8]}' activated"
        elif cmd == "deactivate":
            r = svc.deactivate(args.id)
            msg = f"Framework '{args.id[:8]}' deactivated"
        elif cmd == "associate-entity":
            r = svc.associate_entity(args.fw_id, args.comp_id, args.entity_id)
            msg = "Entity associated"
        elif cmd == "associate-relation":
            r = svc.associate_relation(args.fw_id, args.comp_id, args.rel_id)
            msg = "Relation associated"
        elif cmd == "mark-absent":
            r = svc.mark_absence_deliberate(args.fw_id, args.comp_id)
            msg = "Absence marked as deliberate"
        elif cmd == "duplicate":
            r = svc.duplicate_framework(args.id, args.name)
            msg = f"Framework duplicated as '{args.name}'"
        elif cmd == "add-component":
            r = svc.add_component(args.fw_id, args.name, args.desc, args.optional)
            msg = f"Component '{r.value.id[:8]}' added" if not isinstance(r, Error) else ""
        elif cmd == "coverage":
            r = svc.get_coverage(args.id)
            save = False
        else:
            return
        if isinstance(r, Error):
            print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        if save:
            ps.save(Path(project_path))
        if cmd == "coverage":
            cov = r.value
            print(f"Coverage: {cov.coverage_pct}% ({cov.filled_components}/{cov.total_components})")
            for c in cov.components:
                ents = len(c.associated_entity_ids)
                rels = len(c.associated_relation_ids)
                mark = "·" if c.absence_deliberate else ("✓" if ents + rels > 0 else " ")
                print(f"  [{mark}] {c.name}  ({ents}e, {rels}r)")
        elif msg:
            print(msg)

    elif cmd == "template":
        ps, svc = _get_svc(project_path)
        tcmd = args.template_command
        if tcmd == "list":
            r = svc.list_templates()
            if isinstance(r, Error):
                print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
            for t in r.value:
                builtin = " (builtin)" if len(t.components) > 0 else " (custom)"
                print(f"  {t.id}  {t.name:<30s} {t.framework_type.value}{builtin}")
        elif tcmd == "save":
            r = svc.save_as_template(args.fw_id, args.name)
            if isinstance(r, Error):
                print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
            ps.save(Path(project_path))
            print(f"Template '{args.name}' saved")
