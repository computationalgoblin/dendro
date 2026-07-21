"""Modo Foco por defecto: última entidad, estado vacío y cableado de modos (BETA2-FOCO-08).

FocoView/FocoCanvas se prueban como widgets REALES (offscreen). El cableado del
workspace (3 modos, arranque en foco, command bar oculta en cronología) se
verifica con pins de fuente, patrón de la casa (``test_beta1_chrono_view``):
construir el CreationWorkspace completo headless cuelga PySide6.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402 — tras el guard HAS_QT
from packages.domain.entity import NarrativeEntity  # noqa: E402 — tras el guard HAS_QT

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _services():
    project_service = ProjectService()
    project_service.create("Foco")
    return project_service


def _entity(project_service, name):
    entity = NarrativeEntity(name=name)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _view(project_service):
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    return FocoView(
        project_provider=lambda: project_service.active_project,
        last_entity_getter=lambda: getattr(
            project_service.get_last_worked_entity(), "value", ""
        ),
        last_entity_setter=project_service.set_last_worked_entity,
    )


class TestFocoDefault:
    def test_empty_project_shows_empty_state(self, qapp):
        project_service = _services()
        view = _view(project_service)
        view.refresh()
        assert not view._empty.isHidden()
        assert view._center_card.isHidden()
        assert view.current_entity_id() == ""

    def test_last_worked_entity_is_centered(self, qapp):
        project_service = _services()
        _entity(project_service, "Primera")
        second = _entity(project_service, "Segunda")
        project_service.set_last_worked_entity(second.id)

        view = _view(project_service)
        view.refresh()
        assert view.current_entity_id() == second.id
        assert view._name_label.full_text() == "Segunda"
        assert not view._center_card.isHidden()
        assert view._empty.isHidden()

    def test_first_entity_when_no_last_worked(self, qapp):
        project_service = _services()
        first = _entity(project_service, "Primera")
        _entity(project_service, "Segunda")

        view = _view(project_service)
        view.refresh()
        assert view.current_entity_id() == first.id

    def test_centering_remembers_last_worked(self, qapp):
        project_service = _services()
        first = _entity(project_service, "Primera")
        second = _entity(project_service, "Segunda")
        view = _view(project_service)
        view.refresh()
        assert view.current_entity_id() == first.id

        view.center_entity(second.id)
        assert project_service.get_last_worked_entity().value == second.id

    def test_stale_last_worked_falls_back(self, qapp):
        project_service = _services()
        first = _entity(project_service, "Primera")
        ghost_id = "ya-no-existe"
        project_service.active_project.metadata["last_worked_entity_id"] = ghost_id

        view = _view(project_service)
        view.refresh()
        assert view.current_entity_id() == first.id


class TestWorkspaceWiring:
    """Pins de fuente del cableado en CreationWorkspace (patrón beta1_chrono_view)."""

    def test_three_modes_and_default_foco(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        # BETA2-PLAY: "play" es el cuarto estado (fuera de la píldora de modos).
        assert 'if view not in ("foco", "concentric", "chrono", "play"):' in source
        assert 'self.set_active_view("foco")' in source  # arranque SIEMPRE en foco
        assert "self.foco = FocoView(" in source
        assert "def set_active_view" in source
        assert "creation/active_view" in source  # clave QSettings conservada (compat)

    def test_command_bar_fully_removed(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        # Limpieza post-WIKI (2026-07-21): la command bar se BORRÓ físicamente
        # (antes solo estaba apagada tras _LEGACY_AI_UI). Pin de ausencia.
        assert "_build_command_bar" not in source
        assert "_LEGACY_AI_UI" not in source

    def test_mode_pill_and_foco_refresh_wiring(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "_update_mode_pill" in source
        assert "foco_widget.refresh()" in source
        assert "_foco_open_in_map" in source and "_foco_open_in_chrono" in source
