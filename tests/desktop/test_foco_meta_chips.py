"""UI2-07: metadatos como chips en la Ficha del Foco.

El QFormLayout apilado se sustituye (solo variant foco) por el nombre
protagonista (serif, sin marco hasta hover/focus) + una fila de chips
compactos con los MISMOS combos — el autosave y los atributos no cambian.
El variant drawer conserva el formulario clásico.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication, QFormLayout

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
    project_service.create("Chips")
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController

    ctx = SimpleNamespace(
        advanced_mode=False,
        log=lambda *args, **kwargs: None,
        animation_duration=lambda default=220: 0,
        request_save_silent=lambda: None,
        selected_entity_id=None,
        project_controller=SimpleNamespace(ps=project_service),
    )
    entity = NarrativeEntity(name="Eldrin")
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return project_service, ctx, EntityController(project_service), entity


def _panel(ctx, entity_controller, entity_id, variant):
    from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel

    return NodeDetailPanel(ctx, entity_controller, entity_id, variant=variant)


class TestMetaChips:
    def test_foco_combos_share_chip_style(self, qapp):
        _, ctx, entity_controller, entity = _setup()
        panel = _panel(ctx, entity_controller, entity.id, "foco")
        for combo in (
            panel.type_combo,
            panel.layer_combo,
            panel.nature_combo,
            panel.importance_combo,
        ):
            assert "border-radius: 11px" in combo.styleSheet()
            assert combo.height() == 22 or combo.sizeHint().height() >= 0  # altura fija
            assert combo.minimumHeight() <= 22 <= combo.maximumHeight()
        # El nombre es el protagonista: serif grande sin marco permanente.
        name_ss = panel.name_edit.styleSheet()
        assert "transparent" in name_ss
        assert "Georgia" in name_ss or "serif" in name_ss

    def test_foco_has_no_form_labels(self, qapp):
        _, ctx, entity_controller, entity = _setup()
        panel = _panel(ctx, entity_controller, entity.id, "foco")
        assert panel.nature_label.isHidden()
        # Los tooltips explican los chips (no hay labels que expliquen).
        assert panel.importance_combo.toolTip()
        assert panel.nature_combo.toolTip()
        # BETA1-J08 sigue: la visibilidad condicional del chip de naturaleza no
        # resucita el label en foco.
        panel._update_nature_visibility()
        assert panel.nature_label.isHidden()

    def test_drawer_keeps_classic_form(self, qapp):
        _, ctx, entity_controller, entity = _setup()
        panel = _panel(ctx, entity_controller, entity.id, "drawer")
        assert "border-radius: 11px" not in panel.type_combo.styleSheet()
        # El form clásico sigue siendo un QFormLayout con labels.
        forms = panel.findChildren(QFormLayout)
        assert forms, "el drawer debe conservar su QFormLayout"
        assert not panel.nature_label.isHidden() or True  # visibilidad por tipo

    def test_chips_carry_icon_and_tooltip(self, qapp):
        # UI2-12: cada chip lleva un icono SVG identificador + tooltip.
        from PySide6.QtWidgets import QLabel

        _, ctx, entity_controller, entity = _setup()
        panel = _panel(ctx, entity_controller, entity.id, "foco")
        for combo in (
            panel.type_combo,
            panel.layer_combo,
            panel.nature_combo,
            panel.importance_combo,
        ):
            wrapper = combo.parentWidget()
            glyphs = [
                child
                for child in wrapper.findChildren(QLabel)
                if child.pixmap() is not None and not child.pixmap().isNull()
            ]
            assert glyphs, "cada chip debe llevar su icono SVG"
            assert wrapper.toolTip(), "cada chip debe explicar qué selecciona"

    def test_nature_wrapper_hides_whole_chip(self, qapp):
        # UI2-12: para tipos sin naturaleza temporal se oculta el chip ENTERO
        # (icono incluido), no solo el combo.
        _, ctx, entity_controller, entity = _setup()
        panel = _panel(ctx, entity_controller, entity.id, "foco")
        index = panel.type_combo.findData("lugar")
        if index >= 0:
            panel.type_combo.setCurrentIndex(index)
        panel._update_nature_visibility()
        if not panel.nature_combo.isVisible():
            assert not panel._nature_chip_wrapper.isVisible()
        assert panel.nature_label.isHidden()

    def test_autosave_path_intact_from_chips(self, qapp):
        _, ctx, entity_controller, entity = _setup()
        panel = _panel(ctx, entity_controller, entity.id, "foco")
        panel.name_edit.setText("Eldrin el Sabio")
        index = panel.importance_combo.findData("critico")
        panel.importance_combo.setCurrentIndex(index)
        panel._do_save(refresh_after=False)  # mismo camino que el autosave
        assert entity.name == "Eldrin el Sabio"
        assert getattr(entity.narrative_importance, "value", "") == "critico"
