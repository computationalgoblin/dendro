#!/usr/bin/env python
"""Run all test suites for narrative-architect.

Usage:
    python scripts/run_all_tests.py              # full suite
    python scripts/run_all_tests.py --fast        # skip slow CLI subprocess tests
    python scripts/run_all_tests.py --suites core # run only 'core' suite
    python scripts/run_all_tests.py --suites core arch qa

Suites:
    core        domain + application + persistence (fast)
    arch        architecture (fast)
    ui          CLI tests via subprocess (slow)
    qa          QA contract tests (slow)
    perf        performance tests (fast)
    integ       integration tests (slow)
    desktop     DesktopHost/PySide contract tests (fast/static)
    b33         Creación MVP stable smoke/regression tests
    b34         Tree semantic contract smoke/regression tests
    b35         Coherencia de subgrafo smoke/regression tests
    b36         Worldbuilding causal layer contract tests
    b37         Creación complexity search/filter tests
    b38         Command bar AI jobs smoke/regression tests
    b39         Project control artifacts/tests
    infra       infrastructure tests (fast)
    sanity      test_sanity (fast)
    all         everything (default)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

SUITES: dict[str, list[str]] = {
    "core": ["tests/domain", "tests/application", "tests/persistence"],
    "arch": ["tests/architecture"],
    "ui": ["tests/ui"],
    "qa": ["tests/qa"],
    "perf": ["tests/performance"],
    "integ": ["tests/integration"],
    "desktop": ["tests/desktop"],
    "b33": [
        "tests/application/test_b33_visual_relation.py",
        "tests/application/test_b33_relation_inline_ai.py",
        "tests/application/test_b33_creation_mvp_stabilization.py",
        "tests/ui/test_b33_visual_relation_static.py",
        "tests/ui/test_b33_relation_inline_ai_static.py",
        "tests/desktop/test_b33_creation_mvp_stabilization.py",
    ],
    "b34": [
        "tests/application/test_b34_tree_contract.py",
        "tests/application/test_b34_tree_panel_lifecycle.py",
        "tests/application/test_b34_tree_narrative_relations.py",
        "tests/application/test_b34_tree_ia_context.py",
        "tests/application/test_b34_fix02_transitive_collapse.py",
        "tests/application/test_b34_fix03_zorder_hitesting.py",
    ],
    "b35": [
        "tests/application/test_b35_coherence.py",
    ],
    "b36": [
        "tests/application/test_b36_causal_layer_contract.py",
        "tests/application/test_b36_causal_layers_integration.py",
    ],
    "b37": [
        "tests/desktop/test_b37_creation_search_filters.py",
        "tests/desktop/test_b37_t07_smoke.py",
    ],
    "b38": [
        "tests/application/test_b38_ai_jobs.py",
        "tests/desktop/test_b38_command_bar_jobs.py",
    ],
    "b39": [
        "tests/project_control/test_b39_project_control_artifacts.py",
    ],
    "infra": ["tests/infrastructure"],
    "sanity": ["tests/test_sanity.py"],
}

# Slow suites that get skipped with --fast
FAST_SKIP = {"ui", "qa", "integ"}


def _clean_env() -> dict[str, str]:
    """Return os.environ copy suitable for subprocess (all str values)."""
    import os
    return dict(os.environ)


def run_suite(label: str, paths: list[str], timeout: int = 600) -> tuple[bool, float, int]:
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", *paths]
    env = {**_clean_env(), "PYTHONPATH": str(WORKSPACE)}
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - t0
        print(f"  [{label}] TIMEOUT after {elapsed:.1f}s")
        return False, elapsed, -1

    elapsed = time.perf_counter() - t0
    ok = result.returncode == 0

    # Extract counts from last line like "1149 passed in 12.11s"
    summary = result.stdout.strip().split("\n")[-1] if result.stdout else ""
    count = -1
    for token in summary.split():
        if token.isdigit():
            count = int(token)
            break

    status = "PASS" if ok else "FAIL"
    print(f"  [{label}] {status} — {summary} ({elapsed:.1f}s)")

    if not ok:
        # Show failures
        lines = result.stdout.split("\n")
        for line in lines:
            if "FAILED" in line or "ERROR" in line or "assert" in line.lower():
                print(f"    {line}")

    return ok, elapsed, count


def main() -> int:
    parser = argparse.ArgumentParser(description="Run narrative-architect test suites")
    parser.add_argument("--fast", action="store_true", help="Skip slow suites (ui, qa, integ)")
    parser.add_argument("--suites", nargs="+", choices=[*SUITES.keys(), "all"], default=["all"],
                        help="Which suites to run")
    args = parser.parse_args()

    if "all" in args.suites:
        selected = list(SUITES.keys())
    else:
        selected = args.suites

    if args.fast:
        skipped = [s for s in selected if s in FAST_SKIP]
        selected = [s for s in selected if s not in FAST_SKIP]
        if skipped:
            print(f"Skipping slow suites (--fast): {', '.join(skipped)}")

    print(f"\n{'='*60}")
    print(f"  narrative-architect test runner")
    print(f"  Suites: {', '.join(selected)}")
    print(f"{'='*60}\n")

    results: list[tuple[str, bool, float, int]] = []
    total_t0 = time.perf_counter()

    for suite in selected:
        paths = SUITES[suite]
        ok, elapsed, count = run_suite(suite, paths)
        results.append((suite, ok, elapsed, count))

    total_elapsed = time.perf_counter() - total_t0

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    all_ok = True
    for suite, ok, elapsed, count in results:
        status = "PASS" if ok else "FAIL"
        detail = f"{count} tests" if count >= 0 else "?"
        print(f"  {suite:8s}  {status}  {detail:>10s}  {elapsed:>6.1f}s")
        if not ok:
            all_ok = False

    print(f"  {'TOTAL':8s}  {'----':4s}  {'':>10s}  {total_elapsed:>6.1f}s")
    print()

    if all_ok:
        print("  ALL SUITES PASSED")
    else:
        failed = [s for s, ok, _, _ in results if not ok]
        print(f"  FAILED: {', '.join(failed)}")

    print()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
