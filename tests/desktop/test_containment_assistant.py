"""Asistente de contención del Foco: mover vs anidar (BETA2-FOCO-26)."""

from __future__ import annotations

import os

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from hosts.DesktopHostPySide.controllers.relation_controller import (  # noqa: E402
    RelationController,
)
from packages.application.foco_rings import direct_containments  # noqa: E402
from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.relation import NarrativeRelation, RelationType  # noqa: E402


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


def _setup():
    """Entidad contenida por la rama A; la rama B quiere contenerla también."""
    project_service = ProjectService()
    project_service.create("Contención")
    center = _entity(project_service, "Centro")
    branch_a = _entity(project_service, "Rama A", entity_type="contenedor")
    branch_b = _entity(project_service, "Rama B", entity_type="contenedor")
    old_relation = _relate(project_service, branch_a, center, RelationType.CONTIENE)
    return project_service, center, branch_a, branch_b, old_relation


def _view(project_service):
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    return FocoView(
        project_provider=lambda: project_service.active_project,
        relation_controller=RelationController(project_service),
    )


def _containments(project_service, entity_id):
    return direct_containments(project_service.active_project, entity_id)


class TestResolutionActions:
    def test_move_deletes_old_containment(self, qapp):
        project_service, center, branch_a, branch_b, old_relation = _setup()
        view = _view(project_service)
        view.center_entity(center.id)

        view._containment_move(branch_b.id, old_relation.id)
        containments = _containments(project_service, center.id)
        assert [cid for cid, _rid in containments] == [branch_b.id]

    def test_nest_builds_chain_old_contains_new_contains_entity(self, qapp):
        project_service, center, branch_a, branch_b, old_relation = _setup()
        view = _view(project_service)
        view.center_entity(center.id)

        view._containment_nest(branch_b.id, branch_a.id, old_relation.id)
        # La entidad vive SOLO en la rama nueva…
        assert [cid for cid, _rid in _containments(project_service, center.id)] == [branch_b.id]
        # …y la rama nueva vive dentro de la antigua (A ⊃ B ⊃ entidad).
        assert [cid for cid, _rid in _containments(project_service, branch_b.id)] == [
            branch_a.id
        ]

    def test_no_previous_containment_creates_directly(self, qapp):
        project_service = ProjectService()
        project_service.create("Sin conflicto")
        center = _entity(project_service, "Centro")
        branch = _entity(project_service, "Rama", entity_type="contenedor")
        view = _view(project_service)
        view.center_entity(center.id)

        view._contain_with_assistant(branch.id)  # sin overlay ⇒ ruta directa
        assert [cid for cid, _rid in _containments(project_service, center.id)] == [branch.id]

    def test_conflict_without_overlay_falls_back_to_move(self, qapp):
        # Respaldo defensivo: sin ModalOverlay el conflicto se resuelve moviendo.
        project_service, center, branch_a, branch_b, _old = _setup()
        view = _view(project_service)
        view.center_entity(center.id)

        view._contain_with_assistant(branch_b.id)
        assert [cid for cid, _rid in _containments(project_service, center.id)] == [branch_b.id]


class TestAssistantPanel:
    def test_panel_emits_decisions(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.containment_assistant import (
            ContainmentAssistantPanel,
        )

        panel = ContainmentAssistantPanel(
            entity_name="Centro", old_branch_name="Rama A", new_branch_name="Rama B"
        )
        seen: list[str] = []
        panel.moveChosen.connect(lambda: seen.append("move"))
        panel.nestChosen.connect(lambda: seen.append("nest"))
        panel.cancelled.connect(lambda: seen.append("cancel"))
        panel.move_button.click()
        panel.nest_button.click()
        assert seen == ["move", "nest"]
        # Ambas ramas y la entidad se NOMBRAN en las opciones (visual y claro).
        assert "Rama B" in panel.move_button.text()
        assert "Rama A" in panel.nest_button.text()

    def test_multi_parent_renders_as_also_in_chip_not_ancestor_chain(self, qapp):
        # FOCO-26: datos ya existentes con DOS madres directas — la primera es
        # el marco y la otra aparece como «también en X», no como abuela falsa.
        project_service, center, branch_a, branch_b, _old = _setup()
        _relate(project_service, branch_b, center, RelationType.CONTIENE)
        view = _view(project_service)
        view.resize(1100, 760)
        view.center_entity(center.id)

        frames = view.canvas._container_frames
        assert len(frames) == 1  # co-madre NO encadenada como ancestra
        assert frames[0].container_id == branch_a.id  # primera por nombre
        assert "también en" in frames[0].breadcrumb
        assert "Rama B" in frames[0].breadcrumb
