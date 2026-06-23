"""CRON — vista del informe final del recorrido (offscreen)."""

from __future__ import annotations

import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_report_view_renders_fields():
    _app()
    from hosts.DesktopHostPySide.widgets.chronology_walk_report_view import (
        ChronologyWalkReportView,
    )
    from packages.domain.chronology_walk import ChronologyWalkReport

    report = ChronologyWalkReport(
        session_id="walk_1",
        verdict="Parcialmente coherente",
        milestones_analyzed=["h1", "h2"],
        contradictions=[{"title": "Orden temporal imposible", "kind": "impossible_temporal_order"}],
        critical_gaps=[{"title": "Falta una causa", "kind": "causal_gap"}],
        candidates_created=["c1", "c2", "c3"],
        timeline_reviewed_up_to_milestone_id="h2",
        recommended_next_steps=["Crear hito de la Purga."],
    )

    view = ChronologyWalkReportView()
    view.show_report(report)

    assert "Parcialmente coherente" in view._verdict.text()
    assert "hasta: h2" in view._range.text()
    assert view._contradictions.count() == 1
    assert view._gaps.count() == 1
    assert view._next_steps.count() == 1
    assert "3" in view._candidates.text()


def test_report_view_accepts_plain_dict():
    _app()
    from hosts.DesktopHostPySide.widgets.chronology_walk_report_view import (
        ChronologyWalkReportView,
    )

    view = ChronologyWalkReportView()
    view.show_report({"verdict": "Coherente", "milestones_analyzed": ["h1"]})
    assert "Coherente" in view._verdict.text()
