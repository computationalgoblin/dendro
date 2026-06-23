"""CRON — runner del recorrido + center_on_milestone en el canvas (offscreen)."""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _project_with_milestone():
    from packages.application.causal_milestone_service import CausalMilestoneService
    from packages.application.entity_service import EntityService
    from packages.application.project_service import ProjectService
    from packages.domain.result import Ok

    ps = ProjectService()
    assert isinstance(ps.create("CRON runner"), Ok)
    svc = EntityService(ps, ps.store)
    a = svc.create_entity({"name": "Devian", "entity_type": "personaje", "birth_year": -100}).value
    hito = (
        CausalMilestoneService(project_service=ps)
        .create_hito_manual({"title": "La Purga", "year": -30, "affected_entity_ids": [a.id]})
        .value
    )
    return ps.active_project, hito


def test_center_on_milestone_centers_and_highlights():
    _app()
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    project, hito = _project_with_milestone()
    view = ChronoCanvasView()
    view.set_project(project)

    assert view.center_on_milestone(hito.id) is True
    assert view._walk_highlight_id == hito.id

    view.clear_walk_highlight()
    assert view._walk_highlight_id is None


def test_center_on_unknown_milestone_returns_false():
    _app()
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    project, _ = _project_with_milestone()
    view = ChronoCanvasView()
    view.set_project(project)

    assert view.center_on_milestone("inexistente") is False


def test_runner_shows_step_and_blocks_advance_on_stop():
    _app()
    from hosts.DesktopHostPySide.widgets.chronology_walk_runner_panel import (
        ChronologyWalkRunnerPanel,
    )

    panel = ChronologyWalkRunnerPanel()
    result = {
        "report": "Lectura editorial del hito.",
        "candidates": [{"id": "c1"}, {"id": "c2"}],
        "model_payload": {
            "report": "Lectura editorial del hito.",
            "issues": [
                {
                    "title": "Servidumbre no motivada",
                    "severity": "alta",
                    "kind": "motivation_incompatibility",
                }
            ],
        },
        "walk": {"stopped": True, "stop_reason": "Motivación incompatible"},
    }
    panel.show_step(result)

    assert "Lectura editorial" in panel._reading.toPlainText()
    assert panel._issues.count() == 1
    assert panel._advance_btn.isEnabled() is False  # parada dura bloquea avanzar


def test_runner_editable_changes_emit_apply_items():
    _app()
    from hosts.DesktopHostPySide.widgets.chronology_walk_runner_panel import (
        ChronologyWalkRunnerPanel,
    )

    panel = ChronologyWalkRunnerPanel()
    panel.set_changes(
        [
            {
                "candidate_id": "c1",
                "kind": "entity",
                "apply": "flat",
                "header": "Nueva entidad: Akshan",
                "fields": [
                    {"key": "name", "label": "Nombre", "value": "Akshan"},
                    {
                        "key": "brief_description",
                        "label": "Descripción",
                        "value": "x",
                        "multiline": True,
                    },
                ],
            },
            {
                "candidate_id": "c2",
                "kind": "report",
                "header": "Lectura",
                "before": "informe",
                "fields": [],
            },
        ]
    )
    assert "2" in panel._candidates_label.text()
    assert panel._apply_btn.isEnabled() is True

    # El usuario edita el nombre de la entidad antes de aplicar.
    panel._cards[0]._fields["name"].setText("Akshan el Justo")

    captured = []
    panel.applyRequested.connect(lambda items: captured.extend(items))
    panel._apply_btn.click()

    # El informe (report) no es aplicable; solo la entidad editada.
    assert len(captured) == 1
    assert captured[0]["candidate_id"] == "c1"
    assert captured[0]["edited_data"]["name"] == "Akshan el Justo"


def test_runner_emits_signals():
    _app()
    from hosts.DesktopHostPySide.widgets.chronology_walk_runner_panel import (
        ChronologyWalkRunnerPanel,
    )

    panel = ChronologyWalkRunnerPanel()
    seen = SimpleNamespace(advance=0, stop=0, decision=[])
    panel.advanceRequested.connect(lambda: setattr(seen, "advance", seen.advance + 1))
    panel.stopRequested.connect(lambda: setattr(seen, "stop", seen.stop + 1))
    panel.decisionRequested.connect(lambda d: seen.decision.append(d))

    panel._advance_btn.click()
    panel._stop_btn.click()
    panel._decide_btn.click()

    assert seen.advance == 1
    assert seen.stop == 1
    assert seen.decision == ["revisado"]


def test_walk_pulse_starts_and_stops():
    _app()
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    project, hito = _project_with_milestone()
    view = ChronoCanvasView()
    view.set_project(project)

    assert view.start_walk_pulse(hito.id) is True
    assert view._walk_pulse_id == hito.id
    assert view._walk_pulse_timer.isActive() is True
    view._walk_pulse_tick()  # un tick no lanza y mantiene el pulso vivo

    view.stop_walk_pulse()
    assert view._walk_pulse_id is None
    assert view._walk_pulse_timer.isActive() is False


def test_walk_pulse_on_unknown_milestone_returns_false():
    _app()
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    project, _ = _project_with_milestone()
    view = ChronoCanvasView()
    view.set_project(project)

    assert view.start_walk_pulse("inexistente") is False
    assert view._walk_pulse_timer.isActive() is False


def test_chrono_exposes_walk_requested_signal_and_milestone_lookup():
    _app()
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

    assert hasattr(ChronoCanvasView, "walkRequested")
    project, hito = _project_with_milestone()
    view = ChronoCanvasView()
    view.set_project(project)
    view.resize(800, 600)

    # Sobre un punto vacío no hay hito.
    from PySide6.QtCore import QPoint

    assert view._milestone_id_at(QPoint(-9999, -9999)) == ""

    # Sobre la posición del item del hito, lo identifica.
    items = view._milestone_items.get(hito.id) or []
    assert items, "el hito debe tener items en la escena"
    scene_pt = items[0].sceneBoundingRect().center()
    view_pt = view.mapFromScene(scene_pt)
    found = view._milestone_id_at(view_pt)
    assert found == hito.id


def test_qt_alive_detects_deleted_widget():
    _app()
    import shiboken6
    from PySide6.QtWidgets import QWidget

    from hosts.DesktopHostPySide.views.workspaces import _qt_alive

    assert _qt_alive(None) is False
    w = QWidget()
    assert _qt_alive(w) is True
    shiboken6.delete(w)
    # Tras borrarlo, la referencia Python envuelve un objeto C++ muerto.
    assert _qt_alive(w) is False


def test_runner_no_actionable_changes_disables_apply_with_clear_status():
    _app()
    from hosts.DesktopHostPySide.widgets.chronology_walk_runner_panel import (
        ChronologyWalkRunnerPanel,
    )

    panel = ChronologyWalkRunnerPanel()
    # Solo un informe de lectura (no accionable).
    panel.set_changes([{"candidate_id": "c1", "kind": "report", "header": "Lectura", "fields": []}])
    assert panel._apply_btn.isEnabled() is False
    assert "Sin cambios que aplicar" in panel._status.text()
