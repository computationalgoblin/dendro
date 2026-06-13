"""H07: exact dates for full project calendars."""

from __future__ import annotations

from types import SimpleNamespace

from packages.application.project_chronology_service import ProjectChronologyService
from packages.domain.project import Project
from packages.domain.result import Error


def test_full_calendar_stores_variable_month_and_era_lengths_and_current_date():
    project = Project(name="H07")
    service = ProjectChronologyService(SimpleNamespace(active_project=project))

    result = service.update({
        "mode": "full_calendar",
        "calendar_system": "full_calendar",
        "calendar_name": "Calendario de Sol",
        "eras": ["Era Antigua", "Era Actual"],
        "era_lengths": "Era Antigua: 900\nEra Actual: 42",
        "months": ["Alba", "Bruma"],
        "month_lengths": "Alba: 31\nBruma: 22",
        "weekdays": ["Uno", "Dos"],
        "current_date": {"era": "Era Actual", "year": 12, "month": "Bruma", "day": 20},
    })

    assert not isinstance(result, Error)
    meta = result.value.metadata
    assert meta["era_lengths"] == {"Era Antigua": 900, "Era Actual": 42}
    assert meta["month_lengths"] == {"Alba": 31, "Bruma": 22}
    assert meta["current_date"] == {"era": "Era Actual", "year": 12, "month": "Bruma", "day": 20}
    assert meta["supports_exact_dates"] is True
