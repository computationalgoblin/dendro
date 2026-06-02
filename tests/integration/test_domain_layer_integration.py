"""Integration tests for B10-T05: gaps not covered by B10-T04.

Covers multi-domain/layer, legacy coexistence, persistence roundtrip,
and regression against B09 output.
"""

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


def _create_entity(project_file, name, etype):
    r = _cli(f"entity create \"{name}\" --type {etype}", project=project_file)
    assert r.returncode == 0, r.stderr
    return _entity_id(r.stdout)


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


# ═══ Multi-domain / multi-layer ═══════════════════════════════════

class TestMultiDomain:
    def test_multi_domain_entity(self, project_file):
        eid = _create_entity(project_file, "Arwen", "personaje")
        _cli(f"entity assign-domain {eid} mundo", project=project_file)
        _cli(f"entity assign-domain {eid} campaña", project=project_file)

        r_mundo = _cli("entity list --domain-id mundo", project=project_file)
        r_campana = _cli("entity list --domain-id campaña", project=project_file)

        assert "Arwen" in r_mundo.stdout
        assert "Arwen" in r_campana.stdout

    def test_multi_layer_entity(self, project_file):
        eid = _create_entity(project_file, "Minas Tirith", "localizacion")
        _cli(f"entity assign-layer {eid} layer_geografia", project=project_file)
        _cli(f"entity assign-layer {eid} layer_historia", project=project_file)

        r_geo = _cli("entity list --layer-id layer_geografia", project=project_file)
        r_hist = _cli("entity list --layer-id layer_historia", project=project_file)

        assert "Minas Tirith" in r_geo.stdout
        assert "Minas Tirith" in r_hist.stdout


# ═══ Legacy coexistence ══════════════════════════════════════════

class TestLegacyCoexistence:
    def test_legacy_domain_filter_still_works(self, project_file):
        """entity list --domain <legacy_string> still finds entities by legacy domain field."""
        import sys
        sys.path.insert(0, str(WORKSPACE))
        from packages.application.project_service import ProjectService
        from packages.domain.entity import NarrativeEntity

        ps = ProjectService()
        ps.open(project_file)
        e = NarrativeEntity.from_dict(
            {"name": "Legacy World", "entity_type": "localizacion", "domain": "tierra_media"}
        )
        ps.active_project.entities.append(e)
        ps.save(project_file)
        ps.close()

        r = _cli("entity list --domain tierra_media", project=project_file)
        assert "Legacy World" in r.stdout

    def test_legacy_layer_filter_still_works(self, project_file):
        """entity list --layer <legacy_string> still finds entities by legacy layers field."""
        from packages.domain.entity import NarrativeEntity
        e = NarrativeEntity.from_dict(
            {"name": "Legacy Area", "entity_type": "localizacion",
             "layers": ["geografia"]}
        )
        # Access the active project directly via file manipulation
        # We'll use the CLI to create with custom fields instead
        r = _cli(
            'entity create "Legacy Area" --type localizacion',
            project=project_file,
        )
        eid = _entity_id(r.stdout)

        # Use Python to set the legacy field
        import sys
        sys.path.insert(0, str(WORKSPACE))
        from packages.application.project_service import ProjectService
        ps = ProjectService()
        ps.open(project_file)
        for e in ps.active_project.entities:
            if e.id == eid:
                e.layers = ["geografia"]
                break
        ps.save(project_file)
        ps.close()

        r = _cli("entity list --layer geografia", project=project_file)
        assert "Legacy Area" in r.stdout

    def test_legacy_and_new_coexist_and(self, project_file):
        """--domain-id mundo AND --domain tierra_media both filter (AND)."""
        eid = _create_entity(project_file, "Gandalf", "personaje")
        _cli(f"entity assign-domain {eid} mundo", project=project_file)

        import sys
        sys.path.insert(0, str(WORKSPACE))
        from packages.application.project_service import ProjectService
        ps = ProjectService()
        ps.open(project_file)
        for e in ps.active_project.entities:
            if e.id == eid:
                e.domain = "tierra_media"
                break
        ps.save(project_file)
        ps.close()

        r = _cli(
            "entity list --domain-id mundo --domain tierra_media",
            project=project_file,
        )
        assert "Gandalf" in r.stdout

    def test_domain_ids_does_not_touch_legacy_domain(self, project_file):
        """Assigning domain_id does NOT modify the legacy domain: str field."""
        eid = _create_entity(project_file, "Frodo", "personaje")

        import sys
        sys.path.insert(0, str(WORKSPACE))
        from packages.application.project_service import ProjectService
        ps = ProjectService()
        ps.open(project_file)
        for e in ps.active_project.entities:
            if e.id == eid:
                e.domain = "comarca"
                break
        ps.save(project_file)
        ps.close()

        # Now assign domain_id
        _cli(f"entity assign-domain {eid} mundo", project=project_file)

        # Legacy domain should still be "comarca"
        ps2 = ProjectService()
        ps2.open(project_file)
        for e in ps2.active_project.entities:
            if e.id == eid:
                assert e.domain == "comarca"
                assert "mundo" in e.domain_ids
                break
        ps2.close()

    def test_layer_ids_does_not_touch_legacy_layers(self, project_file):
        """Assigning layer_id does NOT modify the legacy layers: list[str] field."""
        eid = _create_entity(project_file, "Rivendel", "localizacion")

        import sys
        sys.path.insert(0, str(WORKSPACE))
        from packages.application.project_service import ProjectService
        ps = ProjectService()
        ps.open(project_file)
        for e in ps.active_project.entities:
            if e.id == eid:
                e.layers = ["elfica"]
                break
        ps.save(project_file)
        ps.close()

        # Assign new layer_id
        _cli(f"entity assign-layer {eid} layer_geografia", project=project_file)

        # Legacy layers should still be ["elfica"]
        ps2 = ProjectService()
        ps2.open(project_file)
        for e in ps2.active_project.entities:
            if e.id == eid:
                assert e.layers == ["elfica"]
                assert "layer_geografia" in e.layer_ids
                break
        ps2.close()


# ═══ Gallery legacy ══════════════════════════════════════════════

class TestGalleryLegacy:
    def test_gallery_por_capa_still_works(self, project_file):
        """gallery por-capa <legacy_layer> still works from B09."""
        eid = _create_entity(project_file, "Moria", "localizacion")

        import sys
        sys.path.insert(0, str(WORKSPACE))
        from packages.application.project_service import ProjectService
        ps = ProjectService()
        ps.open(project_file)
        for e in ps.active_project.entities:
            if e.id == eid:
                e.layers = ["geografia"]
                break
        ps.save(project_file)
        ps.close()

        r = _cli("gallery por-capa geografia", project=project_file)
        assert "Moria" in r.stdout


# ═══ Relation show layer_ids ═════════════════════════════════════

class TestRelationShowLayer:
    def test_relation_show_shows_layer_ids(self, project_file):
        eid_a = _create_entity(project_file, "A", "personaje")
        eid_b = _create_entity(project_file, "B", "personaje")
        r = _cli(
            f"relation create {eid_a} {eid_b} --type esta_relacionado_con",
            project=project_file,
        )
        # Parse relation ID
        rid = r.stdout.strip().split("'")[1]

        _cli(f"relation assign-layer {rid} layer_narrativa", project=project_file)

        # Check relation show --extended
        r2 = _cli(f"relation show {rid} --extended", project=project_file)
        assert "layer_narrativa" in r2.stdout or "Narrativa" in r2.stdout


# ═══ Persistence roundtrip ═══════════════════════════════════════

class TestPersistenceRoundtrip:
    def test_domain_layer_persistence_roundtrip(self, project_file):
        eid = _create_entity(project_file, "Saruman", "personaje")
        _cli(f"entity assign-domain {eid} campaña", project=project_file)
        _cli(f"entity assign-layer {eid} layer_tecnologia", project=project_file)

        # Save and close
        _cli(f"project save", project=project_file)
        _cli("project close", project=project_file)

        # Reopen
        _cli(f'project open "{project_file}"')

        # Verify
        r = _cli(f"entity show {eid} --extended", project=project_file)
        assert "campaña" in r.stdout
        assert "Tecnología" in r.stdout or "layer_tecnologia" in r.stdout

    def test_config_persistence_roundtrip(self, project_file):
        _cli(
            'project config advanced set primary_genre "ciencia ficción"',
            project=project_file,
        )
        _cli("project save", project=project_file)
        _cli("project close", project=project_file)
        _cli(f'project open "{project_file}"')

        r = _cli("project config advanced get primary_genre", project=project_file)
        assert "ciencia ficción" in r.stdout


# ═══ Regression ══════════════════════════════════════════════════

class TestRegression:
    def test_regression_gallery_types(self, project_file):
        """gallery personajes without new flags returns same output shape as B09."""
        _create_entity(project_file, "Gandalf", "personaje")

        r = _cli("gallery personajes", project=project_file)
        assert r.returncode == 0
        assert "Gandalf" in r.stdout
        # Gallery title should be present
        assert "Personajes" in r.stdout or "personaje" in r.stdout

    def test_regression_entity_show_compact(self, project_file):
        """entity show <id> without --extended shows compact format."""
        eid = _create_entity(project_file, "Gollum", "personaje")

        r = _cli(f"entity show {eid}", project=project_file)
        assert r.returncode == 0
        assert "Gollum" in r.stdout
