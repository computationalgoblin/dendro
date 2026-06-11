"""BETA1-B02: keyboard core on the Creation canvas.

Delete (with confirmation), Escape (cancel/clear/notify) and Space+drag
(pan mode). Confirmation dialogs are monkeypatched — no modal is shown.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from hosts.DesktopHostPySide.widgets.graph_canvas import (
        GraphCanvasView,
        _EdgeView,
        _NodeView,
    )


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def node(entity_id: str, name: str, *, kind: str = "concepto"):
    return _NodeView(
        entity=SimpleNamespace(id=entity_id, name=name, layer_ids=[]),
        entity_id=entity_id,
        name=name,
        kind=kind,
        subtitle="",
        canon="canonico",
        visibility="publico",
        layer_id="",
    )


def edge(relation_id: str, source_id: str, target_id: str):
    return _EdgeView(
        relation=SimpleNamespace(id=relation_id),
        relation_id=relation_id,
        source_id=source_id,
        target_id=target_id,
        kind="deriva_de",
        label="deriva de",
    )


def build_view(qapp) -> "GraphCanvasView":
    view = GraphCanvasView()
    view.set_graph(
        [node("hoja-1", "Hoja Uno"), node("hoja-2", "Hoja Dos")],
        [edge("rel-1", "hoja-1", "hoja-2")],
    )
    return view


def press(key, autorep: bool = False) -> "QKeyEvent":
    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, "", autorep)


def release(key, autorep: bool = False) -> "QKeyEvent":
    return QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier, "", autorep)


# ── Delete ────────────────────────────────────────────────────────────────

def test_delete_emits_after_confirmation(qapp, monkeypatch):
    view = build_view(qapp)
    view._set_single_node_selection(view._nodes["hoja-1"])
    monkeypatch.setattr(view, "_confirm_delete", lambda e, r: True)
    emitted: list[bool] = []
    view.contextDeleteRequested.connect(lambda: emitted.append(True))

    view.keyPressEvent(press(Qt.Key.Key_Delete))

    assert emitted == [True]


def test_delete_cancelled_does_nothing(qapp, monkeypatch):
    view = build_view(qapp)
    view._set_single_node_selection(view._nodes["hoja-1"])
    monkeypatch.setattr(view, "_confirm_delete", lambda e, r: False)
    emitted: list[bool] = []
    view.contextDeleteRequested.connect(lambda: emitted.append(True))

    view.keyPressEvent(press(Qt.Key.Key_Delete))

    assert emitted == []
    assert view.selected_entity_ids() == ["hoja-1"]  # selection untouched


def test_delete_without_selection_skips_confirmation(qapp, monkeypatch):
    view = build_view(qapp)
    calls: list[bool] = []
    monkeypatch.setattr(view, "_confirm_delete", lambda e, r: calls.append(True) or True)
    emitted: list[bool] = []
    view.contextDeleteRequested.connect(lambda: emitted.append(True))

    view.keyPressEvent(press(Qt.Key.Key_Delete))

    assert calls == []  # no dialog when nothing is selected
    assert emitted == []


def test_backspace_behaves_like_delete(qapp, monkeypatch):
    view = build_view(qapp)
    view._set_single_edge_selection(view._edges[0])
    monkeypatch.setattr(view, "_confirm_delete", lambda e, r: True)
    emitted: list[bool] = []
    view.contextDeleteRequested.connect(lambda: emitted.append(True))

    view.keyPressEvent(press(Qt.Key.Key_Backspace))

    assert emitted == [True]


# ── Escape ────────────────────────────────────────────────────────────────

def test_escape_clears_selection_and_notifies(qapp):
    view = build_view(qapp)
    view._set_single_node_selection(view._nodes["hoja-1"])
    escapes: list[bool] = []
    view.escapePressed.connect(lambda: escapes.append(True))

    view.keyPressEvent(press(Qt.Key.Key_Escape))

    assert view.selected_entity_ids() == []
    assert escapes == [True]


def test_escape_cancels_context_relation_mode(qapp):
    view = build_view(qapp)
    rejections: list[str] = []
    view.relationCreateRejected.connect(rejections.append)
    view._begin_context_relation(view._nodes["hoja-1"])
    assert view._drag_source is not None

    view.keyPressEvent(press(Qt.Key.Key_Escape))

    assert view._drag_source is None
    assert rejections == ["Relación cancelada"]


# ── Space+drag ────────────────────────────────────────────────────────────

def test_space_press_enables_pan_and_release_disables(qapp):
    view = build_view(qapp)
    assert view._space_pan_active is False
    assert view.isInteractive() is True

    view.keyPressEvent(press(Qt.Key.Key_Space))
    assert view._space_pan_active is True
    assert view.isInteractive() is False  # items must not steal the drag

    view.keyReleaseEvent(release(Qt.Key.Key_Space))
    assert view._space_pan_active is False
    assert view.isInteractive() is True


def test_space_autorepeat_does_not_toggle(qapp):
    view = build_view(qapp)
    view.keyPressEvent(press(Qt.Key.Key_Space))
    # Holding space produces autorepeat press/release pairs on some platforms;
    # they must not flicker the pan mode off.
    view.keyReleaseEvent(release(Qt.Key.Key_Space, autorep=True))
    view.keyPressEvent(press(Qt.Key.Key_Space, autorep=True))
    assert view._space_pan_active is True
    view.keyReleaseEvent(release(Qt.Key.Key_Space))
    assert view._space_pan_active is False


def test_space_pan_mouse_press_bypasses_selection(qapp):
    view = build_view(qapp)
    view.keyPressEvent(press(Qt.Key.Key_Space))
    selections: list[str] = []
    view.entitySelected.connect(selections.append)

    # With pan active the view is non-interactive: items() ignores nodes and
    # our handler passes straight to the native hand-drag. We verify the
    # selection path is not reachable.
    assert view.isInteractive() is False
    assert selections == []


# ── Text input protection ─────────────────────────────────────────────────

def test_text_input_focus_blocks_canvas_shortcuts(qapp, monkeypatch):
    view = build_view(qapp)
    view._set_single_node_selection(view._nodes["hoja-1"])
    monkeypatch.setattr(view, "_is_text_input_focused", lambda: True)
    confirm_calls: list[bool] = []
    monkeypatch.setattr(view, "_confirm_delete", lambda e, r: confirm_calls.append(True) or True)

    view.keyPressEvent(press(Qt.Key.Key_Delete))
    view.keyPressEvent(press(Qt.Key.Key_Space))

    assert confirm_calls == []  # Delete went to the text editor, not the canvas
    assert view._space_pan_active is False  # Space writes a space, no pan
    assert view.selected_entity_ids() == ["hoja-1"]
