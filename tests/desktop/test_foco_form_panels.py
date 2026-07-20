"""Formulario central de Foco: relevancia, ghost-safe, relaciones clicables y
panel adyacente (BETA2-FOCO-09). Widgets REALES offscreen."""

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

        # BETA2-FOCO-16 (canon total): no hay combo de canon; aparece el aviso.
        assert panel._is_ghost is True
        assert not hasattr(panel, "canon_combo")
        assert not panel.ghost_state_label.isHidden()

        panel.name_edit.setText("¿Sombra renombrada?")
        panel._do_save(refresh_after=False)

        assert ghost.canon_state == CanonState.FANTASMA  # ¡no se des-fantasma!
        assert ghost.name == "¿Sombra renombrada?"

    def test_normal_entity_keeps_canon_on_autosave(self, qapp):
        # BETA2-FOCO-16 (canon total): el panel ya no emite canon_state — el
        # guardado conserva el estado existente tal cual.
        project_service, ctx, entity_controller, _ = _setup()
        entity = _entity(project_service, "Real", canon_state=CanonState.CANONICO)
        panel = _panel(ctx, entity_controller, entity.id)
        panel.name_edit.setText("Real renombrada")
        panel._do_save(refresh_after=False)
        assert entity.canon_state == CanonState.CANONICO
        assert entity.name == "Real renombrada"


class TestClickableRelations:
    # UI2-06: la lista viva de relaciones vive en su propia pestaña de la
    # tarjeta del Foco (FocoRelationsPanel), ya no dentro de NodeDetailPanel.

    @staticmethod
    def _relations_panel(ctx, entity_id, **kwargs):
        from hosts.DesktopHostPySide.widgets.foco.relations_panel import FocoRelationsPanel

        return FocoRelationsPanel(ctx, entity_id, **kwargs)

    def test_relations_tab_lists_all_relations_as_clickable_rows(self, qapp):
        # FOCO-20: lista REAL (una fila-botón por relación, sin tope de 6);
        # click en la fila → panel adyacente.
        from PySide6.QtWidgets import QPushButton

        project_service, ctx, entity_controller, _ = _setup()
        center = _entity(project_service, "Centro")
        friends = [_entity(project_service, f"Aliada {i}") for i in range(8)]
        relations = [_relate(project_service, center, friend) for friend in friends]
        opened: list[str] = []
        panel = self._relations_panel(ctx, center.id, on_open_relation=opened.append)

        rows = [
            panel._relations_rows.itemAt(i).widget()
            for i in range(panel._relations_rows.count())
        ]
        rows = [r for r in rows if isinstance(r, QPushButton)]
        assert len(rows) == 8  # TODAS las relaciones (antes: cap de 6)
        assert panel.relations_empty_label.isHidden()
        assert any("Aliada 0" in r.text() for r in rows)
        assert all(r.text().startswith(("→", "←", "↔")) for r in rows)

        rows[0].click()
        assert opened == [relations[0].id]

    def test_relations_plus_button_triggers_create_flow(self, qapp):
        project_service, ctx, entity_controller, _ = _setup()
        center = _entity(project_service, "Centro")
        created: list[bool] = []
        panel = self._relations_panel(
            ctx, center.id, on_create_relation=lambda: created.append(True)
        )
        assert not panel.add_relation_btn.isHidden()
        panel.add_relation_btn.click()
        assert created == [True]

    def test_node_panel_has_no_relations_section_in_any_variant(self, qapp):
        project_service, ctx, entity_controller, _ = _setup()
        center = _entity(project_service, "Centro")
        drawer_panel = _panel(ctx, entity_controller, center.id)
        # BETA2-UX-03: el resumen «Contexto» (context_box) muerto se eliminó.
        assert not hasattr(drawer_panel, "context_box")
        assert not hasattr(drawer_panel, "_relations_rows")
        # UI2-06: tampoco el variant foco — las relaciones son pestaña propia.
        foco_panel = _panel(ctx, entity_controller, center.id, variant="foco")
        assert not hasattr(foco_panel, "_relations_rows")

    def test_editor_has_no_more_options_no_milestones_and_importance_visible(self, qapp):
        # FOCO-20: «Más opciones» desapareció; hitos fuera del formulario;
        # Relevancia en el formulario principal.
        # UI2-20: «Convertir en rama» desapareció (ramitud derivada del tipo) y
        # el menú ⋯ queda oculto.
        project_service, ctx, entity_controller, _ = _setup()
        center = _entity(project_service, "Centro")
        panel = _panel(ctx, entity_controller, center.id, variant="foco")
        assert not hasattr(panel, "more_section")
        assert panel.related_milestones_panel is None
        assert panel.importance_combo.parent() is not None  # montada en el form
        assert not hasattr(panel, "convert_to_branch_action")
        assert panel.more_menu_btn.isHidden()
        source = Path("hosts/DesktopHostPySide/widgets/node_detail_panel.py").read_text(
            encoding="utf-8"
        )
        assert "AdvancedSection" not in source
        assert "FONT_SERIF" in source  # escritura serif editorial

    def test_type_combo_offers_all_types_and_branch_derives_from_type(self, qapp):
        # UI2-20: cualquier entidad ofrece TODOS los tipos; elegir un tipo de
        # rama la hace rama (marcador interno 'contenedor' + tree_type), elegir
        # un tipo de hoja la deja/vuelve hoja. Sin bloqueo del combo.
        from packages.domain.entity_taxonomy import OFFERED_ENTITY_TYPES, is_branch

        project_service, ctx, entity_controller, _ = _setup()
        leaf = _entity(project_service, "Protagonista")
        panel = _panel(ctx, entity_controller, leaf.id, variant="foco")
        # Los 11 tipos ofrecidos están en el combo.
        combo_values = {panel.type_combo.itemData(i) for i in range(panel.type_combo.count())}
        assert {t.value for t in OFFERED_ENTITY_TYPES} <= combo_values

        # Hoja → rama: elegir «facción» la convierte en rama.
        panel._set_combo_value(panel.type_combo, "faccion")
        panel._do_save(refresh_after=False)
        saved = project_service.active_project.entity_by_id(leaf.id)
        assert saved.entity_type.value == "contenedor"  # marcador interno
        assert is_branch(saved)
        assert (saved.custom_metadata or {}).get("tree_type") == "faccion"

        # Rama → hoja: elegir «personaje» la degrada (sin bloqueo).
        panel.refresh()
        assert panel.type_combo.currentText().lower().startswith("facci")  # muestra su tipo
        panel._set_combo_value(panel.type_combo, "personaje")
        panel._do_save(refresh_after=False)
        saved = project_service.active_project.entity_by_id(leaf.id)
        assert saved.entity_type.value == "personaje"
        assert not is_branch(saved)

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

        view.center_entity(entity.id)
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
        view.center_entity(center.id)

        view._open_relation_adjacent(relation.id)
        assert not view._adjacent_card.isHidden()
        assert view._adjacent_title.full_text() == "Relación"
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
        view.center_entity(center.id)
        view._open_relation_adjacent(relation.id)

        view.center_entity(friend.id)
        assert view._adjacent_card.isHidden()
