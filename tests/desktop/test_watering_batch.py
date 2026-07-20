"""BETA2-FOCO-35 — el worker de riego en lote es a prueba de cuelgues.

Un paso que revienta marca la entidad como fallida y el lote continúa; ``finishedOk``
se emite SIEMPRE (antes, una excepción en un paso mataba el hilo sin emitirlo → el
lote quedaba colgado en silencio). Además, el lote ya NO abre el drawer por-entidad.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

if HAS_QT:
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.widgets.foco.watering_batch import WateringBatchWorker
    from packages.domain.result import Ok


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _BoomService:
    """water_batch_step OK salvo para una entidad, que lanza una excepción."""

    def __init__(self, boom_on: str) -> None:
        self.boom_on = boom_on
        self.calls: list[str] = []

    def water_batch_step(self, entity_id):
        self.calls.append(entity_id)
        if entity_id == self.boom_on:
            raise RuntimeError("carrera lock-free del Project")
        return Ok(None)


def test_batch_step_exception_does_not_hang(qapp):
    service = _BoomService(boom_on="b")
    worker = WateringBatchWorker(service, ["a", "b", "c"])
    done: list[tuple[str, bool]] = []
    progress: list[tuple[int, int]] = []
    finished: list[bool] = []
    worker.entityDone.connect(lambda eid, ok, err: done.append((eid, ok)))
    worker.progressChanged.connect(lambda d, t: progress.append((d, t)))
    worker.finishedOk.connect(lambda: finished.append(True))

    worker.run()  # sincrónico en el test (no start()): la excepción no cuelga

    assert [eid for eid, _ in done] == ["a", "b", "c"]  # los 3 procesados
    assert done[1] == ("b", False)  # el que revienta → fallido, no mata el lote
    assert progress == [(1, 3), (2, 3), (3, 3)]  # progreso por paso
    assert finished == [True]  # finishedOk SIEMPRE emitido


def test_batch_flow_does_not_open_per_entity_drawer(qapp):
    # BETA2-FOCO-35: el lote ya no abre el drawer «Riego» por-entidad (era el
    # gatillo del cuelgue al borrarse al navegar).
    src = Path(__file__).resolve().parents[2] / "hosts/DesktopHostPySide/views/workspaces.py"
    text = src.read_text(encoding="utf-8")
    start = text.index("def _run_watering_batch(")
    end = text.index("def _cancel_watering_batch(", start)
    body = text[start:end]
    assert "_open_watering_drawer" not in body
    assert "waterProgressRequested.connect(self._open_watering_progress)" in text


# ── BETA2-FOCO-39: los slots del lote son a prueba de cosméticos que revientan ──


def _fake_workspace():
    """Stub mínimo para invocar los slots del lote (sin montar el workspace).

    Los refrescos del Mapa REVIENTAN a propósito (simulan el ``AttributeError``
    de regar una rama sin ``set_watering_pulse``): lo ESENCIAL (aviso, reset del
    badge) debe correr igual."""
    import types
    from types import SimpleNamespace

    def _boom(*_a, **_k):
        raise AttributeError("'GraphTreeItem' object has no attribute 'set_watering_pulse'")

    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    fake = SimpleNamespace()
    fake.avisos = []
    fake.logs = []
    fake.badge_resets = []
    fake._batch_state = {}
    fake._batch_total = 0
    fake._watering_progress_popover = None
    fake.ctx = SimpleNamespace(
        log=lambda lvl, msg: fake.logs.append((lvl, msg)),
        request_save_silent=lambda: None,
    )
    fake.graph = SimpleNamespace(set_watering_active=_boom, refresh_garden_status=lambda: None)
    fake.foco = SimpleNamespace(
        set_watering_active=lambda eid: None,
        current_entity_id=lambda: "",
        refresh_cultivation=lambda: None,
        _refresh_tool_context=lambda: None,
    )
    fake._seed_notifications = SimpleNamespace(
        set_watering_progress=lambda d, t: fake.badge_resets.append((d, t))
    )
    fake._job_status_label = SimpleNamespace(setText=lambda s: None)
    fake._request_thirsty_refresh = lambda: None
    fake._raise_cultivo_aviso = lambda eid: fake.avisos.append(eid)
    fake._refresh_watering_progress_popover = lambda **k: None
    fake._refresh_focused_cultivation = types.MethodType(
        CreationWorkspace._refresh_focused_cultivation, fake
    )
    fake._run_batch_cosmetics = types.MethodType(CreationWorkspace._run_batch_cosmetics, fake)
    return CreationWorkspace, fake


def test_run_batch_cosmetics_isolates_each_failure(qapp):
    cls, fake = _fake_workspace()
    ran = []
    cls._run_batch_cosmetics(
        fake,
        lambda: ran.append("a"),
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),  # revienta en medio
        lambda: ran.append("c"),
    )
    assert ran == ["a", "c"]  # el fallo del medio no salta los demás
    assert any("omitido" in m for _, m in fake.logs)


def test_entity_done_raises_aviso_despite_map_crash(qapp):
    # BETA2-FOCO-39: el aviso de Cultivo sale aunque el refresco del Mapa reviente
    # (antes el AttributeError abortaba el slot ANTES del aviso).
    cls, fake = _fake_workspace()
    cls._on_watering_entity_done.__wrapped__(fake, "e1", True, "")
    assert fake.avisos == ["e1"]
    assert fake._batch_state["e1"] == "done"


def test_finished_resets_badge_despite_map_crash(qapp):
    # BETA2-FOCO-39: el badge se resetea (0, 0) aunque un cosmético reviente —
    # antes quedaba congelado en «Regando x/y».
    cls, fake = _fake_workspace()
    fake._batch_state = {"e1": "done"}
    fake._batch_total = 1
    cls._on_watering_finished.__wrapped__(fake)
    assert (0, 0) in fake.badge_resets
    assert fake._batch_state == {} and fake._batch_total == 0
