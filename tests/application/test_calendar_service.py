"""BETA2-CAL-02 — CalendarService: puente eras canónicas ↔ config de calendario.

Verifica que la ruta unificada escribe eras canónicas encadenadas (cerradas salvo la
última abierta), fija el present_year absoluto derivado de (era + año regnal), espeja la
config sin el clobber legacy, calcula el día de la semana real y hace round-trip por
`get_view`.
"""

from __future__ import annotations

from packages.application.calendar_service import CalendarService
from packages.domain.project import Project
from packages.domain.result import Error, Ok


class _FakeProjectService:
    def __init__(self, project):
        self.active_project = project


def _service(project=None):
    project = project or Project(id="p-cal", name="CAL")
    return CalendarService(_FakeProjectService(project)), project


# ── configure: eras encadenadas + presente ───────────────────────────────────


def test_configure_chains_eras_last_open():
    svc, project = _service()
    result = svc.configure(
        {
            "eras": [{"name": "Era A", "duration": 100}, {"name": "Era B", "duration": 50}],
            "present": {"era_index": 1, "year_within": 10},
        }
    )
    assert isinstance(result, Ok)
    eras = project.project_chronology.sorted_eras()
    assert [(e.start_year, e.end_year) for e in eras] == [(0, 99), (100, None)]
    # Presente = Era B (start 100) año 10 → absoluto 109.
    assert project.project_chronology.present_year == 109


def test_configure_mirrors_metadata_without_legacy_clobber():
    svc, project = _service()
    svc.configure(
        {
            "eras": [{"name": "Era A", "duration": 100}, {"name": "Era B", "duration": 50}],
            "present": {"era_index": 1, "year_within": 10},
        }
    )
    meta = project.project_chronology.metadata
    # Sin meses+semana → modo derivado 'vague_periods' pero SIN aplastar era_lengths a 1.
    assert meta["mode"] == "vague_periods"
    assert meta["era_lengths"] == {"Era A": 100, "Era B": 50}
    assert meta["current_year"] == 109
    assert meta["current_date"] == {"era": "Era B", "year": 10, "month": "", "day": 1}
    assert meta["supports_exact_dates"] is False


def test_configure_present_clamped_within_closed_era():
    svc, project = _service()
    svc.configure(
        {
            "eras": [{"name": "Corta", "duration": 5}, {"name": "Abierta", "duration": 10}],
            "present": {"era_index": 0, "year_within": 999},  # se recorta a 5
        }
    )
    # Era cerrada [0,4]; año 5 (máximo) → absoluto 4.
    assert project.project_chronology.present_year == 4


def test_configure_requires_at_least_one_era():
    svc, _ = _service()
    assert isinstance(svc.configure({"eras": []}), Error)


def test_configure_rejects_bad_duration():
    svc, _ = _service()
    assert isinstance(svc.configure({"eras": [{"name": "X", "duration": 0}]}), Error)


def test_configure_rejects_empty_era_name():
    svc, _ = _service()
    assert isinstance(svc.configure({"eras": [{"name": "  ", "duration": 5}]}), Error)


# ── configure: calendario completo (meses/semana/ancla) ──────────────────────


def test_configure_full_calendar_sets_exact_mode_and_weekday():
    svc, project = _service()
    result = svc.configure(
        {
            "eras": [{"name": "Primera", "duration": 3}],
            "present": {"era_index": 0, "year_within": 1, "month": "M1", "day": 1},
            "months": [{"name": "M1", "length": 10}, {"name": "M2", "length": 20}],
            "weekdays": ["a", "b", "c", "d", "e", "f", "g"],
            "week_anchor": 0,
        }
    )
    assert isinstance(result, Ok)
    meta = project.project_chronology.metadata
    assert meta["mode"] == "full_calendar"
    assert meta["supports_exact_dates"] is True
    assert meta["calendar"]["months"] == [
        {"name": "M1", "length": 10},
        {"name": "M2", "length": 20},
    ]
    # Día de la semana real: M1 día 1 en el origen = "a"; M2 día 1 = día abs 10 → "d".
    assert svc.weekday_of(0, 1, "M1", 1) == Ok("a")
    assert svc.weekday_of(0, 1, "M2", 1) == Ok("d")


def test_weekday_of_errors_without_months():
    svc, _ = _service()
    svc.configure(
        {"eras": [{"name": "Sola", "duration": 10}], "present": {"era_index": 0, "year_within": 1}}
    )
    assert isinstance(svc.weekday_of(0, 1, "X", 1), Error)


# ── get_view: round-trip ─────────────────────────────────────────────────────


def test_get_view_roundtrips_configured_calendar():
    svc, _ = _service()
    svc.configure(
        {
            "eras": [{"name": "Era A", "duration": 100}, {"name": "Era B", "duration": 50}],
            "present": {"era_index": 1, "year_within": 10},
            "months": [{"name": "M1", "length": 12}],
            "weekdays": ["l", "m", "x"],
            "week_anchor": 1,
        }
    )
    view = svc.get_view()
    assert isinstance(view, Ok)
    data = view.value
    assert [(e["name"], e["duration"]) for e in data["eras"]] == [("Era A", 100), ("Era B", 50)]
    assert data["present"]["era_index"] == 1
    assert data["present"]["year_within"] == 10
    assert data["months"] == [{"name": "M1", "length": 12}]
    assert data["weekdays"] == ["l", "m", "x"]
    assert data["week_anchor"] == 1


def test_configure_reuses_era_ids_across_reconfigure():
    svc, project = _service()
    payload = {
        "eras": [{"name": "Era A", "duration": 100}, {"name": "Era B", "duration": 50}],
        "present": {"era_index": 1, "year_within": 1},
    }
    svc.configure(payload)
    ids_first = [e.id for e in project.project_chronology.sorted_eras()]
    svc.configure(payload)
    ids_second = [e.id for e in project.project_chronology.sorted_eras()]
    assert ids_first == ids_second
