"""BETA2-STRUCT-03: panel de proyecto de ajustes estructurales + guarda del panel de candidatos.

Ejecutar POR ARCHIVO (offscreen): el directorio desktop completo segfaultea en un proceso.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from hosts.DesktopHostPySide.widgets.candidate_review_panel import (
    CandidateReviewPanel,
    is_structural_candidate,
)
from hosts.DesktopHostPySide.widgets.structure_review_panel import StructureReviewPanel
from packages.application.causal_potency import build_ring_move_proposal
from packages.application.structural_analysis_service import StructuralFinding
from packages.domain.candidate_issue import Candidate, CandidateType
from packages.domain.result import Ok


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


@dataclass
class _FakeService:
    findings: list
    structures: list = field(default_factory=list)
    dismissed: list = field(default_factory=list)
    postponed: list = field(default_factory=list)
    discarded: list = field(default_factory=list)
    enriched: str = "Prosa IA afinada."

    def analyze(self):
        return Ok(list(self.findings))

    def baseline_justification(self, finding):
        return "razón determinista base"

    def enrich_justification(self, finding):
        return Ok(self.enriched)

    def dismiss(self, fingerprint):
        self.dismissed.append(fingerprint)
        return Ok(True)

    def postpone(self, fingerprint):
        self.postponed.append(fingerprint)
        return Ok(True)

    # STRUCT-07
    def structure_proposals(self):
        return list(self.structures)

    def propose_ring_structure(self):
        return Ok(list(self.structures))

    def discard_structure_proposal(self, fingerprint):
        self.discarded.append(fingerprint)
        self.structures = [f for f in self.structures if f.fingerprint != fingerprint]


def _finding(fp: str = "ring_move:H:a->b") -> StructuralFinding:
    pd = build_ring_move_proposal(
        "H", current_ring_id="a", target_ring_id="b",
        reasons=["r1"], expected_consequences=["c1"], supporting_relation_ids=["rel1"],
    )
    return StructuralFinding(
        kind="ring_move", target_id="H", proposed_data=pd,
        confidence=0.7, fingerprint=fp, title="Reubicar «H»: A → B",
    )


class _FakeController:
    def accept(self, cid):
        return Ok(None)


# ── StructureReviewPanel ───────────────────────────────────────────────────


def test_panel_lists_findings_and_accept_routes():
    accepted = []
    svc = _FakeService(findings=[_finding()])
    panel = StructureReviewPanel(svc, on_accept=accepted.append)
    assert panel._findings()  # hay hallazgos
    panel._accept(svc.findings[0], structure=False)
    assert accepted and accepted[0].target_id == "H"


def test_panel_reject_and_postpone_persist_suppression():
    svc = _FakeService(findings=[_finding("fp-x")])
    panel = StructureReviewPanel(svc, on_accept=lambda f: None)
    panel._reject(svc.findings[0], structure=False)
    assert svc.dismissed == ["fp-x"]
    panel._postpone(svc.findings[0])
    assert svc.postponed == ["fp-x"]


def _struct_finding(fp: str = "ring_merge:a->b") -> StructuralFinding:
    return StructuralFinding(
        kind="ring_merge", target_id="",
        proposed_data={"kind": "ring_merge", "source_ring_id": "a", "target_ring_id": "b"},
        confidence=0.7, fingerprint=fp, title="Fusionar «A» → «B»",
    )


def test_structure_proposal_reject_discards_from_session():
    f = _struct_finding()
    svc = _FakeService(findings=[], structures=[f])
    panel = StructureReviewPanel(svc, on_accept=lambda x: None)
    panel._reject(f, structure=True)
    assert svc.discarded == [f.fingerprint]  # NO usa dismiss (no hay entidad)
    assert svc.dismissed == []


def test_structure_proposal_accept_routes_and_discards():
    accepted = []
    f = _struct_finding()
    svc = _FakeService(findings=[], structures=[f])
    panel = StructureReviewPanel(svc, on_accept=accepted.append)
    panel._accept(f, structure=True)
    assert accepted == [f]
    assert svc.discarded == [f.fingerprint]


def test_panel_refine_swaps_in_ai_justification():
    svc = _FakeService(findings=[_finding()])
    panel = StructureReviewPanel(svc, on_accept=lambda f: None)
    label = QLabel("razón determinista base")
    panel._refine(svc.findings[0], label)
    assert label.text() == "Prosa IA afinada."


def test_panel_empty_state_builds():
    svc = _FakeService(findings=[])
    panel = StructureReviewPanel(svc, on_accept=lambda f: None)
    assert panel._findings() == []  # no rompe con lista vacía


def test_panel_close_button_invokes_on_close():
    closed = []
    svc = _FakeService(findings=[_finding()])
    panel = StructureReviewPanel(
        svc, on_accept=lambda f: None, on_close=lambda: closed.append(True)
    )
    panel._close()
    assert closed == [True]


# ── guarda estructural en CandidateReviewPanel ─────────────────────────────


def test_candidate_panel_uses_structural_mode_and_keeps_payload_intact():
    pd = build_ring_move_proposal(
        "H", current_ring_id="a", target_ring_id="b", reasons=["r1"],
        expected_consequences=["c1"],
    )
    assert is_structural_candidate(pd) is True
    cand = Candidate(candidate_type=CandidateType.ANILLO, title="Reubicar", proposed_data=pd)
    panel = CandidateReviewPanel(
        cand,
        _FakeController(),
        on_decision=lambda *a: None,
        on_close=lambda: None,
        on_repair=None,
        log=None,
    )
    assert panel._mode == "structural"
    before = dict(cand.proposed_data)
    panel._apply_edits()  # NO debe reescribir el payload estructural
    assert cand.proposed_data == before
