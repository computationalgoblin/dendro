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
        total = len(self._entity_ids)
        for index, entity_id in enumerate(self._entity_ids):
            if self._cancel_requested:
                break
            result = self._service.water_batch_step(entity_id)
            if isinstance(result, Error):
                self.entityDone.emit(entity_id, False, result.error)
            else:
                self.entityDone.emit(entity_id, True, "")
            self.progressChanged.emit(index + 1, total)
        self.finishedOk.emit()
