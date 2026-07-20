"""BETA2-PLAY-16 — modo preview de NodeDetailPanel y MilestoneDetailPanel.

El preview es la ficha REAL con el patch de la IA aplicado encima del canon:
sin autosave, guardado redirigido a callback (solo el diff), canon intacto.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ctx():
    return SimpleNamespace(
        log=lambda *a, **k: None,
        advanced_mode=False,
        animation_duration=lambda ms: 0,
        selected_entity_id="",
        project_controller=None,
        drawer=None,
    )


def _entity_setup():
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from packages.application.project_service import ProjectService

    ps = ProjectService()
    ps.create("Preview entidad")
    ctrl = EntityController(ps)
    entity = ctrl.create(
        {"name": "Aldric", "entity_type": "personaje", "brief_description": "Un herrero."}
    ).value
    return ps, ctrl, entity


class TestEntityPreview:
    def _panel(self, ctrl, entity, patch, captured):
        from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

        panel = NodeDetailPanel(
            _ctx(),
            ctrl,
            entity.id,
            variant="foco",
            preview_patch=patch,
            on_preview_save=captured.append,
        )
        panel.refresh()
        return panel

    def test_preview_shows_canon_with_patch_applied_and_highlight(self, qapp):
        _ps, ctrl, entity = _entity_setup()
        captured: list[dict] = []
        patch = {"name": "Aldric el Roto", "brief_description": "Herrero marcado."}

        panel = self._panel(ctrl, entity, patch, captured)

        assert panel.name_edit.text() == "Aldric el Roto"  # patch encima del canon
        assert panel.brief_edit.toPlainText() == "Herrero marcado."
        assert "Propuesta de la IA" in panel.name_edit.toolTip()
        assert panel.extended_edit.toolTip() == ""  # sin patch, sin resaltado

    def test_preview_payload_is_diff_only_and_canon_untouched(self, qapp):
        ps, ctrl, entity = _entity_setup()
        captured: list[dict] = []
        patch = {"name": "Aldric el Roto", "birth_year": -120}  # birth_year no se renderiza

        panel = self._panel(ctrl, entity, patch, captured)
        panel.brief_edit.setPlainText("Retoque del usuario.")  # edición humana en preview
        panel._do_save(refresh_after=False)

        assert len(captured) == 1
        diff = captured[0]
        assert diff["name"] == "Aldric el Roto"
        assert diff["brief_description"] == "Retoque del usuario."
        assert diff["birth_year"] == -120  # campo no renderizado viaja tal cual
        assert "extended_description" not in diff  # sin cambio ⇒ fuera del diff
        # El canon NO cambió: el preview jamás escribe.
        canon = ps.active_project.entities[0]
        assert canon.name == "Aldric"
        assert canon.brief_description == "Un herrero."

    def test_normal_mode_still_autosaves_to_canon(self, qapp):
        ps, ctrl, entity = _entity_setup()
        from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

        panel = NodeDetailPanel(_ctx(), ctrl, entity.id, variant="foco")
        panel.refresh()
        panel.name_edit.setText("Aldric Renombrado")
        panel._do_save(refresh_after=False)

        assert ps.active_project.entities[0].name == "Aldric Renombrado"


class TestMilestonePreview:
    def _setup(self):
        from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
            CausalMilestoneController,
        )
        from packages.application.project_service import ProjectService

        ps = ProjectService()
        ps.create("Preview hito")
        ctrl = CausalMilestoneController(ps)
        hito = ctrl.create_manual({"title": "nuevo hito", "year": 100}).value
        return ps, ctrl, hito

    def test_preview_applies_patch_and_emits_diff_only(self, qapp):
        ps, ctrl, hito = self._setup()
        from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel

        captured: list[dict] = []
        panel = MilestoneDetailPanel(
            _ctx(),
            ctrl,
            hito.id,
            preview_patch={"title": "La Purga", "year": 412},
            on_preview_save=captured.append,
        )

        assert panel.title_edit.text() == "La Purga"
        assert int(panel.year_edit.value()) == 412
        assert "Propuesta de la IA" in panel.title_edit.toolTip()

        panel._do_save(reload_after=False)

        assert captured == [{"title": "La Purga", "year": 412}]  # SOLO el diff
        canon = ps.active_project.causal_milestones[0]
        assert canon.title == "nuevo hito"  # canon intacto
        assert canon.year == 100
