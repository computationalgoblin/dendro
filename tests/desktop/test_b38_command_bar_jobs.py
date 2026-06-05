from __future__ import annotations

from types import SimpleNamespace

import pytest

from packages.application.ai_jobs import (
    AIJobService,
    AIJobStatus,
    AIJobType,
    build_ai_job_result,
    classify_ai_job_intent,
)
from packages.domain.result import Error, Ok

try:
    from PySide6.QtWidgets import QApplication, QPushButton
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_b38_ai_job_service_creates_reviewable_queued_job():
    service = AIJobService()
    result = service.create_job(
        AIJobType.GENERATE_ENTITIES,
        "Créame tres personajes para empezar esta historia",
        context_scope={"selected_entity_ids": ["e1"], "worldbuilding_active": True},
    )
    assert isinstance(result, Ok)
    job = result.value
    assert job.status is AIJobStatus.QUEUED
    assert job.type is AIJobType.GENERATE_ENTITIES
    assert job.context_scope["selected_entity_ids"] == ["e1"]
    assert job.result == {}
    assert service.list_jobs() == [job]


def test_b38_ai_job_service_rejects_empty_prompt():
    result = AIJobService().create_job(AIJobType.REVIEW_GRAPH, "   ")
    assert isinstance(result, Error)


def test_b38_ai_job_service_updates_and_cancels_without_persistence():
    service = AIJobService()
    job = service.create_job("review_graph", "Revisa todo el grafo").value
    updated = service.update_status(job.id, AIJobStatus.BUILDING_CONTEXT, message="Construyendo contexto", progress=0.25)
    assert isinstance(updated, Ok)
    assert updated.value.message == "Construyendo contexto"
    assert updated.value.progress == 0.25
    cancelled = service.cancel_job(job.id)
    assert isinstance(cancelled, Ok)
    assert cancelled.value.status is AIJobStatus.CANCELLED


@pytest.mark.parametrize(
    "prompt,worldbuilding,expected",
    [
        ("Créame tres personajes", False, AIJobType.GENERATE_ENTITIES),
        ("Crea un sistema metafísico", False, AIJobType.GENERATE_TREE),
        ("Crea un sistema metafísico", True, AIJobType.EXPAND_WORLDBUILDING),
        ("Propón relaciones para Devian", False, AIJobType.SUGGEST_RELATIONS),
        ("Busca incoherencias", False, AIJobType.ANALYZE_COHERENCE),
        ("Revisa todo el grafo y proponme mejoras", False, AIJobType.REVIEW_GRAPH),
    ],
)
def test_b38_heuristic_intent_classifier(prompt, worldbuilding, expected):
    assert classify_ai_job_intent(prompt, worldbuilding_active=worldbuilding) is expected


def _make_workspace_stub(*, worldbuilding_active=True):
    from PySide6.QtWidgets import QWidget
    from hosts.DesktopHostPySide.widgets.graph_canvas import VisualFilterState

    class CanvasStub:
        def __init__(self):
            self.filter_state = VisualFilterState()
            self.cleared = False
        def apply_visual_filter(self, filter_state):
            self.filter_state = filter_state
        def clear_visual_filters(self):
            self.cleared = True
            self.filter_state = VisualFilterState()

    class WorkspaceStub(QWidget):
        def __init__(self, project, canvas):
            super().__init__()
            self._project = project
            self.graph = SimpleNamespace(canvas=canvas)
        def _get_active_project(self):
            return self._project
        def _activate_layers_view(self):
            pass
        def _deactivate_layers_view(self):
            pass
        def _apply_layer_filter(self, layer_id):
            canvas.apply_visual_filter(VisualFilterState(layer_ids=(layer_id,)))
        def _clear_layer_filter(self):
            canvas.clear_visual_filters()

    project = SimpleNamespace(
        worldbuilding_active=worldbuilding_active,
        world_layers=[
            SimpleNamespace(id="layer_metaphysics", name="Metafísica", order=1),
            SimpleNamespace(id="layer_cultures", name="Culturas", order=7),
        ],
        entities={
            "e1": SimpleNamespace(layer_ids=["layer_metaphysics"]),
            "e2": SimpleNamespace(layer_ids=["layer_cultures"]),
        },
        relations={"r1": SimpleNamespace(layer_ids=["layer_cultures"])},
    )
    canvas = CanvasStub()
    return WorkspaceStub(project, canvas), canvas


def test_b38_layer_drawer_is_persistent_and_lists_counts(qapp):
    from hosts.DesktopHostPySide.views.workspaces import _LayerEdgeFlyout

    workspace, _ = _make_workspace_stub(worldbuilding_active=True)
    panel = _LayerEdgeFlyout(workspace)
    panel.show_flyout()

    assert panel.isHidden() is False
    texts = [btn.text() for btn in panel.findChildren(QPushButton)]
    assert any("Metafísica" in text and "1" in text for text in texts)
    assert any("Culturas" in text and "2" in text for text in texts)

    panel.hide_flyout()
    assert panel.isVisible() is False


def test_b38_layer_drawer_chip_applies_visual_filter(qapp):
    from hosts.DesktopHostPySide.views.workspaces import _LayerEdgeFlyout

    workspace, canvas = _make_workspace_stub(worldbuilding_active=True)
    panel = _LayerEdgeFlyout(workspace)
    panel.show_flyout()
    panel._on_chip_clicked("layer_cultures")

    assert canvas.filter_state.layer_ids == ("layer_cultures",)
    panel._on_chip_clicked("layer_cultures")
    assert canvas.cleared is True


class _CandidateControllerStub:
    def __init__(self):
        self.created = []
    def create(self, data):
        self.created.append(dict(data))
        return Ok(SimpleNamespace(id=f"cand-{len(self.created)}", **data))


def test_b38_job_result_panel_sends_candidates_to_inbox(qapp):
    from hosts.DesktopHostPySide.views.workspaces import AIJobResultPanel

    service = AIJobService()
    job = service.create_job(AIJobType.GENERATE_ENTITIES, "Créame tres personajes").value
    job.result = build_ai_job_result(job)
    controller = _CandidateControllerStub()
    changed = {"count": 0}
    panel = AIJobResultPanel(job, controller, on_candidates_created=lambda: changed.__setitem__("count", changed["count"] + 1))

    panel._send_candidates()

    assert len(controller.created) == 3
    assert changed["count"] == 1
    assert all(c["state"] == "pendiente" for c in controller.created)
    assert all(c["metadata"]["canon_auto_mutation"] is False for c in controller.created)


def test_b38_ai_job_worker_executes_without_touching_ui_thread(qapp):
    from hosts.DesktopHostPySide.views.workspaces import _AIJobWorker

    service = AIJobService()
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa todo el grafo").value
    worker = _AIJobWorker(service, job.id)
    finished = []
    failed = []
    worker.finishedOk.connect(lambda jid: finished.append(jid))
    worker.failed.connect(lambda jid, err: failed.append((jid, err)))

    worker.run()

    assert failed == []
    assert finished == [job.id]
    ready = service.get_job(job.id).value
    assert ready.status is AIJobStatus.READY_FOR_REVIEW
    assert ready.result["kind"] == "analysis_report"
