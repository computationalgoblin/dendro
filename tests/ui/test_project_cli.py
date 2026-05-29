"""
Tests for project CLI commands (B07-T01).

Covers: project create, open, save, close, info, config get/set,
SessionContext, --project flag, type conversion, error handling.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from packages.ui.cli import SessionContext, convert_config_value

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


WORKSPACE = Path(__file__).resolve().parent.parent.parent


def _cli(args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run ``python -m narrative_architect`` with *args* and return the result.

    Default *cwd* is the workspace root so that ``narrative_architect/`` is
    discoverable.  Pass an explicit *cwd* only when testing session-file
    behaviour (PYTHONPATH is set so the entrypoint is always found).
    """
    cmd = [sys.executable, "-m", "narrative_architect"] + args.split()
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
def tmp_project_path(tmp_path: Path) -> Path:
    """Return a temp path for a project file."""
    return tmp_path / "test_project.json"


@pytest.fixture
def session(tmp_path: Path) -> SessionContext:
    """Return a SessionContext using a temp dir."""
    return SessionContext(session_file=tmp_path / ".narrative-session.json")


# ---------------------------------------------------------------------------
# SessionContext
# ---------------------------------------------------------------------------


class TestSessionContext:
    def test_get_none_when_no_file(self, session: SessionContext) -> None:
        assert session.get_project_path() is None

    def test_set_and_get(self, session: SessionContext) -> None:
        session.set_project_path(Path("/tmp/my_project.json"))
        assert session.get_project_path() == Path("/tmp/my_project.json")

    def test_clear_removes_file(self, session: SessionContext) -> None:
        session.set_project_path(Path("/tmp/my_project.json"))
        session.clear()
        assert session.get_project_path() is None

    def test_clear_when_no_file_is_idempotent(self, session: SessionContext) -> None:
        session.clear()  # should not raise

    def test_overwrite(self, session: SessionContext) -> None:
        session.set_project_path(Path("/tmp/a.json"))
        session.set_project_path(Path("/tmp/b.json"))
        assert session.get_project_path() == Path("/tmp/b.json")


# ---------------------------------------------------------------------------
# convert_config_value
# ---------------------------------------------------------------------------


class TestConvertConfigValue:
    def test_bool_true(self) -> None:
        assert convert_config_value("true") is True
        assert convert_config_value("True") is True
        assert convert_config_value("TRUE") is True

    def test_bool_false(self) -> None:
        assert convert_config_value("false") is False
        assert convert_config_value("False") is False

    def test_integer(self) -> None:
        assert convert_config_value("42") == 42
        assert convert_config_value("-10") == -10
        assert convert_config_value("0") == 0

    def test_float(self) -> None:
        assert convert_config_value("3.14") == 3.14
        assert convert_config_value("-0.5") == -0.5

    def test_json_dict(self) -> None:
        assert convert_config_value('{"key": "val"}') == {"key": "val"}

    def test_json_list(self) -> None:
        assert convert_config_value('[1, 2, 3]') == [1, 2, 3]

    def test_json_invalid_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            convert_config_value("{mal")

    def test_string_fallback(self) -> None:
        assert convert_config_value("hello") == "hello"
        assert convert_config_value("dark_mode") == "dark_mode"


# ---------------------------------------------------------------------------
# CLI integration tests (subprocess)
# ---------------------------------------------------------------------------


class TestProjectCreate:
    def test_create_with_path_creates_file(self, tmp_project_path: Path) -> None:
        r = _cli(f'project create "TestWorld" --path {tmp_project_path}')
        assert r.returncode == 0, r.stderr
        assert tmp_project_path.exists()
        assert "TestWorld" in r.stdout

    def test_create_without_path_does_not_create_project_file(self, tmp_path: Path) -> None:
        r = _cli('project create "Ephemeral"', cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        # Session file is created, but NO project JSON file is created.
        project_files = [f for f in tmp_path.glob("*.json")
                         if f.name != ".narrative-session.json"]
        assert len(project_files) == 0, f"Unexpected files: {project_files}"


class TestProjectOpenAndInfo:
    def test_create_open_info_roundtrip(self, tmp_project_path: Path) -> None:
        _cli(f'project create "MyWorld" --path {tmp_project_path}')
        r_open = _cli(f"project open {tmp_project_path}")
        assert r_open.returncode == 0, r_open.stderr

        r_info = _cli("project info")
        assert r_info.returncode == 0, r_info.stderr
        assert "MyWorld" in r_info.stdout
        assert "Entities:      0" in r_info.stdout
        assert "Language:      es" in r_info.stdout

    def test_open_nonexistent_file(self) -> None:
        r = _cli("project open /tmp/nonexistent_file_xyz.json")
        assert r.returncode != 0


class TestProjectSaveClose:
    def test_save_after_create_persists(self, tmp_path: Path) -> None:
        """Create with --path saves; open again and info is the same."""
        proj_file = tmp_path / "save_test.json"
        _cli(f'project create "SaveMe" --path {proj_file}')
        _cli(f"project open {proj_file}")

        # Save again to same path
        r_save = _cli(f"project save {proj_file}")
        assert r_save.returncode == 0, r_save.stderr

        # Reopen and verify
        _cli(f"project open {proj_file}")
        r_info = _cli("project info")
        assert "SaveMe" in r_info.stdout

    def test_close_clears_session(self, tmp_project_path: Path) -> None:
        _cli(f'project create "CloseMe" --path {tmp_project_path}')
        _cli("project close")
        # Without session, info should fail
        r = _cli("project info")
        assert r.returncode != 0
        assert "No active project" in r.stderr or "No active project" in r.stdout


class TestProjectConfig:
    def test_config_get_set_string_roundtrip(self, tmp_project_path: Path) -> None:
        _cli(f'project create "ConfigTest" --path {tmp_project_path}')
        _cli(f"project open {tmp_project_path}")

        r_set = _cli("project config set general.theme cyberpunk")
        assert r_set.returncode == 0, r_set.stderr

        r_get = _cli("project config get general.theme")
        assert r_get.returncode == 0, r_get.stderr
        assert "cyberpunk" in r_get.stdout

    def test_config_get_set_bool_roundtrip(self, tmp_project_path: Path) -> None:
        _cli(f'project create "BoolTest" --path {tmp_project_path}')
        _cli(f"project open {tmp_project_path}")

        _cli("project config set ai.enabled true")
        r_get = _cli("project config get ai.enabled")
        assert "True" in r_get.stdout

        _cli("project config set ai.enabled false")
        r_get = _cli("project config get ai.enabled")
        assert "False" in r_get.stdout

    def test_config_set_invalid_json_error(self, tmp_project_path: Path) -> None:
        _cli(f'project create "JSONTest" --path {tmp_project_path}')
        _cli(f"project open {tmp_project_path}")

        r = _cli("project config set general.tags {bad")
        assert r.returncode != 0
        assert "Invalid JSON" in r.stderr or "error" in r.stderr.lower()

    def test_config_set_json_list(self, tmp_project_path: Path) -> None:
        _cli(f'project create "ListTest" --path {tmp_project_path}')
        _cli(f"project open {tmp_project_path}")

        r_set = _cli('project config set general.tags \'["scifi","noir"]\'')
        assert r_set.returncode == 0, r_set.stderr

        r_get = _cli("project config get general.tags")
        assert r_get.returncode == 0, r_get.stderr
        assert "scifi" in r_get.stdout

    def test_config_set_integer(self, tmp_project_path: Path) -> None:
        _cli(f'project create "IntTest" --path {tmp_project_path}')
        _cli(f"project open {tmp_project_path}")

        _cli("project config set primary_language 42")
        r_get = _cli("project config get primary_language")
        # 42 was converted to int, then setattr; print() renders it as "42"
        assert "42" in r_get.stdout


class TestProjectFlag:
    def test_dash_project_overrides_session(self, tmp_path: Path) -> None:
        """--project flag should work even without an active session."""
        proj1 = tmp_path / "proj1.json"
        proj2 = tmp_path / "proj2.json"

        _cli(f'project create "One" --path {proj1}')
        _cli(f'project create "Two" --path {proj2}')

        # No session active — use --project
        r = _cli(f"--project {proj1} project info")
        assert r.returncode == 0, r.stderr
        assert "One" in r.stdout

        r = _cli(f"--project {proj2} project info")
        assert r.returncode == 0, r.stderr
        assert "Two" in r.stdout

    def test_no_project_no_session_error(self) -> None:
        r = _cli("project info")
        assert r.returncode != 0
        assert "No active project" in r.stderr or "No active project" in r.stdout


class TestHelp:
    def test_help_root(self) -> None:
        r = _cli("--help")
        assert r.returncode == 0
        assert "narrative-architect" in r.stdout
        assert "--project" in r.stdout

    def test_help_project(self) -> None:
        r = _cli("project --help")
        assert r.returncode == 0
        assert "create" in r.stdout
        assert "open" in r.stdout
        assert "config" in r.stdout

    def test_help_config(self) -> None:
        r = _cli("project config --help")
        assert r.returncode == 0
        assert "get" in r.stdout
        assert "set" in r.stdout
