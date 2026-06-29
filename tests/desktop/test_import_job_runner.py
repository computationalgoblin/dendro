"""UX33 — ImportJobRunner: jobs de importación con dueño persistente.

Verifica el dedupe por basket, la reemisión de señales (Ok/Error) y la limpieza,
con un controller fake síncrono-bloqueante (sin proveedor IA real ni disco).
"""

from __future__ import annotations

import threading
import time

import pytest

from packages.domain.result import Error, Ok

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.controllers.import_job_runner import ImportJobRunner  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _spin_until(predicate, timeout_s: float = 3.0) -> bool:
    """Procesa el bucle de eventos hasta que ``predicate()`` sea cierto o expire."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return False


class _GatedController:
    """Fake: ``extract_ai_candidates``/``propose_scaffolding`` se bloquean en un
    Event hasta que el test lo libera, para poder observar el job 'en curso'."""

    def __init__(self, result):
        self.ps = object()
        self.gate = threading.Event()
        self.calls = 0
        self._result = result

    def extract_ai_candidates(self, basket_id, *, progress_callback=None, should_cancel=None):
        self.calls += 1
        self.gate.wait(3.0)
        return self._result

    def propose_scaffolding(self, basket_id):
        self.calls += 1
        self.gate.wait(3.0)
        return self._result


@pytest.fixture
def make_runner(qapp):
    """Crea runners con un controller fake y garantiza apagado limpio (evita
    'QThread destroyed while running' al recolectar el runner con workers vivos)."""
    created: list[tuple[ImportJobRunner, _GatedController]] = []

    def _factory(result):
        runner = ImportJobRunner(controller=type("C", (), {"ps": None})())
        fake = _GatedController(result)
        runner._ic = fake  # sustituye el ImportController real por el fake
        created.append((runner, fake))
        return runner, fake

    yield _factory

    for runner, fake in created:
        fake.gate.set()          # libera cualquier worker bloqueado
        runner.shutdown()        # cancela + wait()
        _spin_until(lambda r=runner: not r._workers)  # drena 'finished'/reap


def test_extraction_emits_done_with_count(make_runner):
    runner, fake = make_runner(Ok(["a", "b", "c"]))
    done: list[tuple] = []
    runner.extractionDone.connect(lambda bid, count, err: done.append((bid, count, err)))

    assert runner.start_extraction("b1") is True
    fake.gate.set()
    assert _spin_until(lambda: bool(done))
    assert done == [("b1", 3, "")]
    assert not runner.is_running("b1")


def test_extraction_error_emits_done_with_message(make_runner):
    runner, fake = make_runner(Error("sin proveedor"))
    done: list[tuple] = []
    runner.extractionDone.connect(lambda bid, count, err: done.append((bid, count, err)))

    runner.start_extraction("b2")
    fake.gate.set()
    assert _spin_until(lambda: bool(done))
    assert done[0][0] == "b2"
    assert done[0][1] == 0
    assert "sin proveedor" in done[0][2]


def test_dedupe_while_running(make_runner):
    runner, fake = make_runner(Ok(["x"]))
    # El worker queda bloqueado en el gate → el basket sigue registrado.
    assert runner.start_extraction("b3") is True
    assert runner.start_extraction("b3") is False  # dedupe: un worker por basket
    fake.gate.set()
    assert _spin_until(lambda: "b3" not in runner._workers)


def test_scaffolding_done_signal(make_runner):
    runner, fake = make_runner(Ok({"chronology": {}}))
    done: list[tuple] = []
    runner.scaffoldingDone.connect(lambda bid, ok, err: done.append((bid, ok, err)))

    runner.start_scaffolding("b4")
    fake.gate.set()
    assert _spin_until(lambda: bool(done))
    assert done[0][0] == "b4" and done[0][1] is True
