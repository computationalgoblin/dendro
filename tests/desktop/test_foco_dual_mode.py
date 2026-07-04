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


class TestDualEntryPoints:
    def test_create_related_enters_dual_with_both_forms_and_relation(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        view.center_entity(center.id, push_history=False)

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
        view.center_entity(center.id, push_history=False)

        view._relate_to(other.id)

        assert view.is_dual_active()
        assert view._dual["a"] == center.id
        assert view._dual["b"] == other.id

    def test_convert_ghost_enters_dual_when_related_to_center(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        view.center_entity(center.id, push_history=False)
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
        view.center_entity(center.id, push_history=False)
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
        view.center_entity(center.id, push_history=False)
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
        view.center_entity(center.id, push_history=False)
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
        view.center_entity(center.id, push_history=False)
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
        view.center_entity(center.id, push_history=False)
        view._relate_to(other.id)
        assert view.is_dual_active()

        view.center_entity(third.id)

        assert not view.is_dual_active()
        assert view.current_entity_id() == third.id
