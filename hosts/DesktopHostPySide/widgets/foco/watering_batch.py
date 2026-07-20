"""Worker de riego en lote (BETA2-FOCO-12), patrón AUDIT-02.

Recorre las entidades UNA a una llamando a ``water_batch_step`` (cada paso
persiste su diagnóstico o su fallo trazable). Cancelación cooperativa ENTRE
pasos; el guardado silencioso lo dispara el slot de UI en ``entityDone``
(NUNCA desde este hilo). Registrar siempre con ``track_worker``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, Signal

from packages.domain.result import Error


class WateringBatchWorker(QThread):
    """Riega ids en secuencia; los parciales quedan persistidos pase lo que pase."""

    entityStarted = Signal(str)  # noqa: N815 — UI2-05: empieza a regarse entity_id
    entityDone = Signal(str, bool, str)  # noqa: N815 — (entity_id, ok, error)
    progressChanged = Signal(int, int)  # noqa: N815 — (hechas, total)
    finishedOk = Signal()  # noqa: N815 — convención Qt de señales

    def __init__(self, watering_service: Any, entity_ids: list[str], parent=None) -> None:
        super().__init__(parent)
        self._service = watering_service
        self._entity_ids = [str(entity_id) for entity_id in entity_ids if entity_id]
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Cancelación cooperativa: se comprueba ENTRE entidades."""
        self._cancel_requested = True

    def cancel_requested(self) -> bool:
        return self._cancel_requested

    def run(self) -> None:  # noqa: N802 (API Qt)
        # BETA2-FOCO-35: cada paso es a prueba de excepciones y ``finishedOk`` se
        # emite SIEMPRE (finally). Antes, una excepción en un paso (p. ej. una
        # carrera lock-free del Project con el guardado del hilo UI) mataba el hilo
        # sin emitir ``finishedOk`` → el lote quedaba colgado en silencio.
        total = len(self._entity_ids)
        try:
            for index, entity_id in enumerate(self._entity_ids):
                if self._cancel_requested:
                    break
                self.entityStarted.emit(entity_id)  # UI2-05: feedback vivo en Mapa/Foco
                try:
                    result = self._service.water_batch_step(entity_id)
                    if isinstance(result, Error):
                        self.entityDone.emit(entity_id, False, result.error)
                    else:
                        self.entityDone.emit(entity_id, True, "")
                except Exception as exc:  # noqa: BLE001 — un paso caído no mata el lote
                    self.entityDone.emit(entity_id, False, f"error interno: {exc}")
                self.progressChanged.emit(index + 1, total)
        finally:
            self.finishedOk.emit()
