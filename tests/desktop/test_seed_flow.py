"""Semillas (Fase A): auto-stage al finalizar + panel de revisión por-candidato."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace
from hosts.DesktopHostPySide.widgets.candidate_review_panel import (
    CandidateReviewPanel,
    candidate_body_text,
)
from hosts.DesktopHostPySide.widgets.seed_audio import ZenBell
from hosts.DesktopHostPySide.widgets.seed_notifications import SeedNotificationLayer
from packages.domain.result import Ok


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class _FakeController:
    def __init__(self):
        self.created = []
        self.accepted = []
        self.rejected = []
        self._seq = 0

    def create(self, data):
        self._seq += 1
        cand = SimpleNamespace(id=f"cand-{self._seq}", title=data.get("name", "x"))
        self.created.append(dict(data))
        return Ok(cand)

    def accept(self, cid):
        self.accepted.append(cid)
        return Ok(SimpleNamespace(id=cid))

    def reject(self, cid):
        self.rejected.append(cid)
        return Ok(SimpleNamespace(id=cid))


def _stub_workspace(qapp, controller):
    from PySide6.QtWidgets import QWidget

    host = QWidget()
    host.resize(900, 600)
    layer = SeedNotificationLayer(host)
    bell = ZenBell()
    bell.set_enabled(False)  # sin síntesis en tests
    stub = SimpleNamespace(
        candidate_view=SimpleNamespace(cc=controller),
        _seed_notifications=layer,
        _zen_bell=bell,
        ctx=SimpleNamespace(log=lambda *a, **k: None),
        _on_suggestion_changed=lambda: None,
        # SEM04: _auto_stage_and_notify divide la semilla del grafo / la marchita.
        graph=SimpleNamespace(split_seed=lambda *a, **k: None, wither_seed=lambda *a, **k: None),
        # FOCO-13: germinación espacial en Foco (idempotente en el flujo real).
        _foco_visible_candidate_ids=lambda: set(),
        _sync_foco_seeds=lambda: None,
    )
    stub._host = host  # mantener vivo el padre
    return stub


def test_auto_stage_creates_candidates_and_notifications(qapp):
    controller = _FakeController()
    stub = _stub_workspace(qapp, controller)
    job = SimpleNamespace(
        message="listo",
        result={"candidates": [{"name": "Aldea del Sur"}, {"name": "Capitán Ruiz"}]},
    )
    CreationWorkspace._auto_stage_and_notify(stub, job)

    assert len(controller.created) == 2
    assert set(stub._seed_notifications.notifications) == {"cand-1", "cand-2"}


def test_report_only_job_creates_no_seeds(qapp):
    controller = _FakeController()
    stub = _stub_workspace(qapp, controller)
    job = SimpleNamespace(message="informe", result={"report": "análisis"})  # sin candidatos
    CreationWorkspace._auto_stage_and_notify(stub, job)

    assert controller.created == []
    assert stub._seed_notifications.notifications == {}


def test_review_panel_accept_and_reject(qapp):
    controller = _FakeController()
    decisions = []
    candidate = SimpleNamespace(
        id="cand-9",
        title="Aldea del Sur",
        candidate_type=SimpleNamespace(value="entidad"),
        proposed_data={"name": "Aldea del Sur", "brief_description": "Un villorrio."},
    )
    panel = CandidateReviewPanel(
        candidate, controller, on_decision=lambda cid, d: decisions.append((cid, d))
    )
    panel._accept()
    assert controller.accepted == ["cand-9"]
    assert decisions == [("cand-9", "accept")]

    panel2 = CandidateReviewPanel(
        candidate, controller, on_decision=lambda cid, d: decisions.append((cid, d))
    )
    panel2._reject()
    assert controller.rejected == ["cand-9"]
    assert decisions[-1] == ("cand-9", "reject")


def test_body_text_extraction():
    assert candidate_body_text({"extended_description": "largo"}) == "largo"
    assert candidate_body_text({"brief_description": "breve"}) == "breve"
    assert candidate_body_text({}) == ""


# ── Semilla de análisis de coherencia: orbita en el anillo activo ─────────────


def test_analysis_jobs_germinate_a_seed():
    # Los análisis (coherencia/review) producen un candidato-informe → deben germinar
    # una semilla; solo el texto inline y la reparación (panel propio) quedan excluidos.
    import hosts.DesktopHostPySide.views.workspaces as ws
    assert "analyze_coherence" not in ws._NO_SEED_JOB_TYPES
    assert "review_graph" not in ws._NO_SEED_JOB_TYPES
    assert "repair_coherence" in ws._NO_SEED_JOB_TYPES
    assert {"improve_text", "generate_text"} <= ws._NO_SEED_JOB_TYPES


class _FakeSignal:
    def connect(self, *a, **k):
        pass


class _FakeWorker:
    def __init__(self, *a, **k):
        self.statusChanged = _FakeSignal()
        self.finishedOk = _FakeSignal()
        self.failed = _FakeSignal()
        self.finished = _FakeSignal()

    def start(self):
        pass


def test_coherence_job_plants_seed_in_active_ring(qapp, monkeypatch):
    import hosts.DesktopHostPySide.views.workspaces as ws
    monkeypatch.setattr(ws, "_AIJobWorker", _FakeWorker)
    captured: dict = {}
    job = SimpleNamespace(
        type=SimpleNamespace(value="analyze_coherence"),
        context_scope={"active_ring_id": "ring-meta"},
    )
    stub = SimpleNamespace(
        ai_job_service=SimpleNamespace(get_job=lambda jid: Ok(job)),
        _ai_workers={},
        graph=SimpleNamespace(
            plant_seed=lambda jid, rid: captured.__setitem__("seed", (jid, rid)),
        ),
        _on_ai_job_status=lambda *a: None,
        _on_ai_job_finished=lambda *a: None,
        _on_ai_job_failed=lambda *a: None,
        _on_ai_worker_stopped=lambda *a: None,
        _refresh_busy_indicator=lambda *a: None,  # UX11
    )
    CreationWorkspace._start_ai_job_worker(stub, "job-1")
    assert captured["seed"] == ("job-1", "ring-meta")  # semilla en el anillo activo


def test_inline_text_job_plants_no_seed(qapp, monkeypatch):
    import hosts.DesktopHostPySide.views.workspaces as ws
    monkeypatch.setattr(ws, "_AIJobWorker", _FakeWorker)
    captured: dict = {}
    job = SimpleNamespace(
        type=SimpleNamespace(value="generate_text"),
        context_scope={"active_ring_id": "ring-meta"},
    )
    stub = SimpleNamespace(
        ai_job_service=SimpleNamespace(get_job=lambda jid: Ok(job)),
        _ai_workers={},
        graph=SimpleNamespace(
            plant_seed=lambda jid, rid: captured.__setitem__("seed", (jid, rid)),
        ),
        _on_ai_job_status=lambda *a: None,
        _on_ai_job_finished=lambda *a: None,
        _on_ai_job_failed=lambda *a: None,
        _on_ai_worker_stopped=lambda *a: None,
        _refresh_busy_indicator=lambda *a: None,  # UX11
    )
    CreationWorkspace._start_ai_job_worker(stub, "job-2")
    assert "seed" not in captured  # texto inline no germina
