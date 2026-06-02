"""Integration tests for B10-T04: domain, layer, and advanced config CLI commands."""

import json
import os
import shlex
from tests._helpers import _split_cli
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parent.parent.parent


def _cli(args: str, project: Path | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "narrative_architect"]
    if project is not None:
        cmd += ["--project", str(project)]
    cmd += _split_cli(args)
    env = {**os.environ, "PYTHONPATH": str(WORKSPACE)}
    return subprocess.run(
        cmd, cwd=cwd or WORKSPACE, capture_output=True, text=True,
        timeout=30, env=env,
    )


def _entity_id(stdout: str) -> str:
    start = stdout.index("(") + 1
    end = stdout.index(")")
    return stdout[start:end]


def _relation_id(stdout: str) -> str:
    start = stdout.index("'") + 1
    end = stdout.index("'", start)
    return stdout[start:end]


@pytest.fixture(autouse=True)
def _clean_workspace_session() -> None:
    session_file = WORKSPACE / ".narrative-session.json"
    try:
        session_file.unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def project_file(tmp_path: Path) -> Path:
    proj = tmp_path / "test.json"
    r = _cli(f'project create "Test" --path {proj}')
    assert r.returncode == 0, r.stderr
    return proj


# ═══ Domain ═══════════════════════════════════════════════════════

class TestDomainCLI:
    def test_domain_list(self, project_file):
        r = _cli("domain list", project=project_file)
        assert r.returncode == 0
        assert "Domains (5)" in r.stdout

    def test_domain_show(self, project_file):
        r = _cli("domain show mundo", project=project_file)
        assert r.returncode == 0
        assert "Domain: mundo" in r.stdout

    def test_domain_show_invalid(self, project_file):
        r = _cli("domain show invalido", project=project_file)
        assert r.returncode != 0


# ═══ Layer ════════════════════════════════════════════════════════

class TestLayerCLI:
    def test_layer_list(self, project_file):
        r = _cli("layer list", project=project_file)
        assert r.returncode == 0
        assert "Layers (16)" in r.stdout

    def test_layer_list_all(self, project_file):
        _cli("layer hide layer_premisa", project=project_file)
        r = _cli("layer list --all", project=project_file)
        assert r.returncode == 0
        assert "Layers (16)" in r.stdout

    def test_layer_create(self, project_file):
        r = _cli('layer create "Custom Layer"', project=project_file)
        assert r.returncode == 0
        assert "created" in r.stdout.lower()
        r2 = _cli("layer list --all", project=project_file)
        assert "Layers (17)" in r2.stdout

    def test_layer_hide_and_unhide(self, project_file):
        _cli("layer hide layer_premisa", project=project_file)
        r = _cli("layer list", project=project_file)
        assert "Layers (15)" in r.stdout
        _cli("layer unhide layer_premisa", project=project_file)
        r2 = _cli("layer list", project=project_file)
        assert "Layers (16)" in r2.stdout

    def test_layer_reorder(self, project_file):
        r = _cli("layer reorder layer_premisa 100", project=project_file)
        assert r.returncode == 0

    def test_layer_show(self, project_file):
        r = _cli("layer show layer_geografia", project=project_file)
        assert r.returncode == 0
        assert "layer_geografia" in r.stdout

    def test_layer_edit(self, project_file):
        r = _cli('layer edit layer_premisa --name "Nuevo nombre"', project=project_file)
        assert r.returncode == 0
        assert "updated" in r.stdout.lower()


# ═══ Entity — domain/layer assignment ════════════════════════════

class TestEntityDomainLayerCLI:
    def test_assign_domain(self, project_file):
        r = _cli('entity create "Gandalf" --type personaje', project=project_file)
        eid = _entity_id(r.stdout)
        r2 = _cli(f"entity assign-domain {eid} mundo", project=project_file)
        assert r2.returncode == 0

    def test_assign_domain_invalid(self, project_file):
        r = _cli('entity create "Gandalf" --type personaje', project=project_file)
        eid = _entity_id(r.stdout)
        r2 = _cli(f"entity assign-domain {eid} invalido", project=project_file)
        assert r2.returncode != 0

    def test_remove_domain(self, project_file):
        r = _cli('entity create "Gandalf" --type personaje', project=project_file)
        eid = _entity_id(r.stdout)
        _cli(f"entity assign-domain {eid} mundo", project=project_file)
        r2 = _cli(f"entity remove-domain {eid} mundo", project=project_file)
        assert r2.returncode == 0

    def test_assign_layer(self, project_file):
        r = _cli('entity create "Tierra Media" --type localizacion', project=project_file)
        eid = _entity_id(r.stdout)
        r2 = _cli(f"entity assign-layer {eid} layer_geografia", project=project_file)
        assert r2.returncode == 0

    def test_assign_layer_invalid(self, project_file):
        r = _cli('entity create "Test" --type nota', project=project_file)
        eid = _entity_id(r.stdout)
        r2 = _cli(f"entity assign-layer {eid} no_existe", project=project_file)
        assert r2.returncode != 0

    def test_remove_layer(self, project_file):
        r = _cli('entity create "Tierra Media" --type localizacion', project=project_file)
        eid = _entity_id(r.stdout)
        _cli(f"entity assign-layer {eid} layer_geografia", project=project_file)
        r2 = _cli(f"entity remove-layer {eid} layer_geografia", project=project_file)
        assert r2.returncode == 0


# ═══ Relation — layer assignment ═════════════════════════════════

class TestRelationLayerCLI:
    def test_assign_layer(self, project_file):
        r1 = _cli('entity create "A" --type personaje', project=project_file)
        eid_a = _entity_id(r1.stdout)
        r2 = _cli('entity create "B" --type personaje', project=project_file)
        eid_b = _entity_id(r2.stdout)
        r3 = _cli(f"relation create {eid_a} {eid_b} --type esta_relacionado_con", project=project_file)
        rid = _relation_id(r3.stdout)
        r4 = _cli(f"relation assign-layer {rid} layer_historia", project=project_file)
        assert r4.returncode == 0

    def test_remove_layer(self, project_file):
        r1 = _cli('entity create "A" --type personaje', project=project_file)
        eid_a = _entity_id(r1.stdout)
        r2 = _cli('entity create "B" --type personaje', project=project_file)
        eid_b = _entity_id(r2.stdout)
        r3 = _cli(f"relation create {eid_a} {eid_b} --type esta_relacionado_con", project=project_file)
        rid = _relation_id(r3.stdout)
        _cli(f"relation assign-layer {rid} layer_historia", project=project_file)
        r4 = _cli(f"relation remove-layer {rid} layer_historia", project=project_file)
        assert r4.returncode == 0


# ═══ Advanced config ═════════════════════════════════════════════

class TestAdvancedConfigCLI:
    def test_show(self, project_file):
        r = _cli("project config advanced show", project=project_file)
        assert r.returncode == 0
        assert "Advanced Configuration" in r.stdout

    def test_set_and_get(self, project_file):
        r = _cli('project config advanced set primary_genre "fantasía épica"', project=project_file)
        assert r.returncode == 0
        r2 = _cli("project config advanced get primary_genre", project=project_file)
        assert r2.returncode == 0
        assert "fantasía" in r2.stdout

    def test_set_array(self, project_file):
        r = _cli('project config advanced set subgenres \'["alta fantasía"]\'', project=project_file)
        assert r.returncode == 0
        r2 = _cli("project config advanced get subgenres", project=project_file)
        assert r2.returncode == 0
        assert "alta fantasía" in r2.stdout


# ═══ Entity list filters ═════════════════════════════════════════

class TestEntityListFilters:
    def test_filter_by_domain_id(self, project_file):
        r = _cli('entity create "Gandalf" --type personaje', project=project_file)
        eid = _entity_id(r.stdout)
        _cli(f"entity assign-domain {eid} mundo", project=project_file)
        r2 = _cli("entity list --domain-id mundo", project=project_file)
        assert r2.returncode == 0
        assert "Gandalf" in r2.stdout

    def test_filter_by_layer_id(self, project_file):
        r = _cli('entity create "Moria" --type localizacion', project=project_file)
        eid = _entity_id(r.stdout)
        _cli(f"entity assign-layer {eid} layer_geografia", project=project_file)
        r2 = _cli("entity list --layer-id layer_geografia", project=project_file)
        assert r2.returncode == 0
        assert "Moria" in r2.stdout


# ═══ Gallery filters ═════════════════════════════════════════════

class TestGalleryFilters:
    def test_gallery_filter_domain_id(self, project_file):
        r = _cli('entity create "Gandalf" --type personaje', project=project_file)
        eid = _entity_id(r.stdout)
        _cli(f"entity assign-domain {eid} mundo", project=project_file)
        r2 = _cli("gallery personajes --domain-id mundo", project=project_file)
        assert r2.returncode == 0
        assert "Gandalf" in r2.stdout

    def test_gallery_filter_layer_id(self, project_file):
        r = _cli('entity create "Gondor" --type localizacion', project=project_file)
        eid = _entity_id(r.stdout)
        _cli(f"entity assign-layer {eid} layer_geografia", project=project_file)
        r2 = _cli("gallery localizaciones --layer-id layer_geografia", project=project_file)
        assert r2.returncode == 0
        assert "Gondor" in r2.stdout


# ═══ Entity show --extended ══════════════════════════════════════

class TestEntityShowExtended:
    def test_extended_shows_domain_ids(self, project_file):
        r = _cli('entity create "Gandalf" --type personaje', project=project_file)
        eid = _entity_id(r.stdout)
        _cli(f"entity assign-domain {eid} mundo", project=project_file)
        r2 = _cli(f"entity show {eid} --extended", project=project_file)
        assert r2.returncode == 0
        assert "mundo" in r2.stdout

    def test_extended_shows_layer_ids(self, project_file):
        r = _cli('entity create "Moria" --type localizacion', project=project_file)
        eid = _entity_id(r.stdout)
        _cli(f"entity assign-layer {eid} layer_geografia", project=project_file)
        r2 = _cli(f"entity show {eid} --extended", project=project_file)
        assert r2.returncode == 0
        assert "Geografía" in r2.stdout
