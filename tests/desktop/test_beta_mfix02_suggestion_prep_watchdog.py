"""BETA-FIX-02: preparación de Sugerencias con vigilante (G-02).

- compose_generation emite las fases por progress_callback y respeta cancel_check
  ENTRE fases (corte cooperativo).
- _SuggestionPrepWorker distingue cancelado / fallo / éxito en su señal `done`
  (antes un fallo caía en silencio al payload base y una cancelación lo lanzaba).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.views.workspaces import _SuggestionPrepWorker  # noqa: E402
from packages.application.watering_service import WateringService  # noqa: E402
from packages.domain.entity import EntityType, NarrativeEntity  # noqa: E402
from packages.domain.project import Project  # noqa: E402
from packages.domain.result import Error, Ok  # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


class _PS:
    def __init__(self, project):
        self.active_project = project


class _FakeAI:
    """AIJobService mínimo: configurado (no simulado), sin llamadas reales."""

    provider = None

    def provider_unconfigured(self) -> bool:
        return False


def _service() -> tuple[WateringService, str]:
    proj = Project(name="FIX-02")
    entity = NarrativeEntity(name="Yara", entity_type=EntityType.PERSONAJE)
    proj.entities.append(entity)
    svc = WateringService(_PS(proj), ai_job_service=_FakeAI())
    return svc, entity.id


# ── compose_generation: fases y cancelación ─────────────────────────────────


def test_compose_emite_fase_de_navegacion():
    svc, eid = _service()
    fases: list[str] = []
    res = svc.compose_generation(eid, "calidad", "pulir", progress_callback=fases.append)
    assert isinstance(res, Ok)
    assert fases == ["Navegando la wiki (1/1)…"]  # calidad no corre intención


def test_compose_cancelada_entre_fases_devuelve_error():
    svc, eid = _service()
    res = svc.compose_generation(eid, "calidad", "pulir", cancel_check=lambda: True)
    assert isinstance(res, Error)
    assert "cancelada" in res.error.lower()


def test_compose_sin_callbacks_sigue_funcionando():
    svc, eid = _service()
    res = svc.compose_generation(eid, "calidad", "pulir")
    assert isinstance(res, Ok)
    assert res.value.get("prompt")


# ── _SuggestionPrepWorker: la señal done distingue resultados ───────────────


class _StubSvc:
    def __init__(self, result):
        self._result = result

    def compose_generation(self, *a, **k):
        return self._result


def _collect_done(worker) -> list:
    seen: list = []
    worker.done.connect(seen.append)
    worker.run()  # síncrono a propósito: probamos la semántica, no el hilo
    return seen


def test_worker_exito_emite_payload(app):
    stub = _StubSvc(Ok({"prompt": "p", "job_type": "x"}))
    worker = _SuggestionPrepWorker(stub, "e", "calidad", "")
    seen = _collect_done(worker)
    assert seen and seen[0].get("prompt") == "p"


def test_worker_fallo_emite_marcador_de_error(app):
    worker = _SuggestionPrepWorker(_StubSvc(Error("proveedor caído")), "e", "calidad", "")
    seen = _collect_done(worker)
    assert seen and seen[0].get("__error__") == "proveedor caído"
    assert not seen[0].get("prompt")  # el host degrada VISIBLEMENTE, no lanza esto


def test_worker_progreso_reemite_las_fases(app):
    fases: list[str] = []

    class _PhasedSvc:
        def compose_generation(self, *a, progress_callback=None, **k):
            progress_callback("Navegando la wiki (1/2)…")
            progress_callback("Analizando la petición (2/2)…")
            return Ok({"prompt": "p"})

    worker = _SuggestionPrepWorker(_PhasedSvc(), "e", "arraigo", "petición")
    worker.progressText.connect(fases.append)
    worker.run()
    assert fases == ["Navegando la wiki (1/2)…", "Analizando la petición (2/2)…"]
