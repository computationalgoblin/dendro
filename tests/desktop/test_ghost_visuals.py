"""Distinción visual del fantasma frente a entidad real (BETA2-FOCO-11).

El fantasma se pinta translúcido y con borde discontinuo (flag ``is_ghost`` del
satélite); una entidad real «falta regar» NO es translúcida. La distinción con
la Semilla IA llega en FOCO-13 (item de germinación propio).
"""

from __future__ import annotations

import os

import pytest

try:
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


def _view_with_neighbors():
    project_service = ProjectService()
    project_service.create("Visuales")
    project = project_service.active_project
    center = NarrativeEntity(name="Centro")
    normal = NarrativeEntity(name="Real sin regar")  # falta regar ≠ fantasma
    ghost = NarrativeEntity(name="¿Sombra?", canon_state=CanonState.FANTASMA)
    project.entities.extend([center, normal, ghost])
    for other in (normal, ghost):
        project.relations.append(
            NarrativeRelation(
                source_id=center.id, target_id=other.id, relation_type=RelationType.ES_ALIADO_DE
            )
        )
    project.touch()

    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    view = FocoView(project_provider=lambda: project)
    view.center_entity(center.id, push_history=False)
    return view, normal, ghost


class TestGhostVisualDistinction:
    def test_ghost_flag_only_on_ghosts(self, qapp):
        view, normal, ghost = _view_with_neighbors()
        assert view.canvas._items[ghost.id].is_ghost is True
        assert view.canvas._items[normal.id].is_ghost is False

    def test_ghost_paints_without_crashing_offscreen(self, qapp):
        view, _, ghost = _view_with_neighbors()
        view.resize(900, 600)
        view.canvas.viewport().repaint()  # translúcido + borde discontinuo, sin efectos Qt
        assert view.canvas._items[ghost.id].zone in {"raices", "entorno", "brotes"}
