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


class TestGardenLens:
    def test_lens_paints_states_from_real_service(self, qapp):
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
        view.set_garden_lens(True, provider)

        # Nutrida 70 → sólida (0.5 + 0.35 = 0.85); obsoleta atenuada ×0.75.
        assert abs(view._nodes[watered.id].opacity() - 0.85) < 0.01
        assert abs(view._nodes[stale.id].opacity() - 0.85 * 0.75) < 0.01
        assert abs(view._nodes[dried.id].opacity() - 0.35) < 0.01  # apagada estable
        assert abs(view._nodes[never.id].opacity() - 0.8) < 0.01
        # Overlays para el primer plano: halo por Iluminada y semilla sin cultivar.
        assert view._garden_overlays[watered.id]["iluminada"] == 80
        assert view._garden_overlays[never.id]["never"] is True
        assert view._garden_overlays[dried.id]["status"] == "secada"

    def test_lens_off_leaves_a_clean_map(self, qapp):
        project_service, watering = _watering()
        watered = _entity(project_service, "Regada")
        ghost_id = "ghost-1"
        watering.water_entity(watered.id)
        view = _view_with_items([(watered.id, "borrador"), (ghost_id, "fantasma")])
        provider = lambda ids: getattr(watering.statuses_for(list(ids)), "value", {})  # noqa: E731

        view.set_garden_lens(True, provider)
        view.set_garden_lens(False)
        assert view._garden_overlays == {}
        assert view._nodes[watered.id].opacity() == 1.0
        # La translucidez del fantasma NO es de la lente: se conserva.
        assert abs(view._nodes[ghost_id].opacity() - 0.45) < 0.01

    def test_lens_never_breaks_on_provider_failure(self, qapp):
        view = _view_with_items([("e1", "borrador")])

        def _boom(_ids):
            raise RuntimeError("provider roto")

        view.set_garden_lens(True, _boom)  # fail-soft: sin overlays, sin excepción
        assert view._garden_overlays == {}


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
        assert '"fantasma": "#B9B29A"' in graph_source
        assert graph_source.count('if node.canon.lower() == "fantasma":') >= 2  # hoja y rama

    def test_map_is_read_only_with_summary_and_batch(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "def _open_map_summary" in source
        assert 'if getattr(self, "_active_view", "") == "concentric" and not is_new:' in source
        assert '"Regar esta entidad"' in source
        assert '"Regar su anillo"' in source
        assert '"Regar todo el grafo"' in source
        assert '"Abrir en Foco (editar)"' in source

    def test_lens_toggle_lives_in_the_map_cluster(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert '"garden_lens", "Lente Jardín' in source
        assert "def _toggle_garden_lens" in source
        assert "self.graph.set_garden_lens(self._garden_lens_on, self._garden_status_map)" in source
