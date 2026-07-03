"""Formulario central de Foco: relevancia, ghost-safe, relaciones clicables y
panel adyacente (BETA2-FOCO-09). Widgets REALES offscreen."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402 — tras el guard HAS_QT
from packages.domain.entity import (  # noqa: E402 — tras el guard HAS_QT
    CanonState,
    NarrativeEntity,
    NarrativeImportance,
)
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
    project_service.create("Formulario")
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController

    ctx = SimpleNamespace(
        advanced_mode=False,
        log=lambda *args, **kwargs: None,
        animation_duration=lambda default=220: 0,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        project_controller=SimpleNamespace(ps=project_service),
    )
    entity_controller = EntityController(project_service)
    relation_controller = RelationController(project_service)
    return project_service, ctx, entity_controller, relation_controller


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


def _panel(ctx, entity_controller, entity_id, **kwargs):
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

    return NodeDetailPanel(ctx, entity_controller, entity_id, **kwargs)


class TestRelevancia:
    def test_importance_combo_saves_through_controller(self, qapp):
        project_service, ctx, entity_controller, _ = _setup()
        entity = _entity(project_service, "Eldrin")
        panel = _panel(ctx, entity_controller, entity.id)

        index = panel.importance_combo.findData("alto")
        assert index >= 0
        panel.importance_combo.setCurrentIndex(index)
        panel._do_save(refresh_after=False)  # mismo camino que el autosave (800 ms)

        assert entity.narrative_importance == NarrativeImportance.ALTO

    def test_importance_loads_current_value(self, qapp):
        project_service, ctx, entity_controller, _ = _setup()
        entity = _entity(
            project_service, "Eldrin", narrative_importance=NarrativeImportance.CRITICO
        )
        panel = _panel(ctx, entity_controller, entity.id)
        assert panel.importance_combo.currentData() == "critico"


class TestGhostSafety:
    def test_ghost_keeps_canon_after_autosave(self, qapp):
        project_service, ctx, entity_controller, _ = _setup()
        ghost = _entity(project_service, "¿Sombra?", canon_state=CanonState.FANTASMA)
        panel = _panel(ctx, entity_controller, ghost.id)

        # El combo de canon queda oculto y aparece el aviso de fantasma.
        assert panel._is_ghost is True
        assert panel.canon_combo.isHidden()
        assert not panel.ghost_state_label.isHidden()

        panel.name_edit.setText("¿Sombra renombrada?")
        panel._do_save(refresh_after=False)

        assert ghost.canon_state == CanonState.FANTASMA  # ¡no se des-fantasma!
        assert ghost.name == "¿Sombra renombrada?"

    def test_normal_entity_still_saves_canon(self, qapp):
        project_service, ctx, entity_controller, _ = _setup()
        entity = _entity(project_service, "Real")
        panel = _panel(ctx, entity_controller, entity.id)
        panel.canon_combo.setCurrentIndex(1)  # Canónico
        panel._do_save(refresh_after=False)
        assert entity.canon_state == CanonState.CANONICO


class TestClickableRelations:
    def test_foco_variant_mounts_relations_and_links_open_adjacent(self, qapp):
        project_service, ctx, entity_controller, _ = _setup()
        center = _entity(project_service, "Centro")
        friend = _entity(project_service, "Aliada")
        relation = _relate(project_service, center, friend)
        opened: list[str] = []
        panel = _panel(
            ctx,
            entity_controller,
            center.id,
            variant="foco",
            on_open_relation=opened.append,
        )

        assert not panel.context_box.isHidden()  # listado EN el formulario
        assert relation.id in panel.relations_label.text()  # enlace con href al id
        panel.relations_label.linkActivated.emit(relation.id)
        assert opened == [relation.id]

    def test_drawer_variant_keeps_context_unmounted(self, qapp):
        project_service, ctx, entity_controller, _ = _setup()
        center = _entity(project_service, "Centro")
        panel = _panel(ctx, entity_controller, center.id)
        assert panel.context_box.isHidden()

    def test_foco_variant_hides_inline_ai_block(self, qapp):
        project_service, ctx, entity_controller, _ = _setup()
        center = _entity(project_service, "Centro")
        panel = _panel(ctx, entity_controller, center.id, variant="foco")
        assert panel.ai_generate_btn.isHidden()
        assert panel.suggestion_frame.isHidden()


class TestFocoViewFormAndAdjacent:
    def _view(self, project_service, ctx, entity_controller, relation_controller):
        from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

        return FocoView(
            project_provider=lambda: project_service.active_project,
            last_entity_setter=project_service.set_last_worked_entity,
            ctx=ctx,
            entity_controller=entity_controller,
            relation_controller=relation_controller,
        )

    def test_center_embeds_real_form_with_autosave_path(self, qapp):
        project_service, ctx, entity_controller, relation_controller = _setup()
        entity = _entity(project_service, "Eldrin")
        view = self._view(project_service, ctx, entity_controller, relation_controller)

        view.center_entity(entity.id, push_history=False)
        assert view._form_panel is not None
        assert view._form_panel.name_edit.text() == "Eldrin"
        assert not view._form_scroll.isHidden()

        view._form_panel.name_edit.setText("Eldrin el Sabio")
        view._form_panel._do_save(refresh_after=False)
        assert entity.name == "Eldrin el Sabio"

    def test_relation_link_opens_adjacent_panel_not_drawer(self, qapp):
        project_service, ctx, entity_controller, relation_controller = _setup()
        center = _entity(project_service, "Centro")
        friend = _entity(project_service, "Aliada")
        relation = _relate(project_service, center, friend)
        view = self._view(project_service, ctx, entity_controller, relation_controller)
        view.center_entity(center.id, push_history=False)

        view._open_relation_adjacent(relation.id)
        assert not view._adjacent_card.isHidden()
        assert view._adjacent_title.text() == "Relación"
        from hosts.DesktopHostPySide.widgets.relation_detail_panel import RelationDetailPanel

        assert isinstance(view._adjacent_scroll.widget(), RelationDetailPanel)

        view.close_adjacent()
        assert view._adjacent_card.isHidden()

    def test_recentering_closes_adjacent(self, qapp):
        project_service, ctx, entity_controller, relation_controller = _setup()
        center = _entity(project_service, "Centro")
        friend = _entity(project_service, "Aliada")
        relation = _relate(project_service, center, friend)
        view = self._view(project_service, ctx, entity_controller, relation_controller)
        view.center_entity(center.id, push_history=False)
        view._open_relation_adjacent(relation.id)

        view.center_entity(friend.id)
        assert view._adjacent_card.isHidden()
