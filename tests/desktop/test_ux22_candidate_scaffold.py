"""Adopción de PanelScaffold en el panel de revisión de candidatos (BETA1-UX22)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.widgets.candidate_review_panel import CandidateReviewPanel
from hosts.DesktopHostPySide.widgets.design_system import Badge, PanelScaffold
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


def _candidate():
    return SimpleNamespace(
        id="cand-1",
        title="Aldea del Sur",
        candidate_type=SimpleNamespace(value="entidad"),
        proposed_data={"name": "Aldea del Sur", "brief_description": "Un villorrio."},
    )


def test_panel_usa_scaffold_con_badge() -> None:
    panel = CandidateReviewPanel(_candidate(), _FakeController())
    scaffolds = panel.findChildren(PanelScaffold)
    assert len(scaffolds) == 1
    # Badge de tipo en la cabecera.
    badges = scaffolds[0].findChildren(Badge)
    assert any("ENTIDAD" in b.text() for b in badges)


def test_api_preservada_y_decision_funciona() -> None:
    controller = _FakeController()
    decisions = []
    panel = CandidateReviewPanel(
        _candidate(), controller, on_decision=lambda cid, d: decisions.append((cid, d))
    )
    # Atributos que otros tests/host dependen.
    assert panel._title_edit is not None
    assert panel._status is not None
    panel._accept()
    assert controller.accepted == ["cand-1"]
    assert decisions == [("cand-1", "accept")]
    assert panel._status.text() == "Aceptado ✓"
