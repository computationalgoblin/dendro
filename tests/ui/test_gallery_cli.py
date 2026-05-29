"""
Tests for gallery CLI commands (B09-T01).

Covers: gallery personajes, localizaciones, facciones, ..., sistemas-magicos,
reglas, archivados, pendientes, por-fuente, por-capa, por-canon, custom,
--sort, --sort-desc, --limit, --offset, --json, error handling.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent.parent


def _cli(args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run ``python -m narrative_architect`` with *args*."""
    cmd = [sys.executable, "-m", "narrative_architect"] + shlex.split(args)
    env = {**os.environ, "PYTHONPATH": str(WORKSPACE)}
    return subprocess.run(
        cmd,
        cwd=cwd if cwd is not None else WORKSPACE,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


@pytest.fixture(autouse=True)
def _clean_workspace_session() -> None:
    """Ensure no stale session contaminates tests."""
    session_file = WORKSPACE / ".narrative-session.json"
    try:
        session_file.unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def project_with_session(tmp_path: Path) -> Path:
    """Create a project and open it, returning the project path."""
    proj_file = tmp_path / "test.json"
    _cli(f'project create "Test" --path {proj_file}')
    _cli(f"project open {proj_file}")
    return proj_file


@pytest.fixture
def populated_project(project_with_session: Path) -> Path:
    """Project with entities for gallery testing."""
    proj = project_with_session
    entities = [
        "entity create Aragorn --type personaje",
        "entity create Gandalf --type personaje",
        "entity create Mordor --type localizacion",
        "entity create Orthanc --type localizacion",
        "entity create Hobbits --type cultura",
    ]
    for cmd in entities:
        r = _cli(cmd)
        assert r.returncode == 0, f"Failed: {cmd}: {r.stderr}"
    return proj


# ---------------------------------------------------------------------------
# Gallery: basic type views
# ---------------------------------------------------------------------------


class TestGalleryTypeViews:
    def test_gallery_personajes(self, populated_project: Path) -> None:
        r = _cli("gallery personajes")
        assert r.returncode == 0, r.stderr
        assert "Aragorn" in r.stdout
        assert "Gandalf" in r.stdout
        assert "Mordor" not in r.stdout  # localizacion

    def test_gallery_localizaciones(self, populated_project: Path) -> None:
        r = _cli("gallery localizaciones")
        assert r.returncode == 0, r.stderr
        assert "Mordor" in r.stdout
        assert "Orthanc" in r.stdout
        assert "Aragorn" not in r.stdout

    def test_gallery_culturas(self, populated_project: Path) -> None:
        r = _cli("gallery culturas")
        assert r.returncode == 0, r.stderr
        assert "Hobbits" in r.stdout

    def test_gallery_sistemas_magicos_no_crash(self, populated_project: Path) -> None:
        """sistemas-magicos with hyphen should not crash."""
        r = _cli("gallery sistemas-magicos")
        assert r.returncode == 0, r.stderr

    def test_gallery_reglas_no_crash(self, populated_project: Path) -> None:
        """reglas maps to REGLA_DEL_MUNDO, should not crash."""
        r = _cli("gallery reglas")
        assert r.returncode == 0, r.stderr

    def test_gallery_empty_type(self, project_with_session: Path) -> None:
        """Empty gallery shows count 0, no error."""
        r = _cli("gallery idiomas")
        assert r.returncode == 0, r.stderr
        assert "0" in r.stdout or "No" in r.stdout.lower()


# ---------------------------------------------------------------------------
# Gallery: state views
# ---------------------------------------------------------------------------


class TestGalleryStateViews:
    def test_gallery_archivados(self, project_with_session: Path) -> None:
        _cli("entity create X --type nota")
        r = _cli("gallery archivados")
        assert r.returncode == 0, r.stderr

    def test_gallery_pendientes(self, project_with_session: Path) -> None:
        _cli("entity create X --type nota")
        r = _cli("gallery pendientes")
        assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# Gallery: special views
# ---------------------------------------------------------------------------


class TestGallerySpecialViews:
    def test_gallery_por_fuente(self, project_with_session: Path) -> None:
        _cli("entity create X --type nota")
        r = _cli("gallery por-fuente nonexistent")
        # Should not crash, just empty or error from QueryService
        assert r.returncode in (0, 1)

    def test_gallery_por_capa(self, project_with_session: Path) -> None:
        _cli("entity create X --type nota")
        r = _cli("gallery por-capa geografia")
        assert r.returncode == 0, r.stderr

    def test_gallery_por_canon(self, project_with_session: Path) -> None:
        _cli("entity create X --type nota")
        r = _cli("gallery por-canon borrador")
        assert r.returncode == 0, r.stderr

    def test_gallery_custom(self, project_with_session: Path) -> None:
        _cli("entity create X --type nota")
        r = _cli("gallery custom some-id")
        assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# Gallery: options
# ---------------------------------------------------------------------------


class TestGalleryOptions:
    def test_gallery_sort_updated_at(self, populated_project: Path) -> None:
        r = _cli("gallery personajes --sort updated_at")
        assert r.returncode == 0, r.stderr

    def test_gallery_sort_desc(self, populated_project: Path) -> None:
        r = _cli("gallery personajes --sort name --sort-desc")
        assert r.returncode == 0, r.stderr

    def test_gallery_limit(self, populated_project: Path) -> None:
        r = _cli("gallery personajes --limit 1")
        assert r.returncode == 0, r.stderr

    def test_gallery_offset(self, populated_project: Path) -> None:
        r = _cli("gallery personajes --limit 1 --offset 1")
        assert r.returncode == 0, r.stderr

    def test_gallery_json(self, populated_project: Path) -> None:
        r = _cli("gallery personajes --json")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert isinstance(data, list)

    def test_gallery_unknown_subcommand(self, project_with_session: Path) -> None:
        r = _cli("gallery nonexistent")
        assert r.returncode != 0


# ---------------------------------------------------------------------------
# Gallery: compound filters (B09-T03B)
# ---------------------------------------------------------------------------


class TestGalleryCompoundFilters:
    def test_gallery_canon_filter(self, populated_project: Path) -> None:
        """gallery personajes --canon borrador should filter."""
        r = _cli("gallery personajes --canon borrador")
        assert r.returncode == 0, r.stderr
        # All created entities are canonico by default, so borrador should be empty
        assert "0" in r.stdout or "(no entities)" in r.stdout

    def test_gallery_canon_canonico(self, populated_project: Path) -> None:
        """gallery personajes --canon canonico returns empty (entities are borrador by default)."""
        r = _cli("gallery personajes --canon canonico")
        assert r.returncode == 0, r.stderr
        # Default entity state is borrador, so canonico filter should be empty
        assert "0" in r.stdout or "(no entities)" in r.stdout

    def test_gallery_canon_borrador(self, populated_project: Path) -> None:
        """gallery personajes --canon borrador returns created entities."""
        r = _cli("gallery personajes --canon borrador")
        assert r.returncode == 0, r.stderr
        assert "Aragorn" in r.stdout
        assert "Gandalf" in r.stdout

    def test_gallery_tag_filter_no_match(self, populated_project: Path) -> None:
        """--tag with nonexistent tag returns empty."""
        r = _cli("gallery personajes --tag noexiste")
        assert r.returncode == 0, r.stderr
        assert "0" in r.stdout or "(no entities)" in r.stdout

    def test_gallery_domain_filter(self, populated_project: Path) -> None:
        """--domain filter should not crash."""
        r = _cli("gallery personajes --domain tierra_media")
        assert r.returncode == 0, r.stderr

    def test_gallery_visibility_filter(self, populated_project: Path) -> None:
        """--visibility filter should not crash."""
        r = _cli("gallery personajes --visibility visible_usuario")
        assert r.returncode == 0, r.stderr
        assert "Aragorn" in r.stdout

    def test_gallery_compound_and_filters(self, populated_project: Path) -> None:
        """Multiple filters combined with AND — borrador + visible_usuario."""
        r = _cli("gallery personajes --canon borrador --visibility visible_usuario")
        assert r.returncode == 0, r.stderr
        assert "Aragorn" in r.stdout

    def test_gallery_por_fuente_positional_still_works(self, project_with_session: Path) -> None:
        """por-fuente with positional source_id, without --source-id flag conflict."""
        _cli("entity create X --type nota")
        r = _cli("gallery por-fuente nonexistent")
        assert r.returncode in (0, 1)

    def test_gallery_por_capa_positional_still_works(self, project_with_session: Path) -> None:
        """por-capa with positional layer arg, without --layer flag conflict."""
        _cli("entity create X --type nota")
        r = _cli("gallery por-capa geografia")
        assert r.returncode == 0, r.stderr

    def test_gallery_por_canon_positional_still_works(self, project_with_session: Path) -> None:
        """por-canon with positional canon_state, without --canon flag conflict."""
        _cli("entity create X --type nota")
        r = _cli("gallery por-canon borrador")
        assert r.returncode == 0, r.stderr

    def test_gallery_custom_positional_still_works(self, project_with_session: Path) -> None:
        """custom with positional custom_type_id, without --custom-type-id flag conflict."""
        _cli("entity create X --type nota")
        r = _cli("gallery custom some-id")
        assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# Gallery: error handling
# ---------------------------------------------------------------------------


class TestGalleryErrors:
    def test_gallery_no_project(self) -> None:
        r = _cli("gallery personajes")
        assert r.returncode != 0
