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
