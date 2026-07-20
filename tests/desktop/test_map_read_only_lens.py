"""Mapa solo lectura, doble click → Foco y Lente Jardín (BETA2-FOCO-14).

La lente se prueba con el WateringService REAL como provider sobre una
GraphCanvasView real (los nodos usan el patrón SimpleNamespace de b44 para el
snapshot). El cableado del workspace y los retoques visuales del item se
verifican con pins de fuente (patrón de la casa).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication, QGraphicsEllipseItem

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.ai_jobs import AIJobService  # noqa: E402 — guard HAS_QT
from packages.application.project_service import ProjectService  # noqa: E402 — guard HAS_QT
from packages.application.watering_service import WateringService  # noqa: E402 — guard HAS_QT
from packages.domain.entity import NarrativeEntity  # noqa: E402 — guard HAS_QT
from packages.infrastructure.ai_provider import AIProvider  # noqa: E402 — guard HAS_QT

_GRAPH = Path("hosts/DesktopHostPySide/widgets/graph_canvas.py")
_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")

_PAYLOAD = {
    "scores": {"arraigo": 30, "nutrida": 70, "iluminada": 80},
    "summary": "Lectura para la lente.",
    "metric_explanations": {},
    "risks": [],
}


class LensProvider(AIProvider):
    provider_name = "fake_lens"
    model = "fake-model-1"

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        return json.dumps(_PAYLOAD, ensure_ascii=False), None


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _watering():
    project_service = ProjectService()
    project_service.create("Lente")
    ai_service = AIJobService(
        provider=LensProvider(), project_provider=lambda: project_service.active_project
    )
    return project_service, WateringService(project_service, ai_job_service=ai_service)


def _entity(project_service, name, **kwargs):
    entity = NarrativeEntity(name=name, **kwargs)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _view_with_items(entity_ids_and_canons):
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasView

    view = GraphCanvasView()
    for entity_id, canon in entity_ids_and_canons:
        item = QGraphicsEllipseItem(-10, -10, 20, 20)  # item Qt real (setOpacity)
        item.node = SimpleNamespace(canon=canon, entity_id=entity_id)
        view._nodes[entity_id] = item
    return view


class TestGardenAlwaysOn:
    """BETA2-JARDIN-01: sin lente conmutable — el estado de riego es el
    aspecto normal del Mapa (estados discretos, sin gradientes de opacidad).
    El detalle visual (tintes/caída/freeze) vive en test_map_garden_status.py."""

    def test_states_always_visible_from_real_service(self, qapp):
        project_service, watering = _watering()
        watered = _entity(project_service, "Regada")
        never = _entity(project_service, "Nunca")
        dried = _entity(project_service, "Secada")
        stale = _entity(project_service, "Obsoleta")
        assert watering.water_entity(watered.id).value is not None
        assert watering.water_entity(stale.id).value is not None
        stale.updated_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        watering.pause(dried.id)
        project_service.active_project.touch()

        view = _view_with_items(
            [(entity.id, "borrador") for entity in (watered, never, dried, stale)]
        )
        provider = lambda ids: getattr(watering.statuses_for(list(ids)), "value", {})  # noqa: E731
        view.set_garden_status_provider(provider)

        # Estados discretos: todas plenas (el tinte comunica, no la opacidad).
        for entity in (watered, never, dried, stale):
            assert view._nodes[entity.id].opacity() == 1.0
        # Halo solo en la regada vigente; la obsoleta vuelve a falta_regar.
        assert view._garden_overlays == {watered.id: {"iluminada": 80, "arraigo": 30}}
        assert view._garden_frozen == {never.id, dried.id, stale.id}
        assert view._garden_droopy == set()  # nutrida 70 >= 60

    def test_ghost_keeps_translucency_out_of_the_cycle(self, qapp):
        project_service, watering = _watering()
        watered = _entity(project_service, "Regada")
        ghost_id = "ghost-1"
        watering.water_entity(watered.id)
        view = _view_with_items([(watered.id, "borrador"), (ghost_id, "fantasma")])
        provider = lambda ids: getattr(watering.statuses_for(list(ids)), "value", {})  # noqa: E731

        view.set_garden_status_provider(provider)
        assert view._nodes[watered.id].opacity() == 1.0
        # La translucidez del fantasma es de su naturaleza, no del jardín;
        # jamás se congela ni se tiñe.
        assert abs(view._nodes[ghost_id].opacity() - 0.45) < 0.01
        assert ghost_id not in view._garden_frozen

    def test_garden_never_breaks_on_provider_failure(self, qapp):
        view = _view_with_items([("e1", "borrador")])

        def _boom(_ids):
            raise RuntimeError("provider roto")

        view.set_garden_status_provider(_boom)  # fail-soft: sin overlays, sin excepción
        assert view._garden_overlays == {}
        assert view._garden_frozen == set()


class TestSourcePins:
    def test_double_click_requests_foco(self):
        graph_source = _GRAPH.read_text(encoding="utf-8")
        assert "entityFocusRequested = Signal(str)" in graph_source
        assert "self.entityFocusRequested.emit(node_id)" in graph_source
        assert "self.canvas.entityFocusRequested.connect(self.entityFocusRequested)" in graph_source
        workspace_source = _WORKSPACES.read_text(encoding="utf-8")
        assert (
            "self.graph.entityFocusRequested.connect(self._on_map_entity_to_foco)"
            in workspace_source
        )

    def test_ghosts_are_translucent_in_map(self):
        graph_source = _GRAPH.read_text(encoding="utf-8")
        assert graph_source.count('if node.canon.lower() == "fantasma":') >= 2  # hoja y rama

    def test_map_click_selects_only_no_obsolete_summary_drawer(self):
        # UI2-22: el drawer obsoleto «Entidad (Mapa)» se eliminó; el clic simple
        # en el Mapa solo selecciona (return temprano) y el doble clic abre el
        # Foco. El riego per-entidad ya no vive en un menú del Mapa.
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "def _open_map_summary" not in source
        assert 'drawer.set_content(card, title="Entidad (Mapa)")' not in source
        # El clic simple en el Mapa hace return sin abrir panel/drawer.
        assert 'if getattr(self, "_active_view", "") == "concentric" and not is_new:' in source
        # El doble clic → Foco se conserva.
        assert (
            "self.graph.entityFocusRequested.connect(self._on_map_entity_to_foco)" in source
        )

    def test_garden_is_always_on_without_toggle(self):
        # BETA2-JARDIN-01: la lente conmutable desapareció del cluster.
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert '"garden_lens"' not in source
        assert "_toggle_garden_lens" not in source
        assert "self.graph.set_garden_status_provider(self._garden_status_map)" in source
        graph_source = _GRAPH.read_text(encoding="utf-8")
        assert "def set_garden_lens" not in graph_source
        assert "def set_garden_status_provider" in graph_source


class TestTimeBarPillDeconflict:
    """BETA2-FOCO-18: la barra temporal queda DEBAJO de la píldora de modos."""

    def _widget(self, qapp):
        from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget

        project = SimpleNamespace(world_layers=[], entities=[], relations=[])
        ctx = SimpleNamespace(
            project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
            advanced_mode=False,
            creation_layout_mode="concentric_rings",
            creation_focused_ring_id="",
            selected_entity_id="",
            save_preferences=lambda: None,
            log=lambda *args, **kwargs: None,
        )
        widget = GraphCanvasWidget(ctx)
        widget.resize(1200, 800)
        return widget

    def test_top_inset_pushes_time_bar_below_pill(self, qapp):
        widget = self._widget(qapp)
        widget._position_time_bar()
        assert widget._time_bar.y() == 14  # sin inset: comportamiento original

        pill_height = 40
        widget.set_time_bar_top_inset(pill_height + 10)
        # y = 14 + inset > 14 + pill_height = borde inferior de la píldora.
        assert widget._time_bar.y() == 14 + pill_height + 10
        assert widget._time_bar.y() > 14 + pill_height

        widget.set_time_bar_top_inset(0)
        assert widget._time_bar.y() == 14
        widget.deleteLater()

    def test_workspace_no_longer_reserves_pill_height(self):
        # FOCO-28: la píldora de modos vive en el banner superior (no flota sobre
        # el Mapa), así que la barra temporal recupera el borde superior con un
        # inset mínimo en vez de reservar la altura de la píldora.
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "graph.set_time_bar_top_inset(10)" in source
        assert "graph.set_time_bar_top_inset(toggle.height() + 10)" not in source
