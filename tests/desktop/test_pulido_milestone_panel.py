"""BETA2-PULIDO-02: menú de hito legible (FlowLayout, scaffold, spinbox, scroll)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtGui import QFontMetrics
    from PySide6.QtWidgets import QApplication, QScrollArea

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.domain.causal_milestone import CausalMilestone  # noqa: E402
from packages.domain.result import Ok  # noqa: E402

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.design_system import FlowLayout, PanelScaffold
    from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class FakeMilestoneController:
    def __init__(self, hitos):
        self.hitos = list(hitos)

    def list_all(self):
        return list(self.hitos)

    def update(self, hito_id: str, data: dict):
        return Ok(None)


def _panel(qapp):
    hito = CausalMilestone(id="hito-1", title="Coronación")
    ctrl = FakeMilestoneController([hito])
    project = SimpleNamespace(
        entities=[], relations=[], causal_milestones=ctrl.hitos, project_chronology=None
    )
    ctx = SimpleNamespace(log=lambda *a, **k: None, drawer=None)
    return MilestoneDetailPanel(ctx, ctrl, "hito-1", project_getter=lambda: project)


class TestMilestonePanelPolish:
    def test_panel_is_a_scaffold_with_flow_badges(self, qapp):
        panel = _panel(qapp)
        assert isinstance(panel, PanelScaffold)
        assert isinstance(panel.badge_row, FlowLayout)
        # Dos badges (tipo + etiqueta temporal) que ENVUELVEN, sin stretch.
        assert panel.badge_row.count() == 2

    def test_end_year_special_text_fits(self, qapp):
        panel = _panel(qapp)
        assert panel.end_year_edit.specialValueText() == "— sin fin"
        metrics = QFontMetrics(panel.end_year_edit.font())
        needed = metrics.horizontalAdvance("— sin fin") + 2 * 24  # botones −/+
        assert panel.end_year_edit.minimumWidth() >= needed
        assert panel.end_year_edit.toolTip()  # el matiz largo vive en tooltip

    def test_exact_date_row_hides_entirely(self, qapp):
        # Sin calendario completo, la FILA entera (label incluida) desaparece.
        panel = _panel(qapp)
        assert panel._form.isRowVisible(panel.exact_date_picker) is False

    def test_panel_does_not_nest_its_own_scroll(self, qapp):
        # BETA2-FOCO-27: el panel ya NO anida un QScrollArea propio — es el scroll
        # del anfitrión (cajón inferior del Foco / RightDrawer) quien desplaza, así
        # el formulario y el calendario no quedan estrangulados ni recortados.
        panel = _panel(qapp)
        assert panel.findChildren(QScrollArea) == []

    def test_quick_create_form_scrolls(self, qapp):
        from hosts.DesktopHostPySide.widgets.chrono_canvas import MilestoneQuickCreatePanel

        meta = {"mode": "full_calendar", "months": ["Alba", "Bruma"]}
        panel = MilestoneQuickCreatePanel(default_year=100, calendar_meta=meta)
        scroll = panel.findChild(QScrollArea)
        assert scroll is not None
        assert scroll.maximumHeight() <= 360

    def test_adjacent_card_minimum_width_raised(self):
        source = Path("hosts/DesktopHostPySide/widgets/foco/foco_view.py").read_text(
            encoding="utf-8"
        )
        assert "max(320, min(440," in source
        assert "max(260, min(440," not in source
