"""B21-T05 QA tests — secrets/clues integration, CLI, regression, smoke."""

from __future__ import annotations

import json, os, shlex, subprocess, sys
from pathlib import Path

import pytest

from packages.application.secrets_service import SecretsService
from packages.application.project_service import ProjectService
from packages.application.entity_service import EntityService
from packages.persistence.store import ProjectStore
from packages.domain.secrets_models import Secreto, Pista, RevelationState, DeliveryState
from packages.domain.entity import EntityType
from packages.domain.result import Error, Ok
from packages.persistence.schema import CURRENT_SCHEMA_VERSION

WORKSPACE = Path(__file__).resolve().parent.parent.parent


def _bootstrap(path: Path):
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.open(path)
    es = EntityService(project_service=ps, store=store)
    svc = SecretsService(project_service=ps, entity_service=es)
    return ps, es, svc


@pytest.fixture
def svc(tmp_path):
    path = tmp_path / "test.json"
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Test")
    ps.save(path)
    ps2, es2, svc2 = _bootstrap(path)
    return ps2, es2, svc2, path


# ── Integration ────────────────────────────────────────────────

class TestSecretsIntegration:
    def test_create_and_list(self, svc):
        ps, es, ssvc, path = svc
        ssvc.create_secret({"content": "S1", "importance": 4})
        ssvc.create_secret({"content": "S2"})
        assert len(ssvc.list_secrets()) == 2

    def test_secret_clue_linking(self, svc):
        ps, es, ssvc, path = svc
        s = ssvc.create_secret({"content": "Big secret"}).value
        c = ssvc.create_clue({"content": "Clue 1", "associated_secret_id": s.id}).value
        linked = ssvc.link_clue_to_secret(c.id, s.id)
        assert linked.value.associated_secret_id == s.id

    def test_revelation_full_flow(self, svc):
        ps, es, ssvc, path = svc
        s = ssvc.create_secret({"content": "S"}).value
        ssvc.reveal_secret(s.id, "rumoreado")
        ssvc.reveal_secret(s.id, "parcialmente_revelado")
        ssvc.reveal_secret(s.id, "revelado")
        final = ssvc.get_secret(s.id).value
        assert final.revelation_state == RevelationState.revelado

    def test_deliver_all_states(self, svc):
        ps, es, ssvc, path = svc
        c = ssvc.create_clue({"content": "C"}).value
        for state in ("perdida", "ignorada", "malinterpretada"):
            ssvc.deliver_clue(c.id, state=state)
            assert ssvc.get_clue(c.id).value.delivery_state.value == state

    def test_detection_idempotent(self, svc):
        ps, es, ssvc, path = svc
        ssvc.create_secret({"content": "No clues"})
        i1 = ssvc.run_secret_validation()
        assert len(i1) >= 1
        i2 = ssvc.run_secret_validation()
        assert len(i2) == 0

    def test_persistence_roundtrip(self, svc):
        ps, es, ssvc, path = svc
        ssvc.create_secret({"content": "Persist", "importance": 3})
        ssvc.create_clue({"content": "PersistClue"})
        ps.save(path)
        ps2, es2, svc2 = _bootstrap(path)
        assert len(svc2.list_secrets()) == 1
        assert len(svc2.list_clues()) == 1


# ── CLI ───────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean_session():
    f = WORKSPACE / ".narrative-session.json"
    try: f.unlink()
    except FileNotFoundError: pass


def _cli(args_str: str):
    args = shlex.split(args_str)
    env = {**os.environ, "PYTHONPATH": str(WORKSPACE)}
    return subprocess.run([sys.executable, "-m", "narrative_architect"] + args,
                          capture_output=True, text=True, cwd=str(WORKSPACE), env=env)


class TestCLISecrets:
    def test_help(self):
        r = _cli("secret --help"); assert r.returncode == 0; assert "create" in r.stdout
        r = _cli("clue --help"); assert r.returncode == 0; assert "create" in r.stdout

    def test_create_and_list(self, tmp_path):
        proj = tmp_path / "cli_s.json"
        _cli(f"project create Test --path {proj}")
        _cli("secret create 'El Anillo' --importance 3")
        r = _cli("secret list --json")
        data = json.loads(r.stdout); assert data["total"] == 1
        r = _cli("clue create 'Mapa' --clarity 4")
        assert r.returncode == 0
        r = _cli("clue list --json")
        data = json.loads(r.stdout); assert data["total"] == 1

    def test_reveal_and_detect(self, tmp_path):
        proj = tmp_path / "cli_r.json"
        _cli(f"project create Test --path {proj}")
        _cli("secret create 'Secret1'")
        r = _cli("secret list --json")
        sid = json.loads(r.stdout)["secrets"][0]["id"]
        r = _cli(f"secret reveal {sid} --state rumoreado")
        assert r.returncode == 0
        r = _cli("secret detect-issues --json")
        assert r.returncode == 0


class TestCLIClues:
    def test_deliver(self, tmp_path):
        proj = tmp_path / "cli_d.json"
        _cli(f"project create Test --path {proj}")
        _cli("clue create 'Pista'")
        r = _cli("clue list --json")
        cid = json.loads(r.stdout)["clues"][0]["id"]
        r = _cli(f"clue deliver {cid} --state perdida")
        assert r.returncode == 0
        r = _cli("clue pending --json")
        data = json.loads(r.stdout)
        assert data["total"] == 0


# ── Regression ────────────────────────────────────────────────

class TestRegression:
    def test_schema_is_v15(self): assert CURRENT_SCHEMA_VERSION == 16
    def test_campaign_still_works(self, svc):
        ps, es, ssvc, path = svc
        assert ps.active_project.campaigns is not None
        assert ps.active_project.secrets is not None
