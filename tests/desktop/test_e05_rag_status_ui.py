from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

from packages.application.ai_jobs import AIJobService, AIJobStatus, AIJobType
from packages.domain.project import Project

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ctx(project=None):
    return SimpleNamespace(
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
        animation_duration=lambda base: 0,
        log=lambda *_args, **_kwargs: None,
    )


def test_e05_home_does_not_show_rag_status(qapp):
    from hosts.DesktopHostPySide.views.home_view import HomeView

    view = HomeView(_ctx(Project(id="proj-e05-ui", name="Proyecto UI")))
    view.refresh()

    assert not hasattr(view, "_rag_status_label")
    assert all(not label.text().startswith("RAG:") for label in view.findChildren(QLabel))


def test_e05_ai_jobs_panel_shows_rag_status_on_active_job(qapp):
    from hosts.DesktopHostPySide.views.workspaces import AIJobsPanel

    service = AIJobService()
    active = service.create_job(AIJobType.REVIEW_GRAPH, "Revisa el grafo").value
    service.update_status(active.id, AIJobStatus.BUILDING_CONTEXT, message="Construyendo contexto", progress=0.2)

    workspace = SimpleNamespace(
        ai_job_service=service,
        _open_ai_job_result_by_id=lambda _jid: None,
        _sync_jobs_indicator=lambda: None,
        ctx=SimpleNamespace(log=lambda *_args, **_kwargs: None),
    )
    panel = AIJobsPanel(workspace)

    texts = [label.text() for label in panel.findChildren(QLabel)]
    assert "RAG: preparando contexto" in texts


def test_e05_ai_jobs_panel_shows_context_pack_summary(qapp):
    from hosts.DesktopHostPySide.views.workspaces import AIJobsPanel

    service = AIJobService()
    job = service.create_job(AIJobType.ANALYZE_COHERENCE, "Analiza Devian").value
    job.plan.setdefault("context", {})["rag_context_pack"] = {
        "schema": "context_pack/v1",
        "items": [{"kind": "entity", "ref_id": "leaf-1", "reason": "selected_item"}],
        "tokens_estimated": 42,
        "warnings": [],
        "truncated": False,
    }
    service.update_status(job.id, AIJobStatus.WAITING_FOR_MODEL, message="Pensando", progress=0.6)

    workspace = SimpleNamespace(
        ai_job_service=service,
        _open_ai_job_result_by_id=lambda _jid: None,
        _sync_jobs_indicator=lambda: None,
        ctx=SimpleNamespace(log=lambda *_args, **_kwargs: None),
    )
    panel = AIJobsPanel(workspace)

    texts = [label.text() for label in panel.findChildren(QLabel)]
    assert "RAG: contexto listo (1 items, 42 tokens)" in texts
