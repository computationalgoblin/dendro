"""BETA2-UX-09: edición de lapso robusta + persistencia de colapso.

- Un clic plano sobre el mango NUNCA edita el lapso (abre la entidad); solo
  Alt+arrastra inicia la edición. Evita la edición accidental por el temblor del
  clic con la vista alejada.
- El colapso/expansión de ramas persiste (preferencia de app) y se respeta al
  reconstruir la escena, incluido el conjunto vacío (todo colapsado).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _press(view, *, alt: bool):
    pos = QPointF(20.0, 20.0)
    mods = Qt.KeyboardModifier.AltModifier if alt else Qt.KeyboardModifier.NoModifier
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pos,
        pos,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        mods,
    )


class TestLapseGesture:
    def test_plain_click_on_handle_does_not_start_edit(self, qapp):
        view = ChronoCanvasView()
        # El cursor está sobre un mango (birth) y dispatch_click abriría la entidad.
        view._handle_at = lambda _pos: ("ent-1", "birth")
        dispatched: list = []
        view._dispatch_click = lambda _pos: (dispatched.append(True) or True)

        view.mousePressEvent(_press(view, alt=False))

        assert view._press_handle is None  # NO se captura el mango para arrastrar
        assert dispatched == [True]  # cae a dispatch_click → abre la entidad

    def test_alt_press_on_handle_starts_edit(self, qapp):
        view = ChronoCanvasView()
        view._handle_at = lambda _pos: ("ent-1", "birth")
        dispatched: list = []
        view._dispatch_click = lambda _pos: (dispatched.append(True) or True)

        view.mousePressEvent(_press(view, alt=True))

        assert view._press_handle == ("ent-1", "birth")  # capturado para arrastrar
        assert dispatched == []  # NO abre la entidad; espera el arrastre


class TestCollapsePersistence:
    def _ctx(self, expanded):
        return SimpleNamespace(
            creation_chrono_expanded_ids=list(expanded),
            save_preferences=lambda: None,
            reduced_motion=False,
        )

    def test_expanded_ids_loaded_from_context(self, qapp):
        view = ChronoCanvasView()
        view.set_atmosphere_context(self._ctx(["branch-1"]))
        assert view._expanded_ids == {"branch-1"}

    def test_set_project_reloads_persisted_collapse(self, qapp):
        view = ChronoCanvasView()
        ctx = self._ctx(["branch-1"])
        view.set_atmosphere_context(ctx)
        # Otra rama se expande fuera (persistida en ctx) → set_project la respeta.
        ctx.creation_chrono_expanded_ids = ["branch-1", "branch-2"]
        view.set_project(None)
        assert view._expanded_ids == {"branch-1", "branch-2"}

    def test_empty_set_means_all_collapsed_persists(self, qapp):
        view = ChronoCanvasView()
        ctx = self._ctx(["branch-1"])
        view.set_atmosphere_context(ctx)
        ctx.creation_chrono_expanded_ids = []  # todo colapsado
        view.set_project(None)
        assert view._expanded_ids == set()
