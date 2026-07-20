"""UI2-06: tarjeta central del Foco con pestañas Ficha/Relaciones/Cultivo.

La tarjeta respira: una superficie a la vez (stack), el retrato de la TARJETA
queda a la izquierda en todas las pestañas, la pestaña activa se recuerda entre
recentrados y el modo resumen (sin controllers) sigue sin pestañas.
"""

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

from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _setup():
    project_service = ProjectService()
    project_service.create("Pestañas")
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.controllers.relation_controller import RelationController

    ctx = SimpleNamespace(
        advanced_mode=False,
        log=lambda *args, **kwargs: None,
        animation_duration=lambda default=220: 0,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        project_controller=SimpleNamespace(ps=project_service, current_path=None),
    )
    entity_controller = EntityController(project_service)
    relation_controller = RelationController(project_service)
    return project_service, ctx, entity_controller, relation_controller


def _entity(project_service, name):
    entity = NarrativeEntity(name=name)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _view(project_service, ctx, entity_controller, relation_controller):
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    return FocoView(
        project_provider=lambda: project_service.active_project,
        ctx=ctx,
        entity_controller=entity_controller,
        relation_controller=relation_controller,
    )


class TestFocoTabs:
    def test_three_tabs_and_form_survives_tab_changes(self, qapp):
        project_service, ctx, entity_controller, relation_controller = _setup()
        entity = _entity(project_service, "Eldrin")
        view = _view(project_service, ctx, entity_controller, relation_controller)
        view.center_entity(entity.id)

        assert view._tab_stack.count() == 3
        assert view._tab_bar.current() == "ficha"
        form_panel = view._form_panel
        assert form_panel is not None
        # Cambiar de pestaña NO desmonta el formulario (autosave intacto).
        view._tab_bar.set_current("relaciones")
        assert view._form_panel is form_panel
        assert view._tab_stack.currentWidget() is view._relations_scroll
        view._tab_bar.set_current("cultivo")
        assert view._tab_stack.currentWidget() is view._cultivo_scroll
        assert view.notebook is not None

    def test_active_tab_survives_recentering(self, qapp):
        project_service, ctx, entity_controller, relation_controller = _setup()
        first = _entity(project_service, "Uno")
        second = _entity(project_service, "Dos")
        view = _view(project_service, ctx, entity_controller, relation_controller)
        view.center_entity(first.id)
        view._tab_bar.set_current("cultivo")
        view.center_entity(second.id)
        assert view._tab_bar.current() == "cultivo"
        assert view._tab_stack.currentWidget() is view._cultivo_scroll

    def test_name_label_always_visible_on_reading_card(self, qapp):
        # UI2-16: la tarjeta es un display de LECTURA — el título fijo no
        # depende de la pestaña (las pestañas viven en el editor fullscreen,
        # que tiene su propia cabecera con el nombre).
        project_service, ctx, entity_controller, relation_controller = _setup()
        entity = _entity(project_service, "Eldrin")
        view = _view(project_service, ctx, entity_controller, relation_controller)
        view.center_entity(entity.id)
        assert not view._name_label.isHidden()
        assert view._name_label.full_text() == "Eldrin"
        view._tab_bar.set_current("relaciones")
        assert not view._name_label.isHidden()
        # El editor fullscreen vive como overlay y aloja las pestañas.
        assert view._editor_overlay.isAncestorOf(view._tab_stack)
        assert view._editor_overlay.isAncestorOf(view._tab_bar)

    def test_portrait_band_belongs_to_card_and_spans_tabs(self, qapp):
        project_service, ctx, entity_controller, relation_controller = _setup()
        entity = _entity(project_service, "Eldrin")
        view = _view(project_service, ctx, entity_controller, relation_controller)
        view.center_entity(entity.id)
        # La banda es de la tarjeta (no del formulario) y es la MISMA instancia
        # en todas las pestañas; sin imagen queda oculta.
        assert view._form_panel.portrait_band is None
        band = view.portrait_band
        assert band.parentWidget() is view._center_card
        view._tab_bar.set_current("relaciones")
        assert view.portrait_band is band
        assert band.isHidden()  # la entidad no tiene retrato

    def test_summary_mode_has_no_tabs(self, qapp):
        # Sin controllers (modo resumen) la tarjeta sigue siendo la de siempre
        # y el editor fullscreen ni existe como opción (sin ⛶, overlay cerrado).
        from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

        project_service, _, _, _ = _setup()
        entity = _entity(project_service, "Solo lectura")
        view = FocoView(project_provider=lambda: project_service.active_project)
        view.center_entity(entity.id)
        assert view._form_panel is None
        assert not view._editor_open
        assert not view._editor_overlay.isVisible()
        assert not view._tab_bar.isVisible()  # vive en el overlay cerrado
        assert view._expand_button.isHidden()
        assert not view._name_label.isHidden()

    def test_relations_tab_hosts_live_panel(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.relations_panel import FocoRelationsPanel

        project_service, ctx, entity_controller, relation_controller = _setup()
        entity = _entity(project_service, "Eldrin")
        view = _view(project_service, ctx, entity_controller, relation_controller)
        view.center_entity(entity.id)
        panel = view._relations_scroll.widget()
        assert isinstance(panel, FocoRelationsPanel)
        assert not panel.relations_empty_label.isHidden()  # sin relaciones aún
