"""H05 desktop wiring for chronology configuration and related milestone AI."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication, QPushButton
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

from packages.domain.project_chronology import ProjectChronology
from packages.domain.result import Ok

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.chronology_config_panel import ChronologyConfigPanel
    from hosts.DesktopHostPySide.widgets.project_wizard import ProjectWizard
    from hosts.DesktopHostPySide.widgets.related_milestones_panel import RelatedMilestonesPanel


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

ROOT = Path(__file__).resolve().parents[2]
WORKSPACES = ROOT / "hosts" / "DesktopHostPySide" / "views" / "workspaces.py"
SETTINGS = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "settings_panels.py"
MILESTONE_VIEW = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "milestone_chronology_view.py"
NODE_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "node_detail_panel.py"
TREE_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "tree_detail_panel.py"
REL_PANEL = ROOT / "hosts" / "DesktopHostPySide" / "widgets" / "relation_detail_panel.py"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeChronologyController:
    def __init__(self):
        self.saved = None
        self.chronology = ProjectChronology(
            calendar_name="Viejo",
            description="",
            calendar_system="vague_periods",
            metadata={"mode": "vague_periods"},
        )

    def get(self):
        return Ok(self.chronology)

    def update(self, data):
        self.saved = dict(data)
        return Ok(self.chronology)


def test_chronology_config_panel_saves_manual_calendar(qapp):
    controller = FakeChronologyController()
    panel = ChronologyConfigPanel(controller, compact=True)

    panel.mode_combo.setCurrentIndex(panel.mode_combo.findData("full_calendar"))
    panel.name_edit.setText("Calendario de las Mareas")
    panel.description_edit.setPlainText("Mide mareas y juramentos.")
    panel.eras_edit.setPlainText("Marea alta: 400\nMarea baja: 200")
    panel.months_edit.setPlainText("Bruma: 28\nSol: 31")
    panel.weekdays_edit.setPlainText("Primer dia\nSegundo dia")
    panel.days_per_month_spin.setValue(28)
    panel.current_year_spin.setValue(1203)
    panel.current_date_picker.set_date({"era": "Marea baja", "year": 12, "month": "Sol", "day": 30})
    panel.findChild(QPushButton, "saveChronologyConfigButton").click()

    assert controller.saved["calendar_name"] == "Calendario de las Mareas"
    assert controller.saved["mode"] == "full_calendar"
    assert controller.saved["eras"] == ["Marea alta", "Marea baja"]
    assert controller.saved["era_lengths"] == "Marea alta: 400\nMarea baja: 200"
    assert controller.saved["months"] == ["Bruma", "Sol"]
    assert controller.saved["month_lengths"] == "Bruma: 28\nSol: 31"
    assert controller.saved["weekdays"] == "Primer dia\nSegundo dia"
    assert controller.saved["days_per_month"] == 28
    assert controller.saved["current_year"] == 1203
    assert controller.saved["current_date"] == {"era": "Marea baja", "year": 12, "month": "Sol", "day": 30}


def test_chronology_config_panel_offers_three_calendar_options(qapp):
    panel = ChronologyConfigPanel(FakeChronologyController(), compact=True)

    modes = [panel.mode_combo.itemData(index) for index in range(panel.mode_combo.count())]

    assert modes == ["none", "vague_periods", "full_calendar"]


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

    # BETA1-G09: el wizard es ahora un QDialog custom; sus campos de cronología
    # son atributos planos (no QWizardPage). La intención del test no cambia.
    wizard.chrono_mode.setCurrentIndex(wizard.chrono_mode.findData("full_calendar"))
    wizard.chrono_name.setText("Calendario del Exilio")
    wizard.chrono_eras.setPlainText("Antes: 900\nDespues: 42")
    wizard.chrono_months.setPlainText("Niebla: 28\nFuego: 31")
    wizard.chrono_weekdays.setPlainText("Uno\nDos")
    wizard.chrono_days.setValue(28)
    wizard.chrono_date.set_date({"era": "Despues", "year": 4, "month": "Fuego", "day": 12})
    cfg = wizard.collect_config()

    assert cfg["project_chronology"]["calendar_name"] == "Calendario del Exilio"
    assert cfg["project_chronology"]["metadata"]["mode"] == "full_calendar"
    project = SimpleNamespace(
        name="",
        primary_language="es",
        worldbuilding_active=False,
        project_chronology=ProjectChronology(),
        creative_config=SimpleNamespace(),
        genre=SimpleNamespace(),
        tone=SimpleNamespace(),
        ai=SimpleNamespace(),
    )
    wizard.apply_to_project(project)

    assert project.project_chronology.calendar_name == "Calendario del Exilio"
    assert project.project_chronology.metadata["eras"] == ["Antes", "Despues"]
    assert project.project_chronology.metadata["months"] == ["Niebla", "Fuego"]
    assert project.project_chronology.metadata["weekdays"] == ["Uno", "Dos"]
    assert project.project_chronology.metadata["current_date"] == {"era": "Despues", "year": 4, "month": "Fuego", "day": 12}
    assert project.project_chronology.metadata["units"] == ["era", "ano", "mes", "dia"]


def test_h05_sources_are_wired_without_graph_or_physics_changes():
    workspace = WORKSPACES.read_text(encoding="utf-8")
    settings = SETTINGS.read_text(encoding="utf-8")
    milestone_view = MILESTONE_VIEW.read_text(encoding="utf-8")
    detail_sources = "\n".join([
        NODE_PANEL.read_text(encoding="utf-8"),
        TREE_PANEL.read_text(encoding="utf-8"),
        REL_PANEL.read_text(encoding="utf-8"),
    ])

    assert "ProjectChronologyController" in workspace
    assert "chronology_controller=self._chronology_ctrl" in workspace
    assert "def _suggest_related_milestone" in workspace
    assert "scope_override" in workspace
    assert "ChronologyConfigPanel" in settings
    assert "ChronologyConfigPanel" in milestone_view
    assert "on_suggest_milestone" in detail_sources
    assert "GraphNodeItem(" not in milestone_view
    assert "_physics_enabled" not in milestone_view
