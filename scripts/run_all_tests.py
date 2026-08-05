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
    b40         Creative project config and wizard tests
    b41         Causal milestones domain/persistence tests
    b42         AI gateway, sanitizer, model params y prompt tests
    b43         Command bar prompt-registry migration tests
    b44         Concentric rings layout (desktop) tests
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
    # BETA-CIERRE WS-G: la suite `integ` (única = e2e del CLI retirado) se eliminó
    # con el host CLI; la integración real la cubre el smoke e2e de `desktop`.
    "desktop": ["tests/desktop"],
    # (limpieza post-WIKI 2026-07-21: los tests de superficie IA retirada se
    # borraron; las suites b3x/b4x conservan solo los ficheros vigentes)
    "b33": [
        "tests/application/test_b33_visual_relation.py",
        "tests/ui/test_b33_visual_relation_static.py",
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
    "b36": [
        "tests/application/test_b36_causal_layer_contract.py",
    ],
    "b37": [
        "tests/desktop/test_b37_creation_search_filters.py",
        "tests/desktop/test_b37_t07_smoke.py",
    ],
    "b40": [
        "tests/application/test_b40_creative_config.py",
        "tests/desktop/test_b40_project_panel_regression.py",
        "tests/desktop/test_b40_graph_candidates_regression.py",
        "tests/desktop/test_b40_project_wizard_save_regression.py",
    ],
    "b41": [
        "tests/domain/test_b41_causal_milestone.py",
        "tests/persistence/test_schema_v23_causal_milestones.py",
        "tests/application/test_candidate_service.py::TestCandidateService::test_create_causal_milestone_candidate_is_review_only",
        "tests/application/test_b41_causal_milestone_service.py",
        "tests/desktop/test_b41_causal_milestone_ui_static.py",
        "tests/desktop/test_b41_t04_hito_from_selection.py",
        "tests/application/test_b41_t06_milestone_reviewer.py",
        "tests/application/test_b41_t07_status_quo.py",
    ],
    "b42": [
        "tests/application/test_b42_t01_ai_request_gateway.py",
        "tests/application/test_b42_t02_context_sanitizer.py",
        "tests/application/test_b42_t03_model_params.py",
        "tests/application/test_b42_t05_output_schema.py",
        "tests/application/test_b42_t06_prompt_registry.py",
        "tests/application/test_b42_t07_legacy_hardening.py",
        "tests/application/test_b42_t08_structured_coherence.py",
        "tests/application/test_b42_t09_observability.py",
        "tests/application/test_b42_t10_candidate_dedup.py",
    ],
    "b43": [
        "tests/application/test_b43_t01_command_bar_migration.py",
        "tests/application/test_b43_t06_static_guard.py",
        "tests/application/test_b43_t07_smoke.py",
    ],
    "b44": [
        "tests/desktop/test_b44_concentric_rings_layout.py",
    ],
    "infra": ["tests/infrastructure"],
    "sanity": ["tests/test_sanity.py"],
    # BETA-CIERRE WS-H: ficheros de test a nivel raiz que la corrida por suites no
    # recogia (test_version_sync es un invariante de release: la version del exe debe
    # cuadrar con pyproject).
    "root": [
        "tests/test_version_sync.py",
        "tests/test_prompt_budget.py",
        "tests/test_neighborhood.py",
        "tests/test_positioning_copy.py",
        "tests/test_ws_m_window_fit.py",
        "tests/test_ws_i_packaging.py",
        "tests/test_ws_o_logging.py",
        # BETA-AUDIT-03: el proyecto de ejemplo que viaja en el zip es la primera
        # impresión de todo tester; esta guarda impide que vuelva a degradarse.
        "tests/test_beta_audit_ejemplo_curado.py",
        # BETA-AUDIT-14: ata el inventario de módulos sin superficie a su tabla.
        "tests/test_beta_audit_unreachable_inventory.py",
    ],
}

# Slow suites that get skipped with --fast (dev loop). El gate completo NO usa --fast.
FAST_SKIP = {"ui", "qa", "desktop"}

# Suites cuyo directorio se ejecuta POR-FICHERO en subprocesos separados
# (BETA-CIERRE WS-H): correr tests/desktop entero en un solo pytest SEGFAULTEA
# (fragilidad PySide6/Qt con muchos widgets en un interprete). El sharding aisla el
# fallo y da una puerta verde REAL para la superficie viva del producto.
SHARDED_SUITES = {"desktop"}


def _clean_env() -> dict[str, str]:
    """Return os.environ copy suitable for subprocess (all str values)."""
    import os
    return dict(os.environ)


def _pytest_env() -> dict[str, str]:
    """Environment for pytest subprocesses.

    Preserve an existing PYTHONPATH (needed in WSL/Hermes when pytest and other
    project dependencies are provided by the repo venv's site-packages) while
    ensuring the workspace itself has priority.
    """
    import os

    env = _clean_env()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(WORKSPACE) if not existing else f"{WORKSPACE}{os.pathsep}{existing}"
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    return env


def run_suite(label: str, paths: list[str], timeout: int = 600) -> tuple[bool, float, int]:
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", *paths]
    env = _pytest_env()
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


def run_suite_sharded(label: str, dir_path: str, timeout: int = 300) -> tuple[bool, float, int]:
    """Ejecuta cada ``test_*.py`` del directorio en su PROPIO subproceso y agrega.

    BETA-CIERRE WS-H: correr ``tests/desktop`` entero en un solo pytest segfaultea
    (Qt); por-fichero aisla el fallo y da una puerta verde fiable de la superficie viva.
    """
    files = sorted((WORKSPACE / dir_path).glob("test_*.py"))
    if not files:
        print(f"  [{label}] (sin ficheros en {dir_path})")
        return True, 0.0, 0
    all_ok = True
    total_count = 0
    failed_files: list[str] = []
    t0 = time.perf_counter()
    for f in files:
        rel = f.relative_to(WORKSPACE).as_posix()
        ok, _, count = run_suite(f"{label}:{f.name}", [rel], timeout=timeout)
        if not ok:
            all_ok = False
            failed_files.append(f.name)
        if count > 0:
            total_count += count
    elapsed = time.perf_counter() - t0
    if failed_files:
        print(f"  [{label}] {len(failed_files)} fichero(s) con fallos: {', '.join(failed_files)}")
    return all_ok, elapsed, total_count


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
        if suite in SHARDED_SUITES:
            ok, elapsed, count = run_suite_sharded(suite, paths[0])
        else:
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
