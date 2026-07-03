"""Drawer de riego, autorización IA visible y lote cancelable (BETA2-FOCO-12)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

try:
    from PySide6.QtWidgets import QApplication, QWidget

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

from packages.application.ai_jobs import AIJobService  # noqa: E402 — tras el guard HAS_QT
from packages.application.history_service import HistoryService  # noqa: E402 — tras el guard HAS_QT
from packages.application.project_service import ProjectService  # noqa: E402 — tras el guard HAS_QT
from packages.application.watering_service import WateringService  # noqa: E402 — guard HAS_QT
from packages.domain.entity import NarrativeEntity  # noqa: E402 — tras el guard HAS_QT
from packages.domain.result import Ok  # noqa: E402 — tras el guard HAS_QT
from packages.infrastructure.ai_provider import AIProvider  # noqa: E402 — tras el guard HAS_QT

_PAYLOAD = {
    "scores": {"arraigo": 34, "nutrida": 71, "iluminada": 18},
    "summary": "Nutrida pero sin raíces.",
    "metric_explanations": {"arraigo": "Sin causa previa."},
    "risks": ["Flota sin sostén"],
}


class FakeProvider(AIProvider):
    provider_name = "fake_drawer"
    model = "fake-model-1"

    def __init__(self, fail_marker: str = ""):
        self.fail_marker = fail_marker
        self.calls: list[str] = []

    def chat(self, system_prompt: str, user_message: str, timeout=None):
        self.calls.append(user_message)
        if self.fail_marker and self.fail_marker in user_message:
            return None, "timeout simulado"
        return json.dumps(_PAYLOAD, ensure_ascii=False), None


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _setup(fail_marker: str = ""):
    project_service = ProjectService()
    project_service.create("Drawer")
    ai_service = AIJobService(
        provider=FakeProvider(fail_marker),
        project_provider=lambda: project_service.active_project,
    )
    watering = WateringService(
        project_service, ai_job_service=ai_service, history_service=HistoryService(project_service)
    )
    return project_service, watering


def _entity(project_service, name, **kwargs):
    entity = NarrativeEntity(name=name, **kwargs)
    project_service.active_project.entities.append(entity)
    project_service.active_project.touch()
    return entity


def _panel(watering):
    from hosts.DesktopHostPySide.widgets.foco.watering_panel import WateringPanel

    return WateringPanel(watering)


class TestWateringPanel:
    def test_never_watered_shows_no_metrics(self, qapp):
        project_service, watering = _setup()
        entity = _entity(project_service, "Nueva")
        panel = _panel(watering)
        panel.set_entity(entity.id)

        assert "nunca regada" in panel.status_chip.text()
        assert panel.bars["arraigo"][1].text() == "—"
        assert all(not b.isEnabled() for b in panel.suggest_buttons.values())
        assert panel.water_button.isEnabled()

    def test_watered_shows_bars_history_and_weak_suggests(self, qapp):
        project_service, watering = _setup()
        entity = _entity(project_service, "Banda")
        assert isinstance(watering.water_entity(entity.id), Ok)
        panel = _panel(watering)
        panel.set_entity(entity.id)

        assert panel.current_status() == "regada"
        assert panel.bars["arraigo"][0].value() == 34
        assert panel.bars["arraigo"][1].text() == "34%"
        assert panel.bars["relevancia"][0].value() == 50  # del usuario (MEDIO)
        assert "Nutrida pero sin raíces" in panel.summary_label.text()
        assert "coste" in panel.context_label.text()
        assert panel.history_list.count() == 1
        # Débil (<60) habilita Sugerir; fuerte no. Calidad siempre con lectura.
        assert panel.suggest_buttons["arraigo"].isEnabled()
        assert not panel.suggest_buttons["nutrida"].isEnabled()
        assert panel.suggest_buttons["iluminada"].isEnabled()
        assert panel.suggest_buttons["calidad"].isEnabled()

    def test_stale_reading_is_dimmed(self, qapp):
        project_service, watering = _setup()
        entity = _entity(project_service, "Banda")
        watering.water_entity(entity.id)
        entity.updated_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        project_service.active_project.touch()
        panel = _panel(watering)
        panel.set_entity(entity.id)

        assert panel.current_status() == "falta_regar"
        assert "ant." in panel.bars["arraigo"][1].text()  # lectura antigua atenuada
        assert "Lectura antigua" in panel.state_note.text()

    def test_pause_toggle_flow(self, qapp):
        project_service, watering = _setup()
        entity = _entity(project_service, "Dormible")
        panel = _panel(watering)
        panel.set_entity(entity.id)
        toggles: list[bool] = []
        panel.pauseToggled.connect(toggles.append)

        panel._toggle_pause()  # en ciclo → pide Secar
        assert toggles == [True]
        assert isinstance(watering.pause(entity.id), Ok)  # (lo haría el workspace)
        panel.refresh()
        assert panel.current_status() == "secada"
        assert panel.pause_button.text() == "Cultivar"
        assert not panel.water_button.isEnabled()

        panel._toggle_pause()  # secada → pide Cultivar
        assert toggles == [True, False]

    def test_batch_failure_is_traceable_in_history(self, qapp):
        project_service, watering = _setup()
        entity = _entity(project_service, "Fallona")
        watering.record_failure(entity.id, "timeout simulado")
        panel = _panel(watering)
        panel.set_entity(entity.id)

        assert "timeout simulado" in panel.state_note.text()
        assert "FALLO" in panel.history_list.item(0).text()


class TestAuthorization:
    def test_panel_renders_and_routes_buttons(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.watering_authorize import (
            WateringAuthorizePanel,
        )

        confirmed: list[bool] = []
        cancelled: list[bool] = []
        panel = WateringAuthorizePanel(
            title="Regar 2 entidades",
            lines=["Entidades: A, B", "Tokens: ~900"],
            cost_class="medio",
            confirm_text="Autorizar y regar",
            on_confirm=lambda: confirmed.append(True),
            on_cancel=lambda: cancelled.append(True),
        )
        assert panel.cost_chip.text() == "MEDIO"
        panel.authorize_button.click()
        panel.cancel_button.click()
        assert confirmed == [True] and cancelled == [True]

    def test_overlay_flow_requires_explicit_confirmation(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.watering_authorize import (
            request_watering_authorization,
        )
        from hosts.DesktopHostPySide.widgets.modal_overlay import ModalOverlay

        host = QWidget()
        host.resize(800, 600)
        host.show()  # offscreen: is_open exige isVisible() del overlay/host
        overlay = ModalOverlay(host)
        confirmed: list[bool] = []
        panel = request_watering_authorization(
            overlay,
            title="Regar 1 entidad",
            lines=["línea"],
            cost_class="bajo",
            confirm_text="Autorizar y regar",
            on_confirm=lambda: confirmed.append(True),
        )
        assert overlay.is_open
        assert confirmed == []  # sin click NO se consume IA
        panel.authorize_button.click()
        assert confirmed == [True]
        assert not overlay.is_open

    def test_without_overlay_nothing_runs(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.watering_authorize import (
            request_watering_authorization,
        )

        confirmed: list[bool] = []
        result = request_watering_authorization(
            None,
            title="x",
            lines=[],
            cost_class="bajo",
            confirm_text="ok",
            on_confirm=lambda: confirmed.append(True),
        )
        assert result is None and confirmed == []


class TestBatchWorker:
    def test_partials_and_traceable_failure(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.watering_batch import WateringBatchWorker

        project_service, watering = _setup(fail_marker="Fallona")
        ids = [
            _entity(project_service, "Alfa").id,
            _entity(project_service, "Fallona").id,
            _entity(project_service, "Zeta").id,
        ]
        worker = WateringBatchWorker(watering, ids)
        done: list[tuple] = []
        progress: list[tuple] = []
        finished: list[bool] = []
        worker.entityDone.connect(lambda eid, ok, err: done.append((eid, ok, err)))
        worker.progressChanged.connect(lambda d, t: progress.append((d, t)))
        worker.finishedOk.connect(lambda: finished.append(True))

        worker.run()  # síncrono en el test (mismo código que en el hilo)
        assert [ok for _, ok, _ in done] == [True, False, True]
        assert "timeout" in done[1][2]
        assert progress == [(1, 3), (2, 3), (3, 3)]
        assert finished == [True]
        assert len(project_service.active_project.watering_diagnostics) == 3

    def test_cancel_between_steps_keeps_partials(self, qapp):
        from hosts.DesktopHostPySide.widgets.foco.watering_batch import WateringBatchWorker

        project_service, watering = _setup()
        ids = [_entity(project_service, f"E{i}").id for i in range(3)]
        worker = WateringBatchWorker(watering, ids)
        worker.entityDone.connect(lambda *_: worker.request_cancel())
        finished: list[bool] = []
        worker.finishedOk.connect(lambda: finished.append(True))

        worker.run()
        assert len(project_service.active_project.watering_diagnostics) == 1  # parcial
        assert finished == [True]


class TestWorkspaceWiring:
    def test_watering_flow_is_wired_with_authorization_first(self):
        source = Path("hosts/DesktopHostPySide/views/workspaces.py").read_text(encoding="utf-8")
        assert "self.foco.waterRequested.connect(self._on_foco_water)" in source
        assert "self.foco.dryRequested.connect(self._on_foco_dry)" in source
        assert "self.foco.cultivateRequested.connect(self._on_foco_cultivate)" in source
        assert "WateringService(" in source
        # Autorización SIEMPRE antes del lote y de las sugerencias.
        water_body = source.split("def _on_foco_water", 1)[1].split("def _run_watering_batch")[0]
        assert "request_watering_authorization" in water_body
        assert "provider_unconfigured" in water_body
        suggest_body = source.split("def _on_foco_suggest", 1)[1]
        assert "request_watering_authorization" in suggest_body
        assert "_launch_toolbar_ai_job" in suggest_body
        assert "track_worker(worker)" in source
