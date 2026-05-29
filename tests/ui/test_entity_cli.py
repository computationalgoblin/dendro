"""
Tests for entity CLI commands (B07-T02).

Covers: entity create, edit, archive, list, show, search,
--project flag, error handling, enum parsing.
"""

from __future__ import annotations

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


def _entity_id(stdout: str) -> str:
    """Extract the entity ID from a create command's stdout."""
    # Format: Entity 'Name' (uuid) created [type]
    start = stdout.index("(") + 1
    end = stdout.index(")")
    return stdout[start:end]


# ---------------------------------------------------------------------------
# Entity create
# ---------------------------------------------------------------------------


class TestEntityCreate:
    def test_create_minimal(self, project_with_session: Path) -> None:
        r = _cli("entity create Aragorn --type personaje")
        assert r.returncode == 0, r.stderr
        assert "Aragorn" in r.stdout
        assert "personaje" in r.stdout

    def test_create_with_all_fields(self, project_with_session: Path) -> None:
        r = _cli(
            "entity create Frodo --type personaje --brief 'Ring bearer' "
            "--extended 'A hobbit from the Shire' --domain middle-earth"
        )
        assert r.returncode == 0, r.stderr

    def test_create_invalid_type(self, project_with_session: Path) -> None:
        r = _cli("entity create Bad --type nonexistent")
        assert r.returncode != 0

    def test_create_without_session(self) -> None:
        r = _cli("entity create Ghost --type personaje")
        assert r.returncode != 0
        assert "No active project" in (r.stderr + r.stdout)


# ---------------------------------------------------------------------------
# Entity edit
# ---------------------------------------------------------------------------


class TestEntityEdit:
    def test_edit_brief(self, project_with_session: Path) -> None:
        r = _cli("entity create EditMe --type objeto")
        eid = _entity_id(r.stdout)

        r2 = _cli(f"entity edit {eid} --brief 'An edited brief'")
        assert r2.returncode == 0, r2.stderr

        r3 = _cli(f"entity show {eid}")
        assert "An edited brief" in r3.stdout

    def test_edit_multiple_fields(self, project_with_session: Path) -> None:
        r = _cli("entity create Eddie --type personaje")
        eid = _entity_id(r.stdout)

        _cli(f"entity edit {eid} --name Eddie2 --extended 'Long text'")

        r_show = _cli(f"entity show {eid}")
        assert "Eddie2" in r_show.stdout
        assert "Long text" in r_show.stdout

    def test_edit_no_fields_error(self, project_with_session: Path) -> None:
        r = _cli("entity create NoEdit --type objeto")
        eid = _entity_id(r.stdout)
        r2 = _cli(f"entity edit {eid}")
        assert r2.returncode != 0


# ---------------------------------------------------------------------------
# Entity archive
# ---------------------------------------------------------------------------


class TestEntityArchive:
    def test_archive_and_show(self, project_with_session: Path) -> None:
        r = _cli("entity create Dead --type personaje")
        eid = _entity_id(r.stdout)
        _cli(f"entity archive {eid}")

        r_show = _cli(f"entity show {eid}")
        assert r_show.returncode == 0
        assert "archivado" in r_show.stdout.lower()


# ---------------------------------------------------------------------------
# Entity list / filter
# ---------------------------------------------------------------------------


class TestEntityList:
    def test_list_empty(self, project_with_session: Path) -> None:
        r = _cli("entity list")
        assert r.returncode == 0
        assert "No entities found" in r.stdout

    def test_list_after_create(self, project_with_session: Path) -> None:
        _cli("entity create Alpha --type personaje")
        _cli("entity create Beta --type localizacion")
        r = _cli("entity list")
        assert r.returncode == 0
        assert "Alpha" in r.stdout
        assert "Beta" in r.stdout
        assert "2 total" in r.stdout

    def test_filter_by_type(self, project_with_session: Path) -> None:
        _cli("entity create Alpha --type personaje")
        _cli("entity create Beta --type localizacion")
        r = _cli("entity list --type personaje")
        assert "Alpha" in r.stdout
        assert "Beta" not in r.stdout

    def test_filter_by_canon(self, project_with_session: Path) -> None:
        _cli("entity create Alpha --type personaje")
        r = _cli("entity list --canon borrador")
        assert "Alpha" in r.stdout

    def test_filter_invalid_canon(self, project_with_session: Path) -> None:
        r = _cli("entity list --canon NOPE")
        assert r.returncode != 0

    def test_filter_archived(self, project_with_session: Path) -> None:
        r = _cli("entity create ArchiveMe --type objeto")
        eid = _entity_id(r.stdout)
        _cli(f"entity archive {eid}")

        r2 = _cli("entity list")
        # Should show ARCHIVADO marker
        assert "[ARCHIVADO]" in r2.stdout or "archivado" in r2.stdout.lower()


# ---------------------------------------------------------------------------
# Entity show
# ---------------------------------------------------------------------------


class TestEntityShow:
    def test_show_has_required_sections(self, project_with_session: Path) -> None:
        r = _cli("entity create ShowMe --type personaje --brief 'Test'")
        eid = _entity_id(r.stdout)
        r_show = _cli(f"entity show {eid}")
        assert "ID:" in r_show.stdout
        assert "Type:" in r_show.stdout
        assert "Canon:" in r_show.stdout
        assert "Visibility:" in r_show.stdout

    def test_show_extended_has_all_23_fields(self, project_with_session: Path) -> None:
        r = _cli("entity create FullCard --type personaje --brief 'Brief' "
                  "--extended 'Extended' --domain 'midgard'")
        eid = _entity_id(r.stdout)
        r_show = _cli(f"entity show {eid} --extended")
        assert r_show.returncode == 0, r_show.stderr
        assert "Certainty:" in r_show.stdout
        assert "Importance:" in r_show.stdout
        assert "Development:" in r_show.stdout
        assert "Created:" in r_show.stdout
        assert "Updated:" in r_show.stdout
        assert "Incidencias:" in r_show.stdout
        assert "Sugerencias IA:" in r_show.stdout
        assert "Acciones:" in r_show.stdout
        assert "Bloque 12" in r_show.stdout
        assert "Bloque 14" in r_show.stdout

    def test_show_extended_json(self, project_with_session: Path) -> None:
        import json
        r = _cli("entity create JSONTest --type personaje")
        eid = _entity_id(r.stdout)
        r_show = _cli(f"entity show {eid} --json")
        assert r_show.returncode == 0, r_show.stderr
        data = json.loads(r_show.stdout)
        assert data["name"] == "JSONTest"
        assert "relations" in data
        assert "sources" in data
        assert "history" in data

    def test_show_resolves_relation_names(self, project_with_session: Path) -> None:
        r1 = _cli("entity create Gandalf --type personaje")
        gid = _entity_id(r1.stdout)
        r2 = _cli("entity create Frodo --type personaje")
        fid = _entity_id(r2.stdout)
        _cli(f"relation create {gid} {fid} --type es_aliado_de")
        r_show = _cli(f"entity show {gid} --extended")
        assert "Frodo" in r_show.stdout

    def test_show_nonexistent(self, project_with_session: Path) -> None:
        r = _cli("entity show deadbeef-1234")
        assert r.returncode != 0


# ---------------------------------------------------------------------------
# Entity search
# ---------------------------------------------------------------------------


class TestEntitySearch:
    def test_search_finds_entity(self, project_with_session: Path) -> None:
        _cli("entity create FindMe --type personaje --brief 'secret keyword'")
        r = _cli("entity search keyword")
        assert r.returncode == 0
        assert "FindMe" in r.stdout

    def test_search_no_match(self, project_with_session: Path) -> None:
        _cli("entity create NoMatch --type objeto")
        r = _cli("entity search xyznonexistent")
        assert r.returncode == 0
        assert "No entities found" in r.stdout

    def test_search_no_private(self, project_with_session: Path) -> None:
        _cli("entity create Secret --type objeto")
        r = _cli("entity search Secret --no-private")
        assert r.returncode == 0


# ---------------------------------------------------------------------------
# --project flag
# ---------------------------------------------------------------------------


class TestProjectFlag:
    def test_entity_list_with_flag(self, tmp_path: Path) -> None:
        proj = tmp_path / "flag_test.json"
        _cli(f'project create "FlagTest" --path {proj}')
        _cli(f"--project {proj} entity create Alpha --type personaje")
        r = _cli(f"--project {proj} entity list")
        assert r.returncode == 0
        assert "Alpha" in r.stdout
