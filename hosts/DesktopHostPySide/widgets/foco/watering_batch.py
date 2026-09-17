"""Worker de riego en lote (BETA2-FOCO-12), patrón AUDIT-02.

Recorre las entidades UNA a una llamando a ``water_batch_step`` (cada paso
persiste su diagnóstico o su fallo trazable). Cancelación cooperativa ENTRE
pasos; el guardado silencioso lo dispara el slot de UI en ``entityDone``
(NUNCA desde este hilo). Registrar siempre con ``track_worker``.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any

from PySide6.QtCore import QThread, Signal

from packages.domain.result import Error


class WateringBatchWorker(QThread):
    """Riega ids en secuencia; los parciales quedan persistidos pase lo que pase."""

    entityStarted = Signal(str)  # noqa: N815 — UI2-05: empieza a regarse entity_id
    entityDone = Signal(str, bool, str)  # noqa: N815 — (entity_id, ok, error)
    progressChanged = Signal(int, int)  # noqa: N815 — (hechas, total)
    # BETA2-FIX-06 (G2-08): fase EN CURSO del paso (entity_id, mensaje, %).
    # Es una Signal, no un setText: `water_entity` corre en ESTE hilo y tocar un widget
    # desde aquí es un crash esperando su turno (patrón `_SuggestionPrepWorker`).
    phaseChanged = Signal(str, str, int)  # noqa: N815 — (entity_id, mensaje, porcentaje)
    finishedOk = Signal()  # noqa: N815 — convención Qt de señales

    def __init__(self, watering_service: Any, entity_ids: list[str], parent=None) -> None:
        super().__init__(parent)
        self._service = watering_service
        self._entity_ids = [str(entity_id) for entity_id in entity_ids if entity_id]
        self._cancel_requested = False

    def accepts_progress_callback(self) -> bool:
        """¿El servicio de riego acepta ``progress_callback`` en ``water_batch_step``?

        BETA2-FIX-06: el servicio real sí; los dobles de test con firma
        estrecha, no. Preguntarlo evita que un `TypeError` convierta cada paso en un
        «riego fallido» (el `except` de abajo se lo tragaría) por culpa del feedback.
        """
        step = getattr(self._service, "water_batch_step", None)
        if step is None:
            return False
        try:
            params = inspect.signature(step).parameters
        except (TypeError, ValueError):  # builtins / callables sin firma introspectable
            return False
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return True
        return "progress_callback" in params

    def _emit_phase(self, entity_id: str, job: Any) -> None:
        """Traduce el AIJob del pipeline a (mensaje, %) y lo marshalla a la UI."""
        try:
            message = str(getattr(job, "message", "") or "")
            progress = float(getattr(job, "progress", 0.0) or 0.0)
        except Exception:  # noqa: BLE001 — el feedback jamás rompe el riego
            return
        percent = int(max(0.0, min(1.0, progress)) * 100)
        self.phaseChanged.emit(entity_id, message, percent)

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
        con_fases = self.accepts_progress_callback()
        try:
            for index, entity_id in enumerate(self._entity_ids):
                if self._cancel_requested:
                    break
                self.entityStarted.emit(entity_id)  # UI2-05: feedback vivo en Mapa/Foco
                try:
                    # BETA-FIX-01: el paso conoce el lote completo para
                    # que la propagación de impacto no invalide a sus compañeras.
                    extra: dict[str, Any] = {}
                    if con_fases:
                        # FIX-06 (G2-08): las fases del pipeline llegan al indicador
                        # global mientras se riega, como ya llegan en una Sugerencia.
                        extra["progress_callback"] = (
                            lambda job, eid=entity_id: self._emit_phase(eid, job)
                        )
                    result = self._service.water_batch_step(
                        entity_id, batch_ids=list(self._entity_ids), **extra
                    )
                    if isinstance(result, Error):
                        self.entityDone.emit(entity_id, False, result.error)
                    else:
                        self.entityDone.emit(entity_id, True, "")
                except TypeError as exc:
                    # BETA2-FIX-05 (G2-05, punto 10): un `TypeError` aquí NO
                    # es un riego fallido: es una firma incompatible de
                    # `water_batch_step` (un error de programación) que este `except`
                    # convertía en «riego fallido» sin traza. Se nombra distinto para
                    # que se distinga del fallo de proveedor en el informe del lote.
                    logging.getLogger(__name__).exception(
                        "WateringBatchWorker: firma incompatible de water_batch_step"
                    )
                    self.entityDone.emit(
                        entity_id, False, f"error de programación (firma incompatible): {exc}"
                    )
                except Exception as exc:  # noqa: BLE001 — un paso caído no mata el lote
                    self.entityDone.emit(entity_id, False, f"error interno: {exc}")
                self.progressChanged.emit(index + 1, total)
        finally:
            self.finishedOk.emit()
