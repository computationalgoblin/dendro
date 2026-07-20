"""UI2-08 / BETA2-FOCO-37: franja de cultivo persistente en el pie de la tarjeta.

Visible en Ficha y Relaciones (estado + micro-métricas + controles de riego);
oculta en la pestaña Cultivo, donde el Cuaderno muestra el detalle. Los controles
de riego son iconos minimalistas (Regar/Secar/Cultivar) con un punto que palpita
cuando falta regar; el chip verboso «Regar ahora» se retiró.
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


def _report(status="regada", scores=None):
    latest = SimpleNamespace(
        scores=scores
        if scores is not None
        else {"arraigo": 62, "nutrida": 71, "iluminada": 55, "relevancia": 80},
        metric_explanations={"arraigo": "Pocas relaciones hacia anillos interiores."},
        risks=[],
        summary="",
    )
    return SimpleNamespace(status=status, latest=latest, stale=False, last_error="")


def _fake_watering_service(report):
    return SimpleNamespace(
        status_of=lambda entity_id: SimpleNamespace(value=report),
        history_for=lambda entity_id: SimpleNamespace(value=[]),
    )


def _setup(report):
    project_service = ProjectService()
    project_service.create("Franja")
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
    entity = NarrativeEntity(name="Eldrin")
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()

    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    view = FocoView(
        project_provider=lambda: project_service.active_project,
        ctx=ctx,
        entity_controller=EntityController(project_service),
        relation_controller=RelationController(project_service),
        watering_service=_fake_watering_service(report),
    )
    return view, entity


class TestCultivationStrip:
    def test_visible_on_card_and_in_editor_except_cultivo(self, qapp):
        # UI2-16: la franja vive en la tarjeta de LECTURA; al abrir el editor
        # se muda a su pie y solo se oculta en la pestaña Cultivo (el Cuaderno
        # ya muestra el detalle). Al cerrar vuelve a la tarjeta.
        view, entity = _setup(_report())
        view.center_entity(entity.id)
        strip = view.cultivation_strip
        assert not strip.isHidden()  # tarjeta de lectura
        assert view._strip_slot.indexOf(strip) >= 0
        view.open_editor()
        assert view._editor_overlay.footer_slot.indexOf(strip) >= 0
        assert not strip.isHidden()  # Ficha del editor
        view._tab_bar.set_current("relaciones")
        assert not strip.isHidden()
        view._tab_bar.set_current("cultivo")
        assert strip.isHidden()  # el Cuaderno ya lo muestra
        view._tab_bar.set_current("ficha")
        assert not strip.isHidden()
        view.close_editor()
        assert view._strip_slot.indexOf(strip) >= 0
        assert not strip.isHidden()
        view.deleteLater()

    def test_micro_bars_reflect_report(self, qapp):
        view, entity = _setup(_report())
        view.center_entity(entity.id)
        strip = view.cultivation_strip
        assert strip.bars["arraigo"].value() == 62
        assert strip.bars["relevancia"].value() == 80
        assert "62%" in strip.bars["arraigo"].toolTip()
        assert "Pocas relaciones" in strip.bars["arraigo"].toolTip()
        view.deleteLater()

    def test_action_icons_route_to_view(self, qapp):
        # BETA2-FOCO-37: los iconos de la franja actúan sobre la entidad en foco.
        view, entity = _setup(_report(status="falta_regar", scores={}))
        view.center_entity(entity.id)
        strip = view.cultivation_strip
        watered: list[list[str]] = []
        dried: list[str] = []
        view.waterRequested.connect(watered.append)
        view.dryRequested.connect(dried.append)
        strip.waterClicked.emit()
        strip.dryClicked.emit()
        assert watered == [[entity.id]]
        assert dried == [entity.id]
        view.deleteLater()

    def test_pulse_and_enable_reflect_state(self, qapp):
        view, entity = _setup(_report(status="falta_regar", scores={}))
        view.center_entity(entity.id)
        strip = view.cultivation_strip
        assert strip.status_dot._pulsing is True  # falta regar → palpita
        assert strip._action_buttons["water"].isEnabled()
        assert strip._action_buttons["dry"].isEnabled()
        assert not strip._action_buttons["cultivate"].isEnabled()  # solo secadas
        view.deleteLater()

    def test_without_service_strip_stays_hidden(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

        project_service = ProjectService()
        project_service.create("Sin servicio")
        entity = NarrativeEntity(name="Sola")
        project_service.active_project.entities.append(entity)
        view = FocoView(project_provider=lambda: project_service.active_project)
        view.center_entity(entity.id)
        assert view.cultivation_strip.isHidden()
        view.deleteLater()
