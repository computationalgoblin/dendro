"""BETA2-SUB-01: sección «Subhitos» del panel de detalle del hito."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402
from packages.persistence.store import ProjectStore  # noqa: E402

if HAS_QT:
    from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
        CausalMilestoneController,
    )
    from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _panel_for(ctrl, ps, milestone_id, **kwargs):
    ctx = SimpleNamespace(log=lambda *a, **k: None, drawer=None)
    return MilestoneDetailPanel(
        ctx, ctrl, milestone_id, project_getter=lambda: ps.active_project, **kwargs
    )


def _setup():
    ps = ProjectService(ProjectStore())
    ps.create(name="Sub")
    ctrl = CausalMilestoneController(ps)
    guerra = ctrl.create_manual({"title": "La Gran Guerra", "year": 100}).value
    batalla = ctrl.create_manual({"title": "Batalla del Vado", "year": 102}).value
    return ps, ctrl, guerra, batalla


class TestSubhitosPanel:
    def test_section_visible_for_marco(self, qapp):
        ps, ctrl, guerra, _ = _setup()
        panel = _panel_for(ctrl, ps, guerra.id)
        assert panel.subhitos_container.isVisibleTo(panel) or panel.subhitos_container.isVisible()
        # el combo ofrece a la batalla como candidata a subhito
        combo = panel.link_subhito_combo
        datas = [combo.itemData(i) for i in range(combo.count())]
        assert guerra.id not in datas  # nunca a sí mismo

    def test_link_existing_creates_containment(self, qapp):
        ps, ctrl, guerra, batalla = _setup()
        panel = _panel_for(ctrl, ps, guerra.id)
        # seleccionar la batalla en el combo y vincular
        idx = next(
            i for i in range(panel.link_subhito_combo.count())
            if panel.link_subhito_combo.itemData(i) == batalla.id
        )
        panel.link_subhito_combo.setCurrentIndex(idx)
        panel._link_existing_subhito()

        assert batalla.parent_milestone_id == guerra.id
        assert panel.subhitos_list.count() == 1

    def test_create_new_subhito_inline(self, qapp):
        ps, ctrl, guerra, _ = _setup()
        panel = _panel_for(ctrl, ps, guerra.id)
        panel.new_subhito_edit.setText("Asedio de la Ciudadela")
        panel._create_subhito()

        titles = [
            h.title
            for h in ps.active_project.causal_milestones
            if h.parent_milestone_id == guerra.id
        ]
        assert "Asedio de la Ciudadela" in titles
        assert panel.new_subhito_edit.text() == ""  # se limpia tras crear

    def test_remove_selected_orphans_subhito(self, qapp):
        ps, ctrl, guerra, batalla = _setup()
        ctrl.set_parent(batalla.id, guerra.id)
        panel = _panel_for(ctrl, ps, guerra.id)
        assert panel.subhitos_list.count() == 1
        panel.subhitos_list.setCurrentRow(0)
        panel._remove_selected_subhito()

        assert batalla.parent_milestone_id is None
        assert panel.subhitos_list.count() == 0

    def test_subhito_hides_section_and_shows_parent_badge(self, qapp):
        ps, ctrl, guerra, batalla = _setup()
        ctrl.set_parent(batalla.id, guerra.id)
        panel = _panel_for(ctrl, ps, batalla.id)
        # la sección se oculta (regla de 1 nivel)
        assert panel.subhitos_container.isVisible() is False
        # aparece el badge del marco
        badge_texts = [
            panel.badge_row.itemAt(i).widget().text()
            for i in range(panel.badge_row.count())
        ]
        assert any("Subhito de" in t for t in badge_texts)

    def test_double_click_opens_subhito_via_callback(self, qapp):
        ps, ctrl, guerra, batalla = _setup()
        ctrl.set_parent(batalla.id, guerra.id)
        opened = []
        panel = _panel_for(ctrl, ps, guerra.id, on_open_milestone=opened.append)
        item = panel.subhitos_list.item(0)
        panel._open_selected_subhito(item)
        assert opened == [batalla.id]
