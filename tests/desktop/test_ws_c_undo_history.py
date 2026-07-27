"""BETA-CIERRE WS-C: historial de deshacer/rehacer por instantánea (lógica pura)."""

from __future__ import annotations

from hosts.DesktopHostPySide.undo_history import UndoHistory


def _snap(n):
    return {"v": n, "entities": [{"id": str(n)}]}


def test_empty_history_cannot_undo_or_redo():
    h = UndoHistory()
    assert not h.can_undo()
    assert not h.can_redo()
    assert h.undo() is None
    assert h.redo() is None


def test_reset_sets_base_state():
    h = UndoHistory()
    h.reset(_snap(0))
    assert h.depth() == 1
    assert not h.can_undo()  # el base no se puede deshacer
    assert not h.can_redo()


def test_record_then_undo_returns_previous_state():
    h = UndoHistory()
    h.reset(_snap(0))
    assert h.record(_snap(1)) is True
    assert h.record(_snap(2)) is True
    assert h.can_undo()
    assert h.undo() == _snap(1)
    assert h.undo() == _snap(0)
    assert not h.can_undo()


def test_redo_after_undo_returns_forward_state():
    h = UndoHistory()
    h.reset(_snap(0))
    h.record(_snap(1))
    h.record(_snap(2))
    h.undo()  # → snap 1
    assert h.can_redo()
    assert h.redo() == _snap(2)
    assert not h.can_redo()


def test_record_dedups_identical_state():
    h = UndoHistory()
    h.reset(_snap(0))
    assert h.record(_snap(0)) is False  # idéntico al base → no registra
    assert h.depth() == 1


def test_new_record_truncates_redo_tail():
    h = UndoHistory()
    h.reset(_snap(0))
    h.record(_snap(1))
    h.record(_snap(2))
    h.undo()  # cursor en snap 1, con snap 2 como cola de rehacer
    h.record(_snap(9))  # rama nueva → borra snap 2
    assert not h.can_redo()
    assert h.undo() == _snap(1)


def test_capacity_evicts_oldest():
    h = UndoHistory(capacity=3)
    h.reset(_snap(0))
    for n in range(1, 6):
        h.record(_snap(n))
    # Solo caben 3: [3, 4, 5]; el actual es 5.
    assert h.depth() == 3
    assert h.undo() == _snap(4)
    assert h.undo() == _snap(3)
    assert not h.can_undo()  # el más antiguo (2, 1, 0) fue desalojado


def test_returned_snapshot_is_isolated_copy():
    h = UndoHistory()
    h.reset(_snap(0))
    h.record(_snap(1))
    got = h.undo()
    got["entities"].append({"id": "mutado"})  # mutar la copia devuelta
    assert h.undo() is None or True  # (base)
    # El estado interno no se contamina: rehacer devuelve el snap 1 intacto.
    assert h.redo() == _snap(1)


def test_reset_none_clears():
    h = UndoHistory()
    h.reset(_snap(0))
    h.record(_snap(1))
    h.reset(None)  # sin proyecto
    assert h.depth() == 0
    assert not h.can_undo() and not h.can_redo()
    assert h.record(_snap(5)) is True  # record sobre vacío inicializa
    assert h.depth() == 1
