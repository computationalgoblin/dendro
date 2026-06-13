"""H07 desktop exact calendar picker."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication, QPushButton
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

from packages.domain.causal_milestone import CausalMilestone
from packages.domain.project_chronology import ProjectChronology
from packages.domain.result import Ok

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.calendar_date_picker import CalendarDatePicker
    from hosts.DesktopHostPySide.widgets.milestone_chronology_view import MilestoneChronologyView


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeMilestoneController:
    def __init__(self, hitos):
        self.hitos = list(hitos)
        self.updated = []

    def list_all(self):
        return list(self.hitos)

    def update(self, hito_id: str, data: dict):
        self.updated.append((hito_id, data))
        for index, hito in enumerate(self.hitos):
            if hito.id == hito_id:
                merged = hito.to_dict()
                merged.update(data)
                self.hitos[index] = CausalMilestone.from_dict(merged)
                return Ok(self.hitos[index])
        return Ok(None)


def calendar_meta():
    return {
        "mode": "full_calendar",
        "eras": ["Era Antigua", "Era Actual"],
        "era_lengths": {"Era Antigua": 900, "Era Actual": 42},
        "months": ["Alba", "Bruma"],
        "month_lengths": {"Alba": 31, "Bruma": 22},
        "weekdays": ["Uno", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Siete"],
        "current_date": {"era": "Era Actual", "year": 12, "month": "Bruma", "day": 20},
    }


def test_calendar_date_picker_respects_month_and_era_lengths(qapp):
    picker = CalendarDatePicker(compact=True)
    picker.set_calendar(calendar_meta())
    picker.set_date({"era": "Era Actual", "year": 99, "month": "Bruma", "day": 30})

    assert picker.year_spin.maximum() == 42
    assert picker.year_spin.value() == 42
    assert picker.date()["day"] == 22
    assert len(picker.findChildren(QPushButton, "calendarDayButton")) == 22


def test_milestone_detail_saves_exact_date_from_calendar_picker(qapp):
    hito = CausalMilestone(id="hito-1", title="Coronacion")
    ctrl = FakeMilestoneController([hito])
    chronology = ProjectChronology(calendar_system="full_calendar", metadata=calendar_meta())
    project = SimpleNamespace(
        entities=[],
        relations=[],
        causal_milestones=ctrl.hitos,
        project_chronology=chronology,
    )
    view = MilestoneChronologyView(ctrl, project_getter=lambda: project)

    view.select_milestone("hito-1")
    assert not view.exact_date_picker.isHidden()
    view.exact_date_picker.set_date({"era": "Era Antigua", "year": 120, "month": "Alba", "day": 31})
    view._save_detail()

    assert ctrl.updated
    metadata = ctrl.updated[0][1]["metadata"]
    assert metadata["exact_date"] == {"era": "Era Antigua", "year": 120, "month": "Alba", "day": 31}
    assert metadata["chronology_key"] == "Era Antigua, ano 120, Alba 31"
