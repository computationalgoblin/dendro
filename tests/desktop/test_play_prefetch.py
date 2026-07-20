"""BETA2-PLAY-08 — prefetch del paso N+1 (offscreen).

El worker se prueba como hilo REAL con controller falso; la lógica de cache,
epoch y adopción vive en el workspace y se fija con pins de fuente (patrón de
la casa: construir CreationWorkspace headless cuelga PySide6). Las garantías
del servicio (analyze_step_at sin mutación / commit_step al llegar) ya están
cubiertas en tests/application/test_chronology_walk_service.py.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeCtrl:
    def __init__(self, result=None, error=""):
        from packages.domain.result import Error, Ok

        self._res = Error(error) if error else Ok(dict(result or {}))
        self.calls: list[tuple[str, str]] = []

    def analyze_at(self, session_id, milestone_id):
        self.calls.append((session_id, milestone_id))
        return self._res


def _drain(worker, qapp):
    assert worker.wait(5000)
    qapp.processEvents()  # entrega de señales encoladas entre hilos


class TestPrefetchWorker:
    def test_worker_emits_result_with_its_epoch(self, qapp):
        from hosts.DesktopHostPySide.views.workspaces import _PlayPrefetchWorker

        ctrl = _FakeCtrl(result={"model_payload": {"summary": "ok"}, "job_id": "j1"})
        worker = _PlayPrefetchWorker(ctrl, "s1", "h2", 7)
        got: list[tuple[str, int, dict]] = []
        worker.finishedOk.connect(lambda mid, epoch, res: got.append((mid, epoch, dict(res))))

        worker.start()
        _drain(worker, qapp)

        assert ctrl.calls == [("s1", "h2")]
        assert len(got) == 1
        mid, epoch, res = got[0]
        assert (mid, epoch) == ("h2", 7)  # el epoch viaja con el resultado
        assert res["job_id"] == "j1"

    def test_worker_emits_failure_without_result(self, qapp):
        from hosts.DesktopHostPySide.views.workspaces import _PlayPrefetchWorker

        worker = _PlayPrefetchWorker(_FakeCtrl(error="sin proveedor"), "s1", "h2", 1)
        errors: list[str] = []
        oks: list[object] = []
        worker.failed.connect(errors.append)
        worker.finishedOk.connect(lambda *a: oks.append(a))

        worker.start()
        _drain(worker, qapp)

        assert errors == ["sin proveedor"]
        assert oks == []


class TestPrefetchWiring:
    """Pins de fuente: cache-hit, adopción, epoch y puntos de invalidación."""

    def test_cache_hit_commits_without_thread(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "self._play_prefetch_cache.pop(mid_now, None)" in source
        assert "ctrl.commit(sid, mid_now, cached)" in source

    def test_inflight_prefetch_is_adopted_or_queued_never_duplicated(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "self._play_adopt_step = True" in source
        assert "self._play_step_queued = True" in source
        # El siguiente prefetch solo arranca sin análisis vivo (regla a).
        assert "if self._walk_analyzing:\n            return  # regla (a)" in source

    def test_epoch_guards_and_invalidation_sites(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "if int(epoch) != self._play_epoch:" in source  # rancio → descartado
        assert "def _invalidate_play_prefetch" in source
        # Invalida SOLO lo que muta canon: edición inline y aplicar candidatos.
        assert source.count("self._invalidate_play_prefetch()") == 2
        # Aplazar/avanzar no aparecen invalidando (no cambian canon).
        assert "PLAY-08: la edición cambia canon" in source
        assert "PLAY-08: aplicar cambia canon" in source

    def test_prefetch_launches_after_each_step(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "self._maybe_prefetch_next()" in source
        assert "_PlayPrefetchWorker(ctrl, sid, next_mid, self._play_epoch)" in source
        assert "track_worker(worker)" in source
