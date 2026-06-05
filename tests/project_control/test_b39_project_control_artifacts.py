from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


REQUIRED_ROOT_DOCS = [
    "ROADMAP.md",
    "PHASE_CURRENT.md",
    "KNOWN_ISSUES.md",
    "CHANGELOG.md",
]

REQUIRED_SUPPORT_DOCS = [
    "docs/contracts/bloque-39-contrato.md",
    "docs/adr/ADR-001-control-operativo-del-proyecto.md",
    "docs/templates/phase-template.md",
    "docs/templates/ticket-template.md",
    "docs/templates/closure-template.md",
]

REQUIRED_VERIFY_SCRIPTS = [
    "scripts/verify_all.sh",
    "scripts/verify_all.ps1",
]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_b39_required_control_artifacts_exist_and_are_non_empty() -> None:
    for relative_path in [*REQUIRED_ROOT_DOCS, *REQUIRED_SUPPORT_DOCS, *REQUIRED_VERIFY_SCRIPTS]:
        path = ROOT / relative_path
        assert path.exists(), f"Missing B39 artifact: {relative_path}"
        assert path.stat().st_size > 200, f"B39 artifact too small/empty: {relative_path}"


def test_phase_current_declares_single_active_phase_and_scope_boundaries() -> None:
    content = _read("PHASE_CURRENT.md")
    assert "## Fase activa" in content
    assert content.count("## Fase activa") == 1
    assert "## Incluye" in content
    assert "## Excluye" in content
    assert "## Definition of Done" in content
    assert "No avanzar" in content or "Si una petición nueva no encaja" in content
    assert "validación Windows ficticia" in content


def test_roadmap_points_to_authoritative_sources_without_replacing_them() -> None:
    content = _read("ROADMAP.md")
    assert "No sustituye" in content
    assert "docs/contracts/contrato_fases" in content
    assert "Kanban" in content
    assert "PHASE_CURRENT.md" in content
    assert "KNOWN_ISSUES.md" in content


def test_known_issues_keeps_existing_debt_ids_and_windows_gates_visible() -> None:
    content = _read("KNOWN_ISSUES.md")
    for debt_id in [
        "DC-026",
        "DC-027",
        "DC-028",
        "DC-033",
        "DC-034",
        "DC-034-04",
        "DC-045",
        "DC-WIN-B36",
        "DC-WIN-B37",
        "DC-WIN-B38",
    ]:
        assert debt_id in content
    assert "No renumerar" in content
    assert "mitigada no significa resuelta" in content


def test_adr_001_records_kanban_docs_split() -> None:
    content = _read("docs/adr/ADR-001-control-operativo-del-proyecto.md")
    assert "Kanban sigue siendo la fuente de verdad de ejecución" in content
    assert "PHASE_CURRENT.md" in content
    assert "KNOWN_ISSUES.md" in content
    assert "Windows" in content


def test_verify_all_scripts_delegate_to_existing_runners() -> None:
    sh = _read("scripts/verify_all.sh")
    ps1 = _read("scripts/verify_all.ps1")
    for content in [sh, ps1]:
        assert "compileall" in content
        assert "tests/architecture" in content
        assert "scripts/run_all_tests.py" in content
        assert "b39" in content


def test_run_all_tests_registers_b39_suite() -> None:
    content = _read("scripts/run_all_tests.py")
    assert '"b39"' in content
    assert "tests/project_control/test_b39_project_control_artifacts.py" in content
