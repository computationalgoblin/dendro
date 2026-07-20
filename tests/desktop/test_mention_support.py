"""BETA2-MEM-03: soporte de @menciones en editores de prosa (offscreen)."""

from __future__ import annotations

import os

import pytest

try:
    from PySide6.QtGui import QTextCursor
    from PySide6.QtWidgets import QApplication, QTextEdit

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


_TARGETS = [
    ("e3", "Bob", "entity"),
    ("e1", "Aria", "entity"),
    ("e2", "Aria", "entity"),  # nombre duplicado → ambiguo
    ("r1", "Politica", "ring"),
]


def _edit_with(qapp, text: str) -> QTextEdit:
    from hosts.DesktopHostPySide.widgets.mention_support import attach_mention_support

    te = QTextEdit()
    ms = attach_mention_support(te, lambda: list(_TARGETS))
    te.setPlainText(text)
    te.moveCursor(QTextCursor.MoveOperation.End)
    return te, ms


def test_pick_unique_name_inserts_and_binds_id(qapp):
    te, ms = _edit_with(qapp, "Habla con @Bo")
    ms._insert_completion("Bob")
    assert te.toPlainText() == "Habla con @Bob "
    assert ms.hints() == {"bob": ("entity", "e3")}


def test_pick_ring_binds_kind(qapp):
    te, ms = _edit_with(qapp, "En @Pol")
    ms._insert_completion("Politica")
    assert "@Politica " in te.toPlainText()
    assert ms.hints() == {"politica": ("ring", "r1")}


def test_pick_duplicate_name_records_no_hint(qapp):
    te, ms = _edit_with(qapp, "Sobre @Ar")
    ms._insert_completion("Aria")
    assert "@Aria " in te.toPlainText()
    assert ms.hints() == {}  # ambiguo: no se fija id en silencio


def test_highlighter_is_attached(qapp):
    te, ms = _edit_with(qapp, "@Bob y @Aria")
    assert ms._highlighter is not None
    assert ms._highlighter.document() is te.document()
