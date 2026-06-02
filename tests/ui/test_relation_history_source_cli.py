"""
Tests for relation, history, and source CLI commands (B07-T03).
"""

from __future__ import annotations

import os
import shlex
from tests._helpers import _split_cli
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent.parent


def _cli(args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "narrative_architect"] + _split_cli(args)
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
    session_file = WORKSPACE / ".narrative-session.json"
    try:
        session_file.unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def populated_project(tmp_path: Path) -> tuple[Path, str, str]:
    """Create a project with two entities, return (path, eid1, eid2)."""
    proj = tmp_path / "test.json"
    _cli(f'project create "Test" --path {proj}')
    _cli(f"project open {proj}")

    r1 = _cli("entity create Alpha --type personaje")
    eid1 = r1.stdout.split("(")[1].split(")")[0]

    r2 = _cli("entity create Beta --type localizacion")
    eid2 = r2.stdout.split("(")[1].split(")")[0]

    return proj, eid1, eid2


# ---------------------------------------------------------------------------
# Relation tests
# ---------------------------------------------------------------------------


class TestRelationCreate:
    def test_create_minimal(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        r = _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        assert r.returncode == 0, r.stderr
        assert "es_aliado_de" in r.stdout

    def test_create_with_desc(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        r = _cli(
            f"relation create {eid1} {eid2} --type pertenece_a "
            "--desc 'Strong bond'"
        )
        assert r.returncode == 0, r.stderr

    def test_create_invalid_type(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        r = _cli(f"relation create {eid1} {eid2} --type nonexistent")
        assert r.returncode != 0

    def test_create_nonexistent_entity(self, populated_project: tuple) -> None:
        _, eid1, _ = populated_project
        r = _cli(f"relation create {eid1} deadbeef-dead-beef-dead-beefdeadbeef --type es_aliado_de")
        assert r.returncode != 0


class TestRelationEdit:
    def test_edit_desc(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        r = _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        rid = r.stdout.split("'")[1]

        r2 = _cli(f"relation edit {rid} --desc 'Updated description'")
        assert r2.returncode == 0, r2.stderr

    def test_edit_no_fields(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        r = _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        rid = r.stdout.split("'")[1]
        r2 = _cli(f"relation edit {rid}")
        assert r2.returncode != 0


class TestRelationArchive:
    def test_archive_and_list(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        r = _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        rid = r.stdout.split("'")[1]
        _cli(f"relation archive {rid}")

        r_list = _cli(f"relation list --entity {eid1}")
        assert "[ARCHIVED]" in r_list.stdout


class TestRelationList:
    def test_list_empty(self, populated_project: tuple) -> None:
        r = _cli("relation list")
        assert r.returncode == 0
        assert "No relations found" in r.stdout

    def test_list_after_create(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        _cli(f"relation create {eid2} {eid1} --type pertenece_a")

        r = _cli("relation list")
        assert "2 total" in r.stdout

    def test_list_by_entity(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        _cli(f"relation create {eid1} {eid2} --type es_aliado_de")

        r = _cli(f"relation list --entity {eid1}")
        assert r.returncode == 0
        assert "1 total" in r.stdout

    def test_list_by_type(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        _cli(f"relation create {eid2} {eid1} --type pertenece_a")

        r = _cli("relation list --type es_aliado_de")
        assert "es_aliado_de" in r.stdout
        assert "pertenece_a" not in r.stdout


class TestRelationShow:
    def test_show(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        r = _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        rid = r.stdout.split("'")[1]

        r_show = _cli(f"relation show {rid}")
        assert r_show.returncode == 0
        assert "es_aliado_de" in r_show.stdout
        assert eid1 in r_show.stdout
        assert eid2 in r_show.stdout

    def test_show_extended(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        r = _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        rid = r.stdout.split("'")[1]
        r_show = _cli(f"relation show {rid} --extended")
        assert r_show.returncode == 0, r_show.stderr
        assert "Intensity:" in r_show.stdout
        assert "Certainty:" in r_show.stdout

    def test_show_json(self, populated_project: tuple) -> None:
        import json
        _, eid1, eid2 = populated_project
        r = _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        rid = r.stdout.split("'")[1]
        r_show = _cli(f"relation show {rid} --json")
        assert r_show.returncode == 0, r_show.stderr
        data = json.loads(r_show.stdout)
        assert "source_name" in data
        assert "target_name" in data


# ---------------------------------------------------------------------------
# History tests
# ---------------------------------------------------------------------------


class TestHistory:
    def test_history_entity_has_events(self, populated_project: tuple) -> None:
        _, eid1, _ = populated_project
        # After entity creation in the fixture, history should record it
        r = _cli(f"history entity {eid1}")
        assert r.returncode == 0, r.stderr
        # B07-T04: HistoryService is now injected, so should have at least
        # the CREACION_ENTIDAD event from the fixture's entity creation.
        assert "creacion_entidad" in r.stdout.lower()

    def test_history_entity_after_mutations(self, populated_project: tuple) -> None:
        _, eid1, _ = populated_project
        _cli(f"entity edit {eid1} --brief 'Updated for history test'")

        r = _cli(f"history entity {eid1} --limit 10")
        assert r.returncode == 0, r.stderr
        assert "edicion_entidad" in r.stdout.lower()

    def test_history_after_archive(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        _cli(f"entity archive {eid2}")

        r = _cli(f"history entity {eid2} --limit 10")
        assert "archivado_entidad" in r.stdout.lower()

    def test_history_recent_has_events(self, populated_project: tuple) -> None:
        # At minimum the 2 entity creations from the fixture
        r = _cli("history recent --limit 10")
        assert r.returncode == 0, r.stderr
        assert "creacion_entidad" in r.stdout.lower()

    def test_history_relation_create(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        r = _cli("history recent --limit 5")
        assert "creacion_relacion" in r.stdout.lower()

    def test_history_persists_after_close_open(self, tmp_path: Path) -> None:
        proj = tmp_path / "history_persist.json"
        _cli(f'project create "PersistTest" --path {proj}')
        _cli(f"project open {proj}")
        _cli("entity create PersistMe --type objeto")
        _cli("project close")
        _cli(f"project open {proj}")

        r = _cli("history recent --limit 5")
        assert r.returncode == 0, r.stderr
        assert "creacion_entidad" in r.stdout.lower()

    def test_history_entity_nonexistent(self, populated_project: tuple) -> None:
        r = _cli("history entity deadbeef-dead-beef-dead-beefdeadbeef")
        assert r.returncode == 0, r.stderr


# ---------------------------------------------------------------------------
# Source tests
# ---------------------------------------------------------------------------


class TestSourceCreate:
    def test_create_minimal(self, populated_project: tuple) -> None:
        r = _cli("source create Manual --type entrada_manual")
        assert r.returncode == 0, r.stderr
        assert "Manual" in r.stdout

    def test_create_with_fields(self, populated_project: tuple) -> None:
        r = _cli(
            "source create Doc --type documento_importado "
            "--reference 'Book 1' --fragment 'Once upon a time'"
        )
        assert r.returncode == 0, r.stderr

    def test_create_invalid_type(self, populated_project: tuple) -> None:
        r = _cli("source create Bad --type invalid_type")
        assert r.returncode != 0


class TestSourceLink:
    def test_link_entity(self, populated_project: tuple) -> None:
        _, eid1, _ = populated_project
        r = _cli("source create S1 --type entrada_manual")
        sid = r.stdout.split("(")[1].split(")")[0]

        r2 = _cli(f"source link-entity {sid} {eid1}")
        assert r2.returncode == 0, r2.stderr

        r3 = _cli(f"source list --entity {eid1}")
        assert sid in r3.stdout

    def test_link_relation(self, populated_project: tuple) -> None:
        _, eid1, eid2 = populated_project
        r_src = _cli("source create S2 --type entrada_manual")
        sid = r_src.stdout.split("(")[1].split(")")[0]

        r_rel = _cli(f"relation create {eid1} {eid2} --type es_aliado_de")
        rid = r_rel.stdout.split("'")[1]

        r2 = _cli(f"source link-relation {sid} {rid}")
        assert r2.returncode == 0, r2.stderr


class TestSourceList:
    def test_list_empty(self, populated_project: tuple) -> None:
        r = _cli("source list")
        assert r.returncode == 0
        assert "No sources found" in r.stdout

    def test_list_after_create(self, populated_project: tuple) -> None:
        _cli("source create S1 --type entrada_manual")
        _cli("source create S2 --type sesion_rol")
        r = _cli("source list")
        assert "2" in r.stdout.split("\n")[0]


class TestSourceShow:
    def test_show(self, populated_project: tuple) -> None:
        r = _cli("source create ShowMe --type entrada_manual --reference 'ref1'")
        sid = r.stdout.split("(")[1].split(")")[0]

        r_show = _cli(f"source show {sid}")
        assert r_show.returncode == 0
        assert "ShowMe" in r_show.stdout
        assert "ref1" in r_show.stdout


# ---------------------------------------------------------------------------
# --project flag + error cases
# ---------------------------------------------------------------------------


class TestProjectFlag:
    def test_relation_list_with_flag(self, tmp_path: Path) -> None:
        proj = tmp_path / "flag_test.json"
        _cli(f'project create "FlagTest" --path {proj}')
        _cli(f"--project {proj} entity create A --type personaje")
        _cli(f"--project {proj} entity create B --type localizacion")
        r = _cli(f"--project {proj} relation list")
        assert r.returncode == 0


class TestNoSession:
    def test_relation_no_session(self) -> None:
        r = _cli("relation list")
        assert r.returncode != 0

    def test_history_no_session(self) -> None:
        r = _cli("history recent")
        assert r.returncode != 0

    def test_source_no_session(self) -> None:
        r = _cli("source list")
        assert r.returncode != 0
