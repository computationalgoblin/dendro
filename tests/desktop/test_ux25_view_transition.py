"""Transición entre vistas vía revelado dentro del viewport (BETA1-UX25/UX31).

El velo overlay no se veía sobre el viewport GPU; ahora el revelado se pinta DENTRO
de la vista (play_reveal → drawForeground). Aquí verificamos el ruteo y el no-op.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace


@pytest.fixture(scope="module", autouse=True)
def _app():
    app = QApplication.instance() or QApplication([])
    yield app


def _stub(duration_mult: float = 1.0):
    calls = {"graph": 0, "chrono": 0}
    graph = SimpleNamespace(play_reveal=lambda **k: calls.__setitem__("graph", calls["graph"] + 1))
    chrono = SimpleNamespace(
        play_reveal=lambda **k: calls.__setitem__("chrono", calls["chrono"] + 1)
    )
    stub = SimpleNamespace(
        graph=graph,
        chrono=chrono,
        ctx=SimpleNamespace(animation_duration=lambda ms: int(ms * duration_mult)),
    )
    return stub, calls


def test_revela_la_vista_cronologica_entrante() -> None:
    stub, calls = _stub()
    CreationWorkspace._play_view_transition(stub, True)
    QApplication.processEvents()  # el reveal se difiere un tick (singleShot 0)
    assert calls["chrono"] == 1 and calls["graph"] == 0


def test_revela_la_vista_grafo_entrante() -> None:
    stub, calls = _stub()
    CreationWorkspace._play_view_transition(stub, False)
    QApplication.processEvents()
    assert calls["graph"] == 1 and calls["chrono"] == 0


def test_sin_animacion_es_noop() -> None:
    stub, calls = _stub(duration_mult=0.0)  # animation_duration → 0
    CreationWorkspace._play_view_transition(stub, True)
    assert calls["chrono"] == 0 and calls["graph"] == 0


def test_failsoft_si_no_hay_play_reveal() -> None:
    # Vista sin play_reveal (p. ej. stub viejo): no debe lanzar.
    stub = SimpleNamespace(
        graph=SimpleNamespace(),
        chrono=SimpleNamespace(),
        ctx=SimpleNamespace(animation_duration=lambda ms: ms),
    )
    CreationWorkspace._play_view_transition(stub, True)  # no exception
