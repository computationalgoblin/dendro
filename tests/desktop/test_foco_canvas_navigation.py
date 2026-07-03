"""Navegación del lienzo de Foco: click centra, flechas por zonas, Ctrl+click (BETA2-FOCO-08)."""

from __future__ import annotations

import os

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


def _entity(project_service, name, **kwargs):
    entity = NarrativeEntity(name=name, **kwargs)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _relate(project_service, source, target, relation_type):
    relation = NarrativeRelation(
        source_id=source.id, target_id=target.id, relation_type=relation_type
    )
    project_service.active_project.relations.append(relation)
    project_service.active_project.touch()
    return relation


def _garden():
    """Centro con raíz causal, brote, dos vecinas planas, rama contenedora y fantasma."""
    project_service = ProjectService()
    project_service.create("Jardín Foco")
    center = _entity(project_service, "Centro")
    root = _entity(project_service, "Guerra previa")
    sprout = _entity(project_service, "Derivada")
    alfa = _entity(project_service, "Alfa")
    beta = _entity(project_service, "Beta")
    branch = _entity(project_service, "Rama madre", entity_type="contenedor")
    ghost = _entity(project_service, "¿Sombra?", canon_state=CanonState.FANTASMA)
    _relate(project_service, root, center, RelationType.CAUSO)
    _relate(project_service, center, sprout, RelationType.CAUSO)
    _relate(project_service, center, alfa, RelationType.ES_ALIADO_DE)
    _relate(project_service, center, beta, RelationType.ES_ALIADO_DE)
    _relate(project_service, branch, center, RelationType.CONTIENE)
    _relate(project_service, ghost, center, RelationType.CAUSO)
    return project_service, center, root, sprout, alfa, beta, branch, ghost


def _view(project_service):
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    view = FocoView(
        project_provider=lambda: project_service.active_project,
        last_entity_setter=project_service.set_last_worked_entity,
    )
    return view


def _press(view, key):
    event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    view.canvas.keyPressEvent(event)


class TestClickAndZones:
    def test_click_on_satellite_centers_it(self, qapp):
        project_service, center, root, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id, push_history=False)

        view.canvas._on_item_clicked(root.id, ctrl=False)
        assert view.current_entity_id() == root.id

    def test_zones_feed_the_canvas_in_order(self, qapp):
        project_service, center, root, sprout, alfa, beta, branch, ghost = _garden()
        view = _view(project_service)
        view.center_entity(center.id, push_history=False)

        assert set(view.canvas.zone_ids("raices")) == {root.id, ghost.id}
        assert view.canvas.zone_ids("brotes") == [sprout.id]
        # Entorno ordenado por nombre: Alfa, Beta, Rama madre (contenedora).
        assert view.canvas.zone_ids("entorno") == [alfa.id, beta.id, branch.id]
        assert view.canvas.container_ids() == [branch.id]
        ghost_item = view.canvas._items[ghost.id]
        assert ghost_item.is_ghost is True  # translúcido/borrador en el lienzo

    def test_ctrl_click_accumulates_highlight_without_recentering(self, qapp):
        project_service, center, _, _, alfa, beta, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id, push_history=False)
        seen: list[list[str]] = []
        view.canvas.selectionChanged.connect(seen.append)

        view.canvas._on_item_clicked(alfa.id, ctrl=True)
        view.canvas._on_item_clicked(beta.id, ctrl=True)
        assert view.canvas.selected_ids() == [alfa.id, beta.id]
        assert view.current_entity_id() == center.id  # la central sigue siendo una
        assert seen[-1] == [alfa.id, beta.id]

        view.canvas._on_item_clicked(alfa.id, ctrl=True)  # toggle fuera
        assert view.canvas.selected_ids() == [beta.id]


class TestArrowNavigation:
    def test_right_goes_to_first_entorno(self, qapp):
        project_service, center, _, _, alfa, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id, push_history=False)
        _press(view, Qt.Key.Key_Right)
        assert view.current_entity_id() == alfa.id

    def test_left_goes_to_last_entorno(self, qapp):
        project_service, center, _, _, _, _, branch, _ = _garden()
        view = _view(project_service)
        view.center_entity(center.id, push_history=False)
        _press(view, Qt.Key.Key_Left)
        assert view.current_entity_id() == branch.id

    def test_up_prioritizes_container_then_roots(self, qapp):
        project_service, center, root, _, _, _, branch, _ = _garden()
        view = _view(project_service)
        view.center_entity(center.id, push_history=False)
        _press(view, Qt.Key.Key_Up)
        assert view.current_entity_id() == branch.id  # contenedora primero
        _press(view, Qt.Key.Key_Up)
        # La rama no tiene contenedora: sube a sus Raíces si las hay (no destructivo).

    def test_down_goes_to_first_sprout(self, qapp):
        project_service, center, _, sprout, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id, push_history=False)
        _press(view, Qt.Key.Key_Down)
        assert view.current_entity_id() == sprout.id

    def test_arrow_without_target_is_noop(self, qapp):
        project_service = ProjectService()
        project_service.create("Solitaria")
        lonely = _entity(project_service, "Sola")
        view = _view(project_service)
        view.center_entity(lonely.id, push_history=False)

        for key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            _press(view, key)
            assert view.current_entity_id() == lonely.id


class TestFocusHistory:
    def test_back_returns_to_previous_focus(self, qapp):
        project_service, center, root, *_ = _garden()
        view = _view(project_service)
        view.center_entity(center.id, push_history=False)

        view.center_entity(root.id)  # navega (push)
        assert view.history_ids() == [center.id]
        assert not view._back_button.isHidden()

        view.go_back()
        assert view.current_entity_id() == center.id
        assert view.history_ids() == []
