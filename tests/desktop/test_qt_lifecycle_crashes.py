"""Regresión BETA1-K01: crashes por acceso a objetos Qt ya destruidos.

Dos crashes confirmados en dendro_crash.log (libshiboken: Internal C++ object
already deleted):

- Crash 3: `BaseSlideDrawer._replace_content` tocaba el panel anterior (o el
  entrante) sin comprobar su validez. Aquí forzamos la destrucción C++ del panel
  con `shiboken6.delete` y verificamos que reemplazar contenido no lanza
  `RuntimeError`.
- Crash 2: `_apply_repair_changes` llamaba a un método inexistente
  (`_save_project_if_possible`). Guard estático: el método muerto no debe volver
  y debe existir el correcto (`_save_project_from_canvas`).

También cubre el helper compartido `_qt_alive`, base de ambos fixes.

Ejecutar por-archivo (la carpeta desktop completa segfaulta):
    QT_QPA_PLATFORM=offscreen python -m pytest tests/desktop/test_qt_lifecycle_crashes.py -q
"""
from __future__ import annotations

import inspect

import pytest
import shiboken6
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from hosts.DesktopHostPySide.widgets.qt_lifecycle import (
    _qt_alive,
    _qt_safe_slot,
    _qt_safe_timer,
)
from hosts.DesktopHostPySide.widgets.right_drawer import RightDrawer


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _drawer():
    parent = QWidget()
    parent.resize(1100, 800)
    d = RightDrawer(parent)
    d._parent_keepalive = parent  # evita que el padre muera antes de tiempo
    return d


# ── Helper _qt_alive ─────────────────────────────────────────────────────────
def test_qt_alive_distingue_vivo_de_borrado():
    w = QWidget()
    assert _qt_alive(w) is True
    assert _qt_alive(None) is False
    shiboken6.delete(w)
    assert _qt_alive(w) is False


# ── Crash 3: BaseSlideDrawer._replace_content ────────────────────────────────
def test_drawer_replace_content_survives_deleted_panel():
    """El panel anterior fue destruido por Qt; reemplazar no debe crashear."""
    d = _drawer()
    panel = QLabel("recorrido")
    d.set_content(panel, "Recorrido cronológico")
    # Qt destruye el panel (reparentado/deleteLater externo simulado).
    shiboken6.delete(panel)
    assert not _qt_alive(panel)

    nuevo = QLabel("nuevo")
    d.set_content(nuevo, "Otro")  # antes: RuntimeError en old.hide()/takeWidget
    assert d._content is nuevo


def test_drawer_set_content_ignores_dead_incoming_widget():
    """Si el widget entrante ya está muerto, el cajón queda vacío, no crashea."""
    d = _drawer()
    d.set_content(QLabel("vivo"), "Uno")

    muerto = QLabel("muerto")
    shiboken6.delete(muerto)
    d.set_content(muerto, "Dos")  # antes: RuntimeError en setWidget/show
    assert d._content is None


# ── Crash 2: referencia muerta de guardado ───────────────────────────────────
def test_creation_workspace_has_no_dead_save_reference():
    from hosts.DesktopHostPySide.views import workspaces

    source = inspect.getsource(workspaces)
    assert "_save_project_if_possible" not in source, (
        "Reapareció la referencia al método inexistente (crash 2)"
    )
    assert hasattr(workspaces.CreationWorkspace, "_save_project_from_canvas")


# ── Barrido sistemático: _qt_safe_slot / _qt_safe_timer ──────────────────────
class _Dummy(QWidget):
    def __init__(self):
        super().__init__()
        self.ran = False

    @_qt_safe_slot
    def do(self, value):
        self.ran = True
        return value

    @_qt_safe_slot
    def touch_dead(self, child):
        child.objectName()  # RuntimeError si el hijo fue borrado
        self.ran = True

    @_qt_safe_slot
    def boom(self):
        raise RuntimeError("error no relacionado")


def test_qt_safe_slot_runs_when_alive():
    d = _Dummy()
    assert d.do(7) == 7
    assert d.ran is True


def test_qt_safe_slot_skips_when_self_dead():
    d = _Dummy()
    shiboken6.delete(d)
    assert d.do(7) is None  # no ejecuta el cuerpo ni crashea


def test_qt_safe_slot_swallows_deleted_child_error():
    d = _Dummy()
    child = QWidget()
    shiboken6.delete(child)
    assert d.touch_dead(child) is None  # absorbe RuntimeError 'already deleted'
    assert d.ran is False


def test_qt_safe_slot_reraises_unrelated_runtimeerror():
    d = _Dummy()
    with pytest.raises(RuntimeError, match="no relacionado"):
        d.boom()


def test_qt_safe_timer_skips_when_widget_dead(_app):
    calls = []
    w = QWidget()
    shiboken6.delete(w)
    _qt_safe_timer(w, 0, calls.append, "x")
    for _ in range(5):
        _app.processEvents()
    assert calls == []  # widget muerto → callback no se ejecuta


def test_qt_safe_timer_runs_when_alive(_app):
    calls = []
    w = QWidget()
    _qt_safe_timer(w, 0, calls.append, "ok")
    for _ in range(5):
        _app.processEvents()
    assert calls == ["ok"]
