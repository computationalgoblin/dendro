"""H05/BETA2-CAL desktop wiring for the unified calendar editor and milestone AI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication, QPushButton
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

from packages.application.calendar_service import CalendarService
from packages.domain.project import Project

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.chronology_config_panel import ChronologyConfigPanel
    from hosts.DesktopHostPySide.widgets.project_wizard import ProjectWizard
    from hosts.DesktopHostPySide.widgets.related_milestones_panel import RelatedMilestonesPanel


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

ROOT = Path(__file__).resolve().parents[2]
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"
SETTINGS = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "settings_panels.py"
NODE_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "node_detail_panel.py"
REL_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "relation_detail_panel.py"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeChronologyController:
    """Controlador real sobre un Project en memoria (ruta CalendarService)."""

    def __init__(self):
        self.project = Project(id="p", name="N")
        self._calendar = CalendarService(SimpleNamespace(active_project=self.project))

    def calendar_view(self):
        return self._calendar.get_view()

    def configure_calendar(self, payload):
        return self._calendar.configure(payload)


def test_chronology_config_panel_saves_chained_calendar(qapp):
    controller = FakeChronologyController()
    panel = ChronologyConfigPanel(controller, compact=True)

    panel.editor.set_value(
        {
            "calendar_name": "Calendario de las Mareas",
            "eras": [{"name": "Marea alta", "duration": 400}, {"name": "Marea baja", "duration": 200}],
            "present": {"era_index": 1, "year_within": 12, "month": "Sol", "day": 30},
            "months": [{"name": "Bruma", "length": 28}, {"name": "Sol", "length": 31}],
            "weekdays": ["Primer dia", "Segundo dia"],
            "week_anchor": 0,
        }
    )
    panel.findChild(QPushButton, "saveChronologyConfigButton").click()

    chrono = controller.project.project_chronology
    eras = chrono.sorted_eras()
    assert [(e.name, e.start_year, e.end_year) for e in eras] == [
        ("Marea alta", 0, 399),
        ("Marea baja", 400, None),
    ]
    # Presente: Marea baja (start 400) año 12 → absoluto 411.
    assert chrono.present_year == 411
    assert chrono.calendar_name == "Calendario de las Mareas"
    assert chrono.metadata["mode"] == "full_calendar"
    assert chrono.metadata["calendar"]["weekdays"] == ["Primer dia", "Segundo dia"]


def test_chronology_config_panel_reloads_existing_calendar(qapp):
    controller = FakeChronologyController()
    controller.configure_calendar(
        {
            "eras": [{"name": "Uno", "duration": 30}, {"name": "Dos", "duration": 10}],
            "present": {"era_index": 1, "year_within": 3},
        }
    )
    panel = ChronologyConfigPanel(controller, compact=True)

    value = panel.editor.value()
    assert [e["name"] for e in value["eras"]] == ["Uno", "Dos"]
    assert value["present"]["era_index"] == 1
    assert value["present"]["year_within"] == 3


def test_related_milestones_panel_suggest_button_emits_context(qapp):
    calls = []
    panel = RelatedMilestonesPanel(
        milestone_controller=SimpleNamespace(list_all=lambda: []),
        target_kind="relation",
        target_id="rel-1",
        on_suggest_milestone=lambda kind, target_id: calls.append((kind, target_id)),
    )

    button = panel.findChild(QPushButton, "suggestRelatedMilestoneButton")
    assert not button.isHidden()
    button.click()

    assert calls == [("relation", "rel-1")]


def test_project_wizard_collects_and_applies_chronology(qapp):
    wizard = ProjectWizard()

    wizard.chrono_editor.set_value(
        {
            "calendar_name": "Calendario del Exilio",
            "eras": [{"name": "Antes", "duration": 900}, {"name": "Despues", "duration": 42}],
            "present": {"era_index": 1, "year_within": 4, "month": "Fuego", "day": 12},
            "months": [{"name": "Niebla", "length": 28}, {"name": "Fuego", "length": 31}],
            "weekdays": ["Uno", "Dos"],
        }
    )
    cfg = wizard.collect_config()
    assert cfg["project_chronology"]["calendar_name"] == "Calendario del Exilio"
    assert [e["name"] for e in cfg["project_chronology"]["eras"]] == ["Antes", "Despues"]

    project = Project(id="pw", name="")
    wizard.apply_to_project(project)

    chrono = project.project_chronology
    assert chrono.calendar_name == "Calendario del Exilio"
    eras = chrono.sorted_eras()
    assert [(e.name, e.start_year, e.end_year) for e in eras] == [
        ("Antes", 0, 899),
        ("Despues", 900, None),
    ]
    # Presente: Despues (start 900) año 4 → absoluto 903.
    assert chrono.present_year == 903
    assert chrono.metadata["mode"] == "full_calendar"


def test_h05_sources_are_wired_without_graph_or_physics_changes():
    workspace = WORKSPACES.read_text(encoding="utf-8")
    settings = SETTINGS.read_text(encoding="utf-8")
    detail_sources = "\n".join([
        NODE_PANEL.read_text(encoding="utf-8"),
        REL_PANEL.read_text(encoding="utf-8"),
    ])

    assert "ProjectChronologyController" in workspace
    assert "chronology_controller=self._chronology_ctrl" in workspace
    assert "def _suggest_related_milestone" in workspace
    assert "scope_override" in workspace
    # BETA2-CAL-06: la configuración abre el editor de calendario en un diálogo ancho
    # (que a su vez hospeda ChronologyConfigPanel).
    assert "CalendarEditorDialog" in settings
    assert "on_suggest_milestone" in detail_sources
