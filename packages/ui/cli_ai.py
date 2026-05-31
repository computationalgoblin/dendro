"""CLI ai commands — generate, expand, summarize, rewrite, suggest (B15-T04)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from packages.application.orchestrator_service import OrchestratorService
from packages.domain.ai_models import AIMode
from packages.domain.result import Error
from packages.ui.cli import _bootstrap_services, require_project_path


def _get_svc(project_path):
    ps, es, rs, ss, hs, qs, ts = _bootstrap_services(project_path)
    from packages.application.candidate_service import CandidateService
    cs = CandidateService(ps, es, rs, hs)
    orch = OrchestratorService(ps, cs, ss, hs)
    return ps, orch, ss


def _get_filters(args):
    f = {}
    for k in ("domain_id", "layer_id", "output_profile", "audience"):
        v = getattr(args, k, None)
        if v: f[k] = v
    if getattr(args, "include_history", False): f["include_history"] = True
    if getattr(args, "include_issues", False): f["include_issues"] = True
    if getattr(args, "canon", None): f["canon_states"] = [args.canon]
    if getattr(args, "visibility", None): f["visibility_states"] = [args.visibility]
    if getattr(args, "framework", None): f["active_framework_ids"] = [args.framework]
    return f or None


def _add_common_flags(p):
    p.add_argument("--canon")
    p.add_argument("--visibility")
    p.add_argument("--audience", choices=["author", "player", "public"])
    p.add_argument("--include-history", action="store_true")
    p.add_argument("--include-issues", action="store_true")
    p.add_argument("--framework")
    p.add_argument("--domain-id")
    p.add_argument("--layer-id")


def register_ai_commands(subparsers: Any) -> None:
    ai = subparsers.add_parser("ai", help="AI commands")
    ais = ai.add_subparsers(dest="ai_command", required=True)

    p = ais.add_parser("generate-entity", help="Generate entity candidates")
    p.add_argument("--prompt", default="")
    p.add_argument("--count", type=int, default=2)
    _add_common_flags(p)

    p = ais.add_parser("generate-relation", help="Generate relation candidates")
    p.add_argument("--prompt", default="")
    _add_common_flags(p)

    p = ais.add_parser("expand", help="Expand entity")
    p.add_argument("entity_id")
    p.add_argument("--prompt", default="")
    _add_common_flags(p)

    p = ais.add_parser("summarize", help="Summarize entity")
    p.add_argument("entity_id")
    _add_common_flags(p)

    p = ais.add_parser("rewrite", help="Rewrite description")
    p.add_argument("entity_id")
    p.add_argument("--style", default="")
    _add_common_flags(p)

    p = ais.add_parser("suggest-tags", help="Suggest tags")
    p.add_argument("entity_id")
    _add_common_flags(p)

    p = ais.add_parser("suggest-relations", help="Suggest relations")
    p.add_argument("entity_id")
    p.add_argument("--prompt", default="")
    _add_common_flags(p)

    p = ais.add_parser("continuity", help="Continuity question")
    p.add_argument("question")
    _add_common_flags(p)

    # B16: analysis commands
    p = ais.add_parser("analyze", help="Critical analysis of entity")
    p.add_argument("entity_id")
    _add_common_flags(p)
    p = ais.add_parser("analyze-group", help="Critical analysis of group")
    p.add_argument("entity_ids", nargs="+")
    _add_common_flags(p)
    p = ais.add_parser("causal", help="Causal analysis")
    p.add_argument("entity_id")
    _add_common_flags(p)
    p = ais.add_parser("consistency", help="Consistency analysis")
    p.add_argument("--scope")
    
    _add_common_flags(p)


def handle_ai_command(args, session):
    project_path = require_project_path(args, session)
    cmd = args.ai_command
    ps, orch, ss = _get_svc(project_path)
    filters = _get_filters(args)

    if cmd == "generate-entity":
        r = orch.generate_candidates(AIMode.GENERATE_ENTITY, prompt_hint=getattr(args, "prompt", ""), filters=filters)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print(f"AI (simulated) generated {len(r.value)} entity candidates")
        for c in r.value:
            print(f"  [{c.id[:8]}] {c.title}")

    elif cmd == "generate-relation":
        r = orch.generate_candidates(AIMode.GENERATE_RELATION, prompt_hint=getattr(args, "prompt", ""), filters=filters)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print(f"AI generated {len(r.value)} relation candidates")

    elif cmd == "expand":
        r = orch.invoke(AIMode.EXPAND_ENTITY, args.entity_id, getattr(args, "prompt", ""), filters)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print(r.value.raw_text)

    elif cmd == "summarize":
        r = orch.invoke(AIMode.SUMMARIZE, args.entity_id, "", filters)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        print(r.value.raw_text)

    elif cmd == "rewrite":
        r = orch.generate_candidates(AIMode.REWRITE_DESCRIPTION, args.entity_id, "", filters)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print(r.value[0].raw_text if hasattr(r.value[0], 'raw_text') else "Rewritten")

    elif cmd == "suggest-tags":
        r = orch.generate_candidates(AIMode.SUGGEST_TAGS, args.entity_id, "", filters)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        for c in r.value:
            print(f"  Suggested tags for entity: {c.title}")

    elif cmd == "suggest-relations":
        r = orch.generate_candidates(AIMode.SUGGEST_RELATIONS, args.entity_id, getattr(args, "prompt", ""), filters)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        ps.save(Path(project_path))
        print(f"AI generated {len(r.value)} relation suggestions")

    elif cmd == "continuity":
        r = orch.invoke(AIMode.CONTINUITY_QUESTION, prompt_hint=args.question, filters=filters)
        if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
        print(r.value.raw_text)

    elif cmd in ("analyze", "analyze-group", "causal", "consistency"):
        from packages.application.analysis_service import AnalysisService
        analysis = AnalysisService(orch, source_service=ss)
        if cmd == "analyze":
            r = analysis.analyze_entity(args.entity_id, filters)
            if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
            res = r.value
            ps.save(Path(project_path))
            print(f"Critical analysis: {len(res.observations)} observations, {len(res.candidate_issues)} issues, {len(res.correction_proposals)} proposals")
        elif cmd == "analyze-group":
            for eid in args.entity_ids:
                r = analysis.analyze_entity(eid, filters)
                if isinstance(r, Error): print(f"  {eid[:8]}: error"); continue
                print(f"  {eid[:8]}: {len(r.value.observations)} observations")
            ps.save(Path(project_path))
        elif cmd == "causal":
            r = analysis.analyze_causal(args.entity_id, filters)
            if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
            print(f"Causal: {len(r.value.direct_consequences)} consequences, {len(r.value.causal_relation_candidates)} relation candidates")
            ps.save(Path(project_path))
        elif cmd == "consistency":
            r = analysis.analyze_consistency(getattr(args, "scope", None), filters)
            if isinstance(r, Error): print(f"error: {r.error}", file=sys.stderr); sys.exit(1)
            total = len(r.value.narrative_contradictions) + len(r.value.causal_gaps)
            print(f"Consistency: {total} issues found")
            ps.save(Path(project_path))
