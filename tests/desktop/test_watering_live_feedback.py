"""UI2-05: feedback visual del riego EN CURSO (Mapa + Foco).

El worker de lote anuncia cada entidad ANTES de regarla (`entityStarted`);
el Mapa enciende un anillo savia pulsante en ese nodo y el Foco vira el marco
de la tarjeta a «regando» mientras dura. Con el gate de animación cerrado no
hay timer (anillo estático) — offscreen sin flakiness.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication, QGraphicsScene

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


# ── Worker: entityStarted antes de cada paso ────────────────────────────────


class _FakeWateringService:
    def __init__(self):
        self.watered: list[str] = []
        self.batches: list[list[str]] = []

    def water_batch_step(self, entity_id: str, *, batch_ids=None):
        # BETA-MULTIAGENT2-FIX-05 (punto 10): el doble estaba desincronizado de la
        # firma real (BETA-MULTIAGENT-FIX-01 añadió `batch_ids=`). El `TypeError`
        # lo tragaba el `except` del worker, el paso se reportaba «fallido» en
        # silencio y este test afirmaba sobre una lista vacía sin enterarse.
        self.watered.append(entity_id)
        self.batches.append(list(batch_ids or []))
        return SimpleNamespace(value=object())  # no-Error


class TestWorkerAnnouncesStart:
    def test_entity_started_precedes_done_for_each_step(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.watering_batch import WateringBatchWorker

        service = _FakeWateringService()
        worker = WateringBatchWorker(service, ["a", "b"])
        events: list[tuple[str, str]] = []
        worker.entityStarted.connect(lambda eid: events.append(("started", eid)))
        worker.entityDone.connect(lambda eid, ok, err: events.append(("done", eid)))
        worker.run()  # síncrono en el test (sin hilo)
        assert events == [("started", "a"), ("done", "a"), ("started", "b"), ("done", "b")]
        assert service.watered == ["a", "b"]
        assert service.batches == [["a", "b"], ["a", "b"]]  # el lote viaja a cada paso

    def test_firma_incompatible_se_reporta_como_error_de_programacion(self, qapp):
        """FIX-05: el `except` genérico ya no disfraza un bug de firma de riego fallido."""
        from hosts.DesktopHostPySide.widgets.foco.watering_batch import WateringBatchWorker

        class _StaleDouble:
            def water_batch_step(self, entity_id):  # sin batch_ids: firma vieja
                raise AssertionError("no debería llegar a ejecutarse")

        worker = WateringBatchWorker(_StaleDouble(), ["a"])
        errores: list[str] = []
        worker.entityDone.connect(lambda _eid, ok, err: errores.append(err) if not ok else None)
        worker.run()
        assert errores and "error de programación" in errores[0]


# ── Mapa: anillo savia por nodo ─────────────────────────────────────────────


def _node_item(entity_id: str = "e1"):
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphNodeItem

    node = SimpleNamespace(
        name="Aria",
        kind="personaje",
        color="",
        proposed=False,
        canon="canon",
        visibility="publico",
        image_path="",
        image_crop=None,
        is_event=False,
        entity_id=entity_id,
    )
    return GraphNodeItem(node, x=0.0, y=0.0, radius=40.0)


class TestMapPulse:
    def test_set_watering_active_toggles_item_pulse(self, qapp):
        from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView

        view = GraphCanvasView()
        item = _node_item("e1")
        view.scene_obj.addItem(item)
        view._nodes["e1"] = item
        view.set_motion_gate(lambda: False)  # animación cerrada → sin timer
        view.set_watering_active("e1")
        assert item._watering_pulse is True
        assert not view._watering_pulse_timer.isActive()
        view.set_watering_active("")
        assert item._watering_pulse is False
        view.deleteLater()

    def test_pulse_moves_between_entities_and_timer_gates_open(self, qapp):
        from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView

        view = GraphCanvasView()
        first, second = _node_item("e1"), _node_item("e2")
        view.scene_obj.addItem(first)
        view.scene_obj.addItem(second)
        view._nodes.update({"e1": first, "e2": second})
        view.set_motion_gate(lambda: True)  # animación abierta → timer vivo
        view.set_watering_active("e1")
        assert view._watering_pulse_timer.isActive()
        view.set_watering_active("e2")
        assert first._watering_pulse is False
        assert second._watering_pulse is True
        view.set_watering_active("")
        view._watering_pulse_tick()  # sin objetivo → el timer se apaga solo
        assert not view._watering_pulse_timer.isActive()
        view.deleteLater()

    def test_pulse_grows_bounding_rect_only_while_active(self, qapp):
        item = _node_item()
        scene = QGraphicsScene()
        scene.addItem(item)
        base = item.boundingRect()
        item.set_watering_pulse(True)
        assert item.boundingRect().width() > base.width()
        item.set_watering_pulse(False)
        assert item.boundingRect() == base


class TestMapPulseBranchSafe:
    """BETA2-FOCO-39: regar una RAMA (nodo sin ``set_watering_pulse``, como el
    ``GraphTreeItem`` contenedor) no revienta el Mapa ni arranca el timer de pulso.
    Antes lanzaba ``AttributeError`` y colgaba el slot del lote (sin avisos, badge
    congelado)."""

    def _branch(self):
        # Espeja la API del contenedor: SOLO tinte, sin pulso.
        return SimpleNamespace(set_watering_tint=lambda kind: None)

    def test_branch_node_without_pulse_does_not_raise(self, qapp):
        from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView

        view = GraphCanvasView()
        view._nodes["rama1"] = self._branch()
        view.set_motion_gate(lambda: True)  # animación abierta
        view.set_watering_active("rama1")  # antes: AttributeError
        assert view._watering_active_id == "rama1"
        assert not view._watering_pulse_timer.isActive()  # sin pulso → sin timer
        view.set_watering_active("")  # apagar la rama previa tampoco revienta
        view.deleteLater()

    def test_leaf_then_branch_transition_is_safe(self, qapp):
        from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView

        view = GraphCanvasView()
        leaf = _node_item("hoja1")
        view.scene_obj.addItem(leaf)
        view._nodes.update({"hoja1": leaf, "rama1": self._branch()})
        view.set_motion_gate(lambda: True)
        view.set_watering_active("hoja1")
        assert leaf._watering_pulse is True
        assert view._watering_pulse_timer.isActive()
        view.set_watering_active("rama1")  # la hoja previa se apaga; la rama no pulsa
        assert leaf._watering_pulse is False
        assert not view._watering_pulse_timer.isActive()
        view.deleteLater()


# ── Foco: marco «regando» transitorio ───────────────────────────────────────


def _foco_view():
    from hosts.DesktopHostPySide.widgets.foco.foco_view import FocoView

    return FocoView(project_provider=lambda: None)


class TestFocoWateringTone:
    def test_center_card_signals_active_watering(self, qapp):
        view = _foco_view()
        view._center_id = "e1"
        view.set_watering_active("e1")
        assert view._center_card.property("wateringState") == "regando"
        view.set_watering_active("")
        assert view._center_card.property("wateringState") != "regando"
        view.deleteLater()

    def test_other_entity_watering_does_not_touch_center(self, qapp):
        view = _foco_view()
        view._center_id = "e1"
        view.set_watering_active("otra")
        assert view._center_card.property("wateringState") != "regando"
        view.deleteLater()


class TestFocoCanvasPulse:
    """UI2-21: el lienzo del Foco hace latir en SAGE a CUALQUIER entidad regada
    (satélite hoja no centrado o marco de rama), no solo a la tarjeta central."""

    def _canvas_with_items(self):
        from hosts.DesktopHostPySide.widgets.foco.foco_canvas import (
            FocoCanvas,
            FocoContainerFrame,
            FocoSatelliteItem,
        )

        canvas = FocoCanvas()
        leaf = FocoSatelliteItem("leaf1", "Hoja vecina", "personaje")
        rama = FocoContainerFrame("rama1", "Rama madre")
        canvas._scene.addItem(leaf)
        canvas._scene.addItem(rama)
        canvas._items["leaf1"] = leaf
        canvas._container_frames.append(rama)
        return canvas, leaf, rama

    def test_pulse_on_non_centered_leaf(self, qapp):
        canvas, leaf, _rama = self._canvas_with_items()
        canvas.set_watering_active("leaf1")
        assert leaf._watering_pulse is True
        assert canvas._watering_timer.isActive()
        canvas.set_watering_active("")
        assert leaf._watering_pulse is False
        canvas._watering_tick()  # sin objetivo → el timer se apaga solo
        assert not canvas._watering_timer.isActive()
        canvas.deleteLater()

    def test_pulse_on_branch_frame_and_moves_between(self, qapp):
        canvas, leaf, rama = self._canvas_with_items()
        canvas.set_watering_active("rama1")
        assert rama._watering_pulse is True
        canvas.set_watering_active("leaf1")
        assert rama._watering_pulse is False  # se apaga la anterior
        assert leaf._watering_pulse is True
        canvas.deleteLater()


class TestFocoViewForwardsPulseToCanvas:
    def test_set_watering_active_forwards_to_canvas(self, qapp):
        view = _foco_view()
        view._center_id = "e1"
        view.set_watering_active("e2")
        # UI2-21: el lienzo recibe el id regado (aunque no sea la centrada).
        assert view.canvas._watering_active_id == "e2"
        view.set_watering_active("")
        assert view.canvas._watering_active_id == ""
        view.deleteLater()


class TestNotebookRunningState:
    def test_running_state_notebook_note_and_strip_water(self, qapp):
        from types import SimpleNamespace

        from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import (
            CultivationNotebook,
        )
        from hosts.DesktopHostPySide.widgets.foco.cultivation_strip import CultivationStrip

        # El Cuaderno sigue avisando «Regando…» en su chip de estado.
        notebook = CultivationNotebook()
        notebook.set_watering_running(True)
        assert "Regando" in notebook.status_chip.text()
        notebook.deleteLater()

        # BETA2-FOCO-37: el botón Regar vive ahora en la franja; ahí se deshabilita
        # mientras se riega la central.
        strip = CultivationStrip()
        strip.set_report(SimpleNamespace(status="falta_regar", latest=None, stale=False))
        assert strip._action_buttons["water"].isEnabled()
        strip.set_watering_running(True)
        assert not strip._action_buttons["water"].isEnabled()
        strip.set_watering_running(False)
        assert strip._action_buttons["water"].isEnabled()
        strip.deleteLater()
