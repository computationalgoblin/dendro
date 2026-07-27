"""Modo dual de Foco (BETA2-FOCO-23): entidad ↔ relación ↔ entidad.

Se entra desde crear-entidad-relacionada, crear-relación-con-existente y
convertir/vincular fantasma; se sale con doble click sobre una de las dos
entidades (pasa a ser el foco único) o con Esc (vuelve a la previa).
Widgets REALES offscreen.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402 — tras el guard HAS_QT
from packages.domain.entity import CanonState, NarrativeEntity  # noqa: E402 — tras el guard HAS_QT
from packages.domain.relation import (  # noqa: E402 — tras el guard HAS_QT
    NarrativeRelation,
    RelationType,
)


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _setup():
    project_service = ProjectService()
    project_service.create("Dual")
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.ghost_controller import GhostController
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    ctx = SimpleNamespace(
        advanced_mode=False,
        log=lambda *args, **kwargs: None,
        animation_duration=lambda default=220: 0,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        project_controller=SimpleNamespace(ps=project_service),
    )
    view = FocoView(
        project_provider=lambda: project_service.active_project,
        last_entity_setter=project_service.set_last_worked_entity,
        ctx=ctx,
        entity_controller=EntityController(project_service),
        relation_controller=RelationController(project_service),
        ghost_service=GhostController(project_service),
    )
    view.resize(1200, 800)
    return project_service, view


def _entity(project_service, name, **kwargs):
    entity = NarrativeEntity(name=name, **kwargs)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _relate(project_service, source, target):
    relation = NarrativeRelation(
        source_id=source.id, target_id=target.id, relation_type=RelationType.ES_ALIADO_DE
    )
    project_service.active_project.relations.append(relation)
    project_service.active_project.touch()
    return relation


class TestDualEntryPoints:
    def test_create_related_enters_dual_with_both_forms_and_relation(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        view.center_entity(center.id)

        view._create_related({"name": "Nueva aliada", "entity_type": "nota"})

        assert view.is_dual_active()
        assert view._center_card.isHidden()
        panel_a, relation_panel, panel_b = view._dual_panels
        assert panel_a.entity_id == center.id
        assert panel_b.entity_id != center.id
        assert relation_panel.relation_id == view._dual["relation"]

    def test_relate_to_existing_enters_dual(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        other = _entity(project_service, "Existente")
        view.center_entity(center.id)

        view._relate_to(other.id)

        assert view.is_dual_active()
        assert view._dual["a"] == center.id
        assert view._dual["b"] == other.id

    def test_convert_ghost_enters_dual_when_related_to_center(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        view.center_entity(center.id)
        # Fantasma nacido vinculado al centro (ruta real del popover).
        view._create_ghost({"name": "¿Pendiente?"})
        ghost = next(
            e
            for e in project_service.active_project.entities
            if e.canon_state == CanonState.FANTASMA
        )

        view._convert_ghost(ghost.id)

        assert view.is_dual_active()
        assert view._dual["b"] == ghost.id
        assert ghost.canon_state == CanonState.CANONICO

    def test_link_ghost_enters_dual_with_link_target(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        real = _entity(project_service, "Real")
        view.center_entity(center.id)
        view._create_ghost({"name": "¿Alias?"})
        ghost = next(
            e
            for e in project_service.active_project.entities
            if e.canon_state == CanonState.FANTASMA
        )

        view._link_ghost(ghost.id, real.id)

        assert view.is_dual_active()
        assert view._dual["b"] == real.id


class TestDualEditingAndExit:
    def test_forms_edit_their_own_entities_without_crosstalk(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        other = _entity(project_service, "Existente")
        view.center_entity(center.id)
        view._relate_to(other.id)
        panel_a, _relation_panel, panel_b = view._dual_panels

        panel_a.name_edit.setText("Centro editado")
        panel_a._do_save(refresh_after=False)
        panel_b.name_edit.setText("Existente editada")
        panel_b._do_save(refresh_after=False)

        assert center.name == "Centro editado"
        assert other.name == "Existente editada"

    def test_double_click_on_entity_card_exits_and_centers_it(self, qapp):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QMouseEvent

        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        other = _entity(project_service, "Existente")
        view.center_entity(center.id)
        view._relate_to(other.id)
        _panel_a, _rel, panel_b = view._dual_panels

        event = QMouseEvent(
            QEvent.Type.MouseButtonDblClick,
            QPointF(5, 5),
            QPointF(5, 5),
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        handled = view.eventFilter(panel_b, event)

        assert handled is True
        assert not view.is_dual_active()
        assert view.current_entity_id() == other.id
        assert not view._center_card.isHidden()

    def test_escape_returns_to_previous_center(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        other = _entity(project_service, "Existente")
        view.center_entity(center.id)
        view._relate_to(other.id)
        assert view.is_dual_active()

        key_event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
        )
        handled = view.eventFilter(view._dual_card, key_event)

        assert handled is True
        assert not view.is_dual_active()
        assert view.current_entity_id() == center.id

    def test_centering_any_entity_abandons_dual(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        other = _entity(project_service, "Existente")
        third = _entity(project_service, "Tercera")
        view.center_entity(center.id)
        view._relate_to(other.id)
        assert view.is_dual_active()

        view.center_entity(third.id)

        assert not view.is_dual_active()
        assert view.current_entity_id() == third.id


class TestDualFromRelationsList:
    """UI2-13: pulsar una relación en la pestaña Relaciones abre el DUAL."""

    def test_open_relation_dual_resolves_endpoints(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        friend = _entity(project_service, "Aliada")
        relation = _relate(project_service, center, friend)
        view.center_entity(center.id)

        view._open_relation_dual(relation.id)

        assert view.is_dual_active()
        assert view._dual["a"] == center.id
        assert view._dual["b"] == friend.id
        assert view._dual["relation"] == relation.id

    def test_clicking_relation_row_enters_dual(self, qapp):
        from PySide6.QtWidgets import QPushButton

        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        friend = _entity(project_service, "Aliada")
        _relate(project_service, center, friend)
        view.center_entity(center.id)

        # WS-E: cada fila es ahora un contenedor (cápsula clicable + «×» de
        # borrado); descendemos para hallar el botón de la relación.
        containers = [
            view._relations_panel._relations_rows.itemAt(i).widget()
            for i in range(view._relations_panel._relations_rows.count())
        ]
        rows: list[QPushButton] = []
        for container in containers:
            if isinstance(container, QPushButton):
                rows.append(container)
            elif container is not None:
                rows.extend(container.findChildren(QPushButton))
        assert rows, "la pestaña Relaciones debe listar la relación"
        rows[0].click()

        assert view.is_dual_active()
        assert view._dual["b"] == friend.id

    def test_unresolvable_relation_falls_back_to_adjacent(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        view.center_entity(center.id)

        view._open_relation_dual("no-existe")

        assert not view.is_dual_active()  # fallback: nada revienta


class TestDualChronology:
    """BETA2-FOCO-29: cronología editable bajo las 3 columnas del dual."""

    def _setup_ms(self):
        project_service = ProjectService()
        project_service.create("DualChrono")
        from hosts.DesktopHostPySide.controllers.causal_milestone_controller import (
            CausalMilestoneController,
        )
        from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
        from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
        from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

        ctx = SimpleNamespace(
            advanced_mode=False,
            log=lambda *args, **kwargs: None,
            animation_duration=lambda default=220: 0,
            request_save_silent=lambda: None,
            selected_entity_id=None,
            project_controller=SimpleNamespace(ps=project_service),
        )
        view = FocoView(
            project_provider=lambda: project_service.active_project,
            ctx=ctx,
            entity_controller=EntityController(project_service),
            relation_controller=RelationController(project_service),
            milestone_controller=CausalMilestoneController(project_service),
        )
        view.resize(1400, 900)
        return project_service, view

    def _dual(self, ps, view):
        a = _entity(ps, "A", birth_year=0, death_year=100)
        b = _entity(ps, "B")  # sin datar
        rel = _relate(ps, a, b)
        view.center_entity(a.id)
        view.enter_dual(a.id, b.id, rel.id)
        return a, b, rel

    def test_three_editable_lapso_only_bands(self, qapp):
        ps, view = self._setup_ms()
        self._dual(ps, view)
        assert len(view._dual_lifelines) == 3
        assert all(bd is not None for bd in view._dual_lifelines)
        assert all(bd._lapso_only and not bd._read_only for bd in view._dual_lifelines)

    def test_entity_lapso_persists_and_dual_survives(self, qapp):
        ps, view = self._setup_ms()
        a, _b, _rel = self._dual(ps, view)
        view._dual_lifelines[0].set_span_by_drag("death", 80)
        assert ps.active_project.entity_by_id(a.id).death_year == 80
        assert view.is_dual_active()  # persistir NO desmonta el dual

    def test_undated_entity_lapso_definable_in_dual(self, qapp):
        ps, view = self._setup_ms()
        _a, b, _rel = self._dual(ps, view)
        view._dual_lifelines[2].set_span_by_drag("birth", 5)
        assert ps.active_project.entity_by_id(b.id).birth_year == 5

    def test_relation_lapso_persists_via_relation_controller(self, qapp):
        ps, view = self._setup_ms()
        _a, _b, rel = self._dual(ps, view)
        band_rel = view._dual_lifelines[1]
        band_rel.set_span_by_drag("birth", 10)
        band_rel.set_span_by_drag("death", 60)
        stored = next(r for r in ps.active_project.relations if r.id == rel.id)
        assert (stored.birth_year, stored.death_year) == (10, 60)
        assert view.is_dual_active()

    def test_hito_click_opens_bottom_sheet_over_dual(self, qapp):
        from hosts.DesktopHostPySide.widgets.milestone_detail_panel import MilestoneDetailPanel
        from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus

        ps, view = self._setup_ms()
        a, _b, _rel = self._dual(ps, view)
        milestone = CausalMilestone(
            title="Pacto", year=30, status=CausalMilestoneStatus.CANON, affected_entity_ids=[a.id]
        )
        ps.active_project.causal_milestones.append(milestone)
        ps.active_project.touch()
        view._dual_lifelines[0].activate_milestone(milestone.id)
        assert not view._bottom_sheet.isHidden()
        assert isinstance(view._bottom_sheet.content(), MilestoneDetailPanel)

    def test_exit_dual_clears_bands_and_closes_sheet(self, qapp):
        ps, view = self._setup_ms()
        self._dual(ps, view)
        view._bottom_sheet.open_over(view._dual_card.geometry())
        view.exit_dual()
        assert not view.is_dual_active()
        assert view._dual_lifelines == []
        assert view._bottom_sheet.isHidden()
