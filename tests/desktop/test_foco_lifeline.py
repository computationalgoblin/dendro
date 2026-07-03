"""Cronología local de Foco: span arrastrable, hitos clicables y creación (BETA2-FOCO-10)."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402 — tras el guard HAS_QT
from packages.domain.causal_milestone import (  # noqa: E402 — tras el guard HAS_QT
    CausalMilestone,
    CausalMilestoneStatus,
)
from packages.domain.entity import NarrativeEntity  # noqa: E402 — tras el guard HAS_QT


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _band():
    from hosts.DesktopHostPySide.widgets.foco.foco_lifeline import FocoLifelineBand

    band = FocoLifelineBand()
    band.resize(640, 64)
    return band


def _entity(name="Eldrin", birth=1000, death=1050):
    return NarrativeEntity(name=name, birth_year=birth, death_year=death)


def _milestone(entity_id, title, year):
    return CausalMilestone(
        title=title,
        year=year,
        status=CausalMilestoneStatus.CANON,
        affected_entity_ids=[entity_id],
    )


class TestScaleAndMarks:
    def test_linear_scale_roundtrip(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [_milestone(entity.id, "Guerra", 1010)])

        assert band.x_at(1000) < band.x_at(1025) < band.x_at(1050)
        assert abs(band.year_at(band.x_at(1025)) - 1025) <= 1

    def test_milestone_hit_and_activation(self, qapp):
        band = _band()
        entity = _entity()
        milestone = _milestone(entity.id, "Guerra", 1010)
        band.set_entity(entity, [milestone])
        seen: list[str] = []
        band.milestoneActivated.connect(seen.append)

        assert band.milestone_at(band.x_at(1010)) == milestone.id
        band.activate_milestone(band.milestone_at(band.x_at(1010)))
        assert seen == [milestone.id]

    def test_undated_entity_shows_hint_without_crash(self, qapp):
        band = _band()
        band.set_entity(NarrativeEntity(name="Sin fechas"))
        assert band.span() == (None, None)
        band.repaint()  # pintado del estado "sin datación" no revienta offscreen


class TestSpanDrag:
    def test_drag_death_emits_global_signature(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [])
        seen: list[tuple] = []
        band.lifespanEdited.connect(lambda eid, birth, death: seen.append((eid, birth, death)))

        band.set_span_by_drag("death", 1080)
        assert seen == [(entity.id, 1000, 1080)]
        assert band.span() == (1000, 1080)

    def test_drag_birth_clamps_to_death(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [])
        seen: list[tuple] = []
        band.lifespanEdited.connect(lambda eid, birth, death: seen.append((eid, birth, death)))

        band.set_span_by_drag("birth", 1990)  # más allá de la muerte → clamp
        assert seen == [(entity.id, 1050, 1050)]

    def test_create_button_uses_span_midpoint(self, qapp):
        band = _band()
        entity = _entity()
        band.set_entity(entity, [])
        seen: list[tuple] = []
        band.milestoneCreateRequested.connect(lambda year, era: seen.append((year, era)))

        band._request_create()
        assert seen == [(1025, "")]


class TestFocoViewIntegration:
    def _setup(self):
        project_service = ProjectService()
        project_service.create("Lifeline")
        from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
            CausalMilestoneController,
        )
        from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
        from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

        ctx = SimpleNamespace(
            advanced_mode=False,
            log=lambda *args, **kwargs: None,
            animation_duration=lambda default=220: 0,
            request_save_silent=lambda: None,
            selected_entity_id=None,
            project_controller=SimpleNamespace(ps=project_service),
        )
        milestone_controller = CausalMilestoneController(project_service)
        view = FocoView(
            project_provider=lambda: project_service.active_project,
            ctx=ctx,
            entity_controller=EntityController(project_service),
            milestone_controller=milestone_controller,
        )
        return project_service, view

    def test_lifeline_loads_entity_and_milestones(self, qapp):
        project_service, view = self._setup()
        entity = _entity()
        project = project_service.active_project
        project.entities.append(entity)
        project.causal_milestones.append(_milestone(entity.id, "Guerra", 1010))
        project.touch()

        view.center_entity(entity.id, push_history=False)
        assert not view.lifeline.isHidden()
        assert view.lifeline.entity_id() == entity.id
        assert len(view.lifeline.milestone_ids()) == 1

    def test_span_edit_reemits_for_workspace_persistence(self, qapp):
        project_service, view = self._setup()
        entity = _entity()
        project_service.active_project.entities.append(entity)
        project_service.active_project.touch()
        view.center_entity(entity.id, push_history=False)
        seen: list[tuple] = []
        view.lifespanEdited.connect(lambda eid, birth, death: seen.append((eid, birth, death)))

        view.lifeline.set_span_by_drag("death", 1090)
        assert seen == [(entity.id, 1000, 1090)]

    def test_milestone_click_opens_adjacent_panel(self, qapp):
        project_service, view = self._setup()
        entity = _entity()
        project = project_service.active_project
        milestone = _milestone(entity.id, "Guerra", 1010)
        project.entities.append(entity)
        project.causal_milestones.append(milestone)
        project.touch()
        view.center_entity(entity.id, push_history=False)

        view.lifeline.activate_milestone(milestone.id)
        assert not view._adjacent_card.isHidden()
        assert view._adjacent_title.text() == "Hito"


class TestWorkspaceWiring:
    def test_lifeline_signals_reuse_global_slots(self):
        source = Path("hosts/DesktopHostPySide/views/workspaces.py").read_text(encoding="utf-8")
        assert "self.foco.lifespanEdited.connect(self._on_lifespan_edited)" in source
        assert (
            "self.foco.milestoneCreateRequested.connect(self._on_chrono_create_milestone)" in source
        )
