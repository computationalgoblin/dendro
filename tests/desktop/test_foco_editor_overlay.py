"""UI2-16/17: editor de entidad a pantalla completa (EntityEditorOverlay).

La tarjeta central es un display de LECTURA (⛶ abre el editor); el fullscreen
aloja las pestañas Ficha/Relaciones/Cultivo, hereda la navegación por flechas
sin cerrarse y nunca coexiste con el modo dual.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.relation import (  # noqa: E402
    NarrativeRelation,
    RelationType,
)


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _setup():
    project_service = ProjectService()
    project_service.create("Editor")
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    ctx = SimpleNamespace(
        advanced_mode=False,
        log=lambda *args, **kwargs: None,
        animation_duration=lambda default=220: 0,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        project_controller=SimpleNamespace(ps=project_service, current_path=None),
    )
    view = FocoView(
        project_provider=lambda: project_service.active_project,
        ctx=ctx,
        entity_controller=EntityController(project_service),
        relation_controller=RelationController(project_service),
    )
    view.resize(1200, 800)
    return project_service, view


def _entity(project_service, name):
    entity = NarrativeEntity(name=name)
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


class TestReadingCard:
    def test_card_shows_meta_summary_and_expand_button(self, qapp):
        project_service, view = _setup()
        entity = _entity(project_service, "Eldrin")
        view.center_entity(entity.id)
        assert not view._expand_button.isHidden()
        assert not view._meta_summary_box.isHidden()
        assert view._meta_summary.count() >= 2  # tipo + relevancia como mínimo
        assert not view._name_label.isHidden()
        assert not view._editor_open

    def test_editor_card_is_editorial_column(self, qapp):
        project_service, view = _setup()
        overlay = view._editor_overlay
        assert overlay.editor_card.maximumWidth() == 900
        assert overlay.isAncestorOf(view._tab_stack)


class TestOpenClose:
    def test_expand_opens_and_close_returns(self, qapp):
        project_service, view = _setup()
        entity = _entity(project_service, "Eldrin")
        view.center_entity(entity.id)
        view.open_editor()
        assert view._editor_open
        assert not view._editor_overlay.isHidden()
        assert view._editor_overlay.geometry() == view.rect()
        assert view._editor_overlay.name_label.full_text() == "Eldrin"
        view._editor_overlay.close_button.click()
        assert not view._editor_open
        assert view._editor_overlay.isHidden()

    def test_editor_persists_across_recentering(self, qapp):
        project_service, view = _setup()
        first = _entity(project_service, "Uno")
        second = _entity(project_service, "Dos")
        view.center_entity(first.id)
        view.open_editor()
        form_before = view._form_panel
        view.center_entity(second.id)
        assert view._editor_open  # sigue abierto
        assert view._form_panel is not form_before  # remontado
        assert view._form_panel.entity_id == second.id
        assert view._editor_overlay.name_label.full_text() == "Dos"
        # UI2-18: la tarjeta de LECTURA no reaparece por encima del editor.
        assert view._center_card.isHidden()

    def test_expand_button_is_top_right(self, qapp):
        project_service, view = _setup()
        entity = _entity(project_service, "Eldrin")
        view.center_entity(entity.id)
        card_w = view._center_card.width()
        # UI2-18: ⛶ anclado al borde DERECHO (antes x=10 fijo = izquierda,
        # solapando el nombre). El borde derecho del botón queda a 10px del borde.
        assert view._expand_button.x() + view._expand_button.width() == card_w - 10
        if card_w > 100:
            assert view._expand_button.x() > card_w // 2

    def test_summary_mode_has_no_editor(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

        project_service = ProjectService()
        project_service.create("Resumen")
        entity = _entity(project_service, "Sola")
        view = FocoView(project_provider=lambda: project_service.active_project)
        view.center_entity(entity.id)
        view.open_editor()  # guard: sin controllers no hay edición
        assert not view._editor_open


class TestNavigation:
    def test_header_arrows_navigate_without_closing(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        friend = _entity(project_service, "Aliada")
        _relate(project_service, center, friend)
        view.center_entity(center.id)
        view.open_editor()
        # La aliada comparte anillo: → debe llevar a ella (destino real).
        target = view.canvas._arrow_target(Qt.Key.Key_Right, shift=False)
        if target:
            view._editor_overlay.nav_right.click()
            assert view.current_entity_id() == target
            assert view._editor_open  # sin salir del fullscreen
        else:
            # Sin destino el botón queda gris y el clic es inocuo.
            assert not view._editor_overlay.nav_right.isEnabled()

    def test_nav_enabled_reflects_real_targets(self, qapp):
        project_service, view = _setup()
        lonely = _entity(project_service, "Solitaria")
        view.center_entity(lonely.id)
        view.open_editor()
        # Entidad sin vecinas: todas las flechas gris.
        assert not view._editor_overlay.nav_left.isEnabled()
        assert not view._editor_overlay.nav_right.isEnabled()
        assert not view._editor_overlay.nav_up.isEnabled()

    def test_navigation_preserves_active_tab(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        friend = _entity(project_service, "Aliada")
        _relate(project_service, center, friend)
        view.center_entity(center.id)
        view.open_editor()
        view._tab_bar.set_current("relaciones")
        assert view._tab_bar.current() == "relaciones"
        target = view.canvas._arrow_target(Qt.Key.Key_Right, shift=False)
        if not target:
            pytest.skip("sin destino de navegación en este layout")
        view._editor_overlay.nav_right.click()
        assert view._editor_open
        # UI2-18: la pestaña activa (Relaciones) se conserva en la entidad siguiente.
        assert view._tab_bar.current() == "relaciones"
        # ...y la tarjeta de lectura no reaparece durante la navegación.
        assert view._center_card.isHidden()


class TestDualInterplay:
    def test_opening_dual_closes_editor_and_exit_does_not_reopen(self, qapp):
        project_service, view = _setup()
        center = _entity(project_service, "Centro")
        friend = _entity(project_service, "Aliada")
        relation = _relate(project_service, center, friend)
        view.center_entity(center.id)
        view.open_editor()

        view._open_relation_dual(relation.id)
        assert view.is_dual_active()
        assert not view._editor_open  # el dual manda

        view.exit_dual()
        assert not view.is_dual_active()
        assert not view._editor_open  # NO se reabre (decisión de diseño)
        assert not view._center_card.isHidden()


class TestLiveUpdate:
    """UI2-19: un cambio en el editor se ve al instante en la tarjeta de lectura."""

    def test_brief_edit_reflects_on_reading_card_after_save(self, qapp):
        project_service, view = _setup()
        entity = _entity(project_service, "Bio")
        view.center_entity(entity.id)
        view.open_editor()
        view._form_panel.brief_edit.setPlainText("Una nueva biografía viva")
        view._form_panel._autosave()  # simula el debounce del autoguardado
        saved = project_service.active_project.entity_by_id(entity.id)
        assert saved.brief_description == "Una nueva biografía viva"
        assert "Una nueva biografía viva" in view._brief_label.text()

    def test_close_editor_flushes_pending_and_refreshes_brief(self, qapp):
        project_service, view = _setup()
        entity = _entity(project_service, "Cierre")
        view.center_entity(entity.id)
        view.open_editor()
        # Escribir y cerrar SIN esperar al temporizador: close_editor debe volcar
        # el autoguardado pendiente y refrescar la tarjeta.
        view._form_panel.brief_edit.setPlainText("Escrito y cerrado")
        view.close_editor()
        assert not view._editor_open
        saved = project_service.active_project.entity_by_id(entity.id)
        assert saved.brief_description == "Escrito y cerrado"
        assert "Escrito y cerrado" in view._brief_label.text()
        assert not view._center_card.isHidden()


class TestLifespanChronology:
    """BETA2-FOCO-27: la cronología se muda entre descripción (solo lectura) y el
    pie del editor (editable); el cajón inferior del hito vive en el overlay."""

    def test_reading_card_lifeline_is_read_only(self, qapp):
        project_service, view = _setup()
        entity = _entity(project_service, "Eldrin")
        view.center_entity(entity.id)
        assert view.lifeline._read_only is True
        assert view.lifeline._add_button.isHidden()
        # La banda vive en el slot de la tarjeta de lectura.
        assert view._lifeline_slot.indexOf(view.lifeline) >= 0

    def test_editor_moves_lifeline_to_footer_editable(self, qapp):
        project_service, view = _setup()
        entity = _entity(project_service, "Eldrin")
        view.center_entity(entity.id)
        view.open_editor()
        assert view.lifeline._read_only is False
        assert not view.lifeline._add_button.isHidden()
        assert view._editor_overlay.footer_slot.indexOf(view.lifeline) >= 0
        # Al cerrar vuelve a la tarjeta en SOLO lectura.
        view.close_editor()
        assert view.lifeline._read_only is True
        assert view._lifeline_slot.indexOf(view.lifeline) >= 0

    def test_relations_tab_has_create_related_button(self, qapp):
        project_service, view = _setup()
        entity = _entity(project_service, "Eldrin")
        view.center_entity(entity.id)
        view.open_editor()
        panel = view._relations_panel
        assert hasattr(panel, "add_related_btn")
        assert not panel.add_related_btn.isHidden()  # on_create_related está cableado

    def test_bottom_sheet_is_child_of_view(self, qapp):
        # BETA2-FOCO-29: el cajón inferior es hijo de la VISTA (no del overlay del
        # editor) para poder abrirse también sobre la tarjeta dual.
        project_service, view = _setup()
        assert view._bottom_sheet.parent() is view
        assert view._bottom_sheet.isHidden()
