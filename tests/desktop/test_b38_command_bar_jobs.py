from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from packages.application.ai_jobs import (
    AIJobService,
    AIJobStatus,
    AIJobType,
)
from packages.domain.result import Error, Ok
from packages.infrastructure.ai_provider import AIProvider

try:
    from PySide6.QtWidgets import QApplication, QPushButton, QProgressBar
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


class DesktopCommandBarProvider(AIProvider):
    provider_name = "desktop_test_provider"

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        prompt = json.loads(user_message)["prompt_exacto_usuario"]
        lower = prompt.lower()
        if "revisa" in lower:
            return json.dumps({
                "summary": "Informe listo",
                "report": "Revisión basada en grafo visible.",
                "issues": [{"title": "Hueco", "description": "Falta una causa", "severity": "media"}],
            }, ensure_ascii=False), None
        return json.dumps({
            "summary": "Candidatos listos",
            "report": "Resultado revisable.",
            "entities": [
                {"name": "Hermano traidor tragicómico", "entity_type": "personaje", "brief_description": "Hermano y traidor en tono tragicómico."},
                {"name": "Hermana traidora tragicómica", "entity_type": "personaje", "brief_description": "Hermana y traidora en tono tragicómico."},
            ],
        }, ensure_ascii=False), None

    def invoke(self, operation):  # pragma: no cover
        raise AssertionError("Desktop command-bar worker must use chat()")


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
def test_b38_desktop_intent_classifier(prompt, worldbuilding, expected):
    from packages.application.ai_jobs import classify_ai_job_intent
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
            self.ai_job_service = AIJobService(provider=DesktopCommandBarProvider())
            self.opened_job_ids = []
            self.logged = []
            self.ctx = SimpleNamespace(log=lambda level, msg: self.logged.append((level, msg)), drawer=None)
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
        def _open_ai_job_result_by_id(self, job_id):
            self.opened_job_ids.append(job_id)
        def _sync_jobs_indicator(self):
            pass

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

    service = AIJobService(provider=DesktopCommandBarProvider())
    job = service.create_job(AIJobType.GENERATE_ENTITIES, "Créame tres personajes hermanos traidores tragicómicos").value
    executed = service.execute_job(job.id)
    assert isinstance(executed, Ok)
    controller = _CandidateControllerStub()
    changed = {"count": 0}
    panel = AIJobResultPanel(executed.value, controller, on_candidates_created=lambda: changed.__setitem__("count", changed["count"] + 1))

    panel._send_candidates()

    assert len(controller.created) == 2
    assert changed["count"] == 1
    assert all(c["state"] == "pendiente" for c in controller.created)
    assert all(c["metadata"]["canon_auto_mutation"] is False for c in controller.created)


def test_b38_ai_job_worker_executes_without_touching_ui_thread_and_emits_phases(qapp):
    from hosts.DesktopHostPySide.views.workspaces import _AIJobWorker

    service = AIJobService(provider=DesktopCommandBarProvider())
    job = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa todo el grafo").value
    worker = _AIJobWorker(service, job.id)
    phases = []
    finished = []
    failed = []
    worker.statusChanged.connect(lambda status, message, progress: phases.append((status, message, progress)))
    worker.finishedOk.connect(lambda jid: finished.append(jid))
    worker.failed.connect(lambda jid, err: failed.append((jid, err)))

    worker.run()

    assert failed == []
    assert finished == [job.id]
    statuses = [status for status, _message, _progress in phases]
    assert "building_context" in statuses
    assert "planning" in statuses
    assert "waiting_for_model" in statuses
    assert "postprocessing" in statuses
    assert statuses[-1] == "ready_for_review"
    ready = service.get_job(job.id).value
    assert ready.status is AIJobStatus.READY_FOR_REVIEW
    assert ready.result["kind"] == "analysis_report"


def test_b38_ai_jobs_panel_shows_active_and_ready_jobs_with_progress(qapp):
    from hosts.DesktopHostPySide.views.workspaces import AIJobsPanel

    workspace, _ = _make_workspace_stub(worldbuilding_active=True)
    active = workspace.ai_job_service.create_job(AIJobType.GENERATE_ENTITIES, "Créame tres personajes").value
    workspace.ai_job_service.update_status(active.id, AIJobStatus.BUILDING_CONTEXT, message="Construyendo contexto…", progress=0.2)
    ready = workspace.ai_job_service.create_job(AIJobType.REVIEW_GRAPH, "Revisa todo el grafo").value
    workspace.ai_job_service.execute_job(ready.id)

    panel = AIJobsPanel(workspace)
    progress_bars = panel.findChildren(QProgressBar)
    buttons = panel.findChildren(QPushButton)
    texts = [b.text() for b in buttons]

    assert len(progress_bars) >= 2
    assert any(bar.value() == 20 for bar in progress_bars)
    assert any(bar.value() == 100 for bar in progress_bars)
    assert "Ver resultado" in texts
    assert "Cancelar" in texts
