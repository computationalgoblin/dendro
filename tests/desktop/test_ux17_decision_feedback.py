"""Feedback de decisión al aceptar/rechazar candidatos (BETA1-UX17)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace
from hosts.DesktopHostPySide.widgets.candidate_review_panel import CandidateReviewPanel
from packages.domain.result import Ok


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeController:
    def __init__(self):
        self.accepted, self.rejected = [], []

    def accept(self, cid):
        self.accepted.append(cid)
        return Ok(SimpleNamespace(id=cid))

    def reject(self, cid):
        self.rejected.append(cid)
        return Ok(SimpleNamespace(id=cid))


def _decision_stub(decision: str):
    """Stub mínimo de self para _on_candidate_decision, capturando toasts."""
    toasts: list[tuple[str, str]] = []
    stub = SimpleNamespace(
        ctx=SimpleNamespace(
            notify=lambda msg, kind="info": toasts.append((msg, kind)),
            drawer=None,
            modal_overlay=None,
        ),
        _seed_notifications=SimpleNamespace(remove=lambda *a, **k: None),
        graph=SimpleNamespace(
            bloom_seed=lambda *a, **k: None,
            wither_seed=lambda *a, **k: None,
            bloom_node=lambda *a, **k: None,
            bloom_relation=lambda *a, **k: None,
            bloom_ring=lambda *a, **k: None,
        ),
        _find_candidate=lambda cid: None,
        _on_suggestion_changed=lambda: None,
        _germinate=lambda meta: None,
    )
    return stub, toasts


def test_aceptar_emite_toast_success() -> None:
    stub, toasts = _decision_stub("accept")
    CreationWorkspace._on_candidate_decision(stub, "cand-1", "accept")
    assert ("Semilla integrada al canon", "success") in toasts


def test_rechazar_emite_toast_info() -> None:
    stub, toasts = _decision_stub("reject")
    CreationWorkspace._on_candidate_decision(stub, "cand-2", "reject")
    assert ("Semilla descartada", "info") in toasts


def test_decision_sin_notify_no_rompe() -> None:
    # ctx sin notify (CLI/tests): fail-soft, no excepción.
    stub, _ = _decision_stub("accept")
    stub.ctx = SimpleNamespace(drawer=None, modal_overlay=None)  # sin notify
    CreationWorkspace._on_candidate_decision(stub, "cand-3", "accept")


def test_panel_fija_status_y_decision_sincrona() -> None:
    controller = _FakeController()
    decisions = []
    candidate = SimpleNamespace(
        id="cand-9",
        title="Aldea",
        candidate_type=SimpleNamespace(value="entidad"),
        proposed_data={"name": "Aldea", "brief_description": "x"},
    )
    panel = CandidateReviewPanel(
        candidate, controller, on_decision=lambda cid, d: decisions.append((cid, d))
    )
    panel._accept()
    assert controller.accepted == ["cand-9"]
    assert decisions == [("cand-9", "accept")]
    assert panel._status.text() == "Aceptado ✓"

    panel2 = CandidateReviewPanel(
        candidate, controller, on_decision=lambda cid, d: decisions.append((cid, d))
    )
    panel2._reject()
    assert controller.rejected == ["cand-9"]
    assert panel2._status.text() == "Descartado"
