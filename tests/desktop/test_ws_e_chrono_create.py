"""BETA-CIERRE WS-E: botones ＋Hito / ＋Era visibles en la Cronología.

Antes solo se podía crear hito/era por clic derecho (invisible para un usuario
nuevo); y en un proyecto vacío el scrubber+embudo están ocultos, justo cuando más
falta hace el primer hito/era. Ahora una barra de creación siempre visible los
ofrece, reutilizando las señales del menú contextual.
"""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

if HAS_QT:
    from PySide6.QtWidgets import QApplication, QPushButton

    from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _project():
    return SimpleNamespace(
        entities=[], relations=[], world_layers=[], causal_milestones=[],
        project_chronology=SimpleNamespace(present_year=100, eras=[], metadata={}),
    )


def _view():
    v = ChronoCanvasView()
    v._collapse_default = False
    v.set_atmosphere_context(SimpleNamespace(creation_chrono_expanded_ids=[]))
    v.resize(900, 500)
    v.set_project(_project())
    return v


def test_toolbar_hidden_without_project(qapp):
    v = ChronoCanvasView()
    v.resize(900, 500)
    # Sin set_project, la barra existe pero no se muestra.
    assert v._create_toolbar.isHidden()
    v.deleteLater()


def test_toolbar_visible_with_project_and_has_two_buttons(qapp):
    v = _view()
    assert not v._create_toolbar.isHidden()  # visible al cargar proyecto (incluso vacío)
    labels = [b.text() for b in v._create_toolbar.findChildren(QPushButton)]
    assert any("Hito" in t for t in labels)
    assert any("Era" in t for t in labels)
    v.deleteLater()


def test_hito_button_emits_with_present_year(qapp):
    v = _view()
    got = []
    v.milestoneCreateRequested.connect(lambda year, era: got.append((year, era)))
    v._emit_create_milestone()
    assert got == [(100, "")]  # sugiere el presente; era vacía (editable en el panel)
    v.deleteLater()


def test_era_button_emits_era_create(qapp):
    v = _view()
    fired = []
    v.eraCreateRequested.connect(lambda: fired.append(True))
    era_btn = next(
        b for b in v._create_toolbar.findChildren(QPushButton) if "Era" in b.text()
    )
    era_btn.click()
    assert fired == [True]
    v.deleteLater()
