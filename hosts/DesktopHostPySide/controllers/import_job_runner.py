"""ImportJobRunner — dueño persistente de los jobs de importación (UX33).

Antes, los QThread de andamiaje (Fase 1) y de extracción (Fase 2) colgaban de la
``ImportExportView``, que vive en el cajón derecho. Al cerrar el cajón (o al
reemplazar su contenido por el panel de config) la vista se destruía y arrastraba
al worker → la extracción moría a medias.

Este runner es propiedad de ``MainWindow`` (no de ninguna vista): posee los
workers (``parent=self``), uno por ``basket_id``, los mantiene vivos hasta que
terminan y reemite sus señales con el ``basket_id`` para que cualquier vista
abierta refresque y para que MainWindow autoguarde + avise al terminar.

Patrón espejo de ``_AIJobWorker``/``self._ai_workers`` en workspaces.py.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from hosts.DesktopHostPySide.controllers.import_controller import ImportController
from packages.domain.result import Error


class _ImportExtractionWorker(QThread):
    """Ejecuta la extracción IA de candidatos en segundo plano (I17).

    Emite ``progress(done, total, label)`` por segmento y ``finishedOk(list)`` /
    ``failed(str)`` al terminar. ``cancel()`` corta entre segmentos.
    """

    progress = Signal(int, int, str)
    finishedOk = Signal(list)
    failed = Signal(str)

    def __init__(self, controller, basket_id: str, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._basket_id = basket_id
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            result = self._controller.extract_ai_candidates(
                self._basket_id,
                progress_callback=lambda done, total, label: self.progress.emit(
                    int(done), int(total), str(label)
                ),
                should_cancel=lambda: self._cancel,
            )
        except Exception as exc:  # noqa: BLE001 — frontera de hilo
            self.failed.emit(str(exc))
            return
        if isinstance(result, Error):
            self.failed.emit(str(result.error))
        else:
            self.finishedOk.emit(list(getattr(result, "value", None) or []))


class _ScaffoldingWorker(QThread):
    """Propone el andamiaje del mundo en segundo plano (I22 Fase 1).

    Una sola llamada IA a nivel documento (config + calendario + anillos + hitos).
    Emite ``finishedOk(dict)`` con la propuesta o ``failed(str)``.
    """

    finishedOk = Signal(dict)
    failed = Signal(str)

    def __init__(self, controller, basket_id: str, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._basket_id = basket_id

    def run(self):
        try:
            result = self._controller.propose_scaffolding(self._basket_id)
        except Exception as exc:  # noqa: BLE001 — frontera de hilo
            self.failed.emit(str(exc))
            return
        if isinstance(result, Error):
            self.failed.emit(str(result.error))
        else:
            self.finishedOk.emit(dict(getattr(result, "value", None) or {}))


class ImportJobRunner(QObject):
    """Dueño persistente de los jobs de importación por ``basket_id``.

    Un worker vivo por basket (dedupe). Reemite las señales del worker añadiendo
    el ``basket_id`` para que la UI (vista + MainWindow) reaccione sin poseer el
    worker. Las señales QThread→este QObject(hilo principal) se entregan en cola,
    así que los slots conectados corren en el hilo principal (save/notify seguros).
    """

    scaffoldingDone = Signal(str, bool, str)        # basket_id, ok, error
    extractionStarted = Signal(str)                 # basket_id
    extractionProgress = Signal(str, int, int, str)  # basket_id, done, total, label
    extractionDone = Signal(str, int, str)          # basket_id, count, error ("" si ok)

    def __init__(self, controller: Any, parent: QObject | None = None):
        super().__init__(parent)
        # Un ImportController reusable derivado del project_service activo (como
        # hacía la vista). No depende de ninguna vista.
        self._ic = ImportController(project_service=getattr(controller, "ps", None))
        self._workers: dict[str, QThread] = {}
        self._kinds: dict[str, str] = {}  # basket_id → "scaffolding" | "extraction"

    # ── Consultas ────────────────────────────────────────────────────────
    def is_running(self, basket_id: str) -> bool:
        worker = self._workers.get(basket_id)
        return worker is not None and worker.isRunning()

    def running_kind(self, basket_id: str) -> str | None:
        return self._kinds.get(basket_id) if self.is_running(basket_id) else None

    # ── Lanzadores ───────────────────────────────────────────────────────
    def start_scaffolding(self, basket_id: str) -> bool:
        """Lanza la Fase 1. Devuelve False si ya hay un job vivo para el basket."""
        if basket_id in self._workers:
            return False
        worker = _ScaffoldingWorker(self._ic, basket_id, parent=self)
        self._track(basket_id, worker, "scaffolding")
        worker.finishedOk.connect(
            lambda _proposal, bid=basket_id: self.scaffoldingDone.emit(bid, True, "")
        )
        worker.failed.connect(
            lambda error, bid=basket_id: self.scaffoldingDone.emit(bid, False, str(error))
        )
        worker.start()
        return True

    def start_extraction(self, basket_id: str) -> bool:
        """Lanza la Fase 2. Devuelve False si ya hay un job vivo para el basket."""
        if basket_id in self._workers:
            return False
        worker = _ImportExtractionWorker(self._ic, basket_id, parent=self)
        self._track(basket_id, worker, "extraction")
        worker.progress.connect(
            lambda done, total, label, bid=basket_id: self.extractionProgress.emit(
                bid, int(done), int(total), str(label)
            )
        )
        worker.finishedOk.connect(
            lambda candidates, bid=basket_id: self.extractionDone.emit(
                bid, len(candidates or []), ""
            )
        )
        worker.failed.connect(
            lambda error, bid=basket_id: self.extractionDone.emit(bid, 0, str(error))
        )
        worker.start()
        self.extractionStarted.emit(basket_id)
        return True

    def cancel_extraction(self, basket_id: str) -> None:
        worker = self._workers.get(basket_id)
        if isinstance(worker, _ImportExtractionWorker) and worker.isRunning():
            worker.cancel()

    # ── Ciclo de vida ────────────────────────────────────────────────────
    def _track(self, basket_id: str, worker: QThread, kind: str) -> None:
        self._workers[basket_id] = worker
        self._kinds[basket_id] = kind
        # ``finished`` se entrega en el hilo principal: limpia la ref para no
        # filtrar QThreads ni bloquear un relanzamiento del mismo basket.
        worker.finished.connect(lambda bid=basket_id: self._reap(bid))

    def _reap(self, basket_id: str) -> None:
        worker = self._workers.pop(basket_id, None)
        self._kinds.pop(basket_id, None)
        if worker is not None:
            worker.deleteLater()

    def shutdown(self) -> None:
        """Cancela y espera (corto) los workers vivos al cerrar la app.

        Evita el aborto 'QThread destroyed while still running'. Best-effort: si
        un worker no termina a tiempo, se sigue cerrando.
        """
        for worker in list(self._workers.values()):
            if isinstance(worker, _ImportExtractionWorker):
                worker.cancel()
            if worker.isRunning():
                worker.wait(2000)
