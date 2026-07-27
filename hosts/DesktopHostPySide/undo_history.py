"""Historial de deshacer/rehacer por INSTANTÁNEA de documento (BETA-CIERRE WS-C).

Cada mutación de canon "asentada" (tras el autoguardado) captura un snapshot
completo del proyecto vía ``project.to_dict()`` — la MISMA serialización que la
persistencia usa (``ProjectStore.save`` guarda ``to_dict`` y carga con
``Project.from_dict``, así que el ida-y-vuelta es sin pérdida y ya está probado).

Deshacer/rehacer restauran un snapshot ENTERO. Es correcto para CUALQUIER
mutación —incluidas las que cascada, como borrar una entidad que arrastra sus
relaciones— sin modelo paralelo ni comandos por-campo frágiles que tendrían que
reconstruir el estado cascadeado a mano (el riesgo real de un undo parcial). El
coste es memoria: se acota la profundidad de la pila.

Puro (dict de entrada, dict de salida): testeable sin Qt ni disco.
"""

from __future__ import annotations

import copy


class UndoHistory:
    """Pila lineal de instantáneas con un cursor al estado actual."""

    def __init__(self, capacity: int = 40) -> None:
        # Mínimo 2: el estado base + al menos un paso para poder deshacer.
        self._capacity = max(2, int(capacity))
        self._stack: list[dict] = []
        self._cursor = -1  # índice del estado ACTUAL dentro de _stack

    def reset(self, snapshot: dict | None) -> None:
        """Reinicia el historial con el estado base (al cargar/crear proyecto).

        ``None`` deja el historial vacío (sin proyecto activo)."""
        if snapshot is None:
            self._stack = []
            self._cursor = -1
            return
        self._stack = [copy.deepcopy(snapshot)]
        self._cursor = 0

    def record(self, snapshot: dict | None) -> bool:
        """Registra un nuevo estado tras una mutación asentada.

        Devuelve ``False`` (sin registrar) si no hay snapshot, si el historial no
        está inicializado, o si el estado es idéntico al actual (coalescencia de
        guardados no-op). Trunca cualquier cola de *rehacer* pendiente."""
        if snapshot is None:
            return False
        if self._cursor < 0:
            self.reset(snapshot)
            return True
        if snapshot == self._stack[self._cursor]:
            return False  # sin cambios reales → no ensuciar el historial
        # Una mutación nueva invalida la rama de rehacer.
        del self._stack[self._cursor + 1:]
        self._stack.append(copy.deepcopy(snapshot))
        self._cursor += 1
        # Acota la profundidad: descarta los estados más antiguos.
        overflow = len(self._stack) - self._capacity
        if overflow > 0:
            del self._stack[:overflow]
            self._cursor -= overflow
        return True

    def can_undo(self) -> bool:
        return self._cursor > 0

    def can_redo(self) -> bool:
        return 0 <= self._cursor < len(self._stack) - 1

    def undo(self) -> dict | None:
        """Mueve el cursor un paso atrás y devuelve ese snapshot (o ``None``)."""
        if not self.can_undo():
            return None
        self._cursor -= 1
        return copy.deepcopy(self._stack[self._cursor])

    def redo(self) -> dict | None:
        """Mueve el cursor un paso adelante y devuelve ese snapshot (o ``None``)."""
        if not self.can_redo():
            return None
        self._cursor += 1
        return copy.deepcopy(self._stack[self._cursor])

    def depth(self) -> int:
        """Número de instantáneas guardadas (para tests/diagnóstico)."""
        return len(self._stack)


__all__ = ["UndoHistory"]
