"""PA02: estado Auto del RadialTuner (no envía override hasta tocarlo)."""

from __future__ import annotations

import pytest

from hosts.DesktopHostPySide.widgets.radial_tuner import RadialTuner


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app


def test_tuner_starts_auto_and_shows_hint(qapp):
    t = RadialTuner(minimum=256, maximum=24000, value=2000, is_integer=True, auto=True)
    assert t.is_auto is True
    t.set_hint(6000)
    # En Auto el valor mostrado refleja el hint (default por tarea).
    assert t.value() == 6000
    assert t.is_auto is True  # set_hint no saca de Auto


def test_dragging_leaves_auto_and_emits(qapp):
    t = RadialTuner(minimum=0.0, maximum=1.0, value=0.7, is_integer=False, auto=True)
    seen = []
    t.valueChanged.connect(seen.append)
    # Simula un arrastre comprometiendo una fracción.
    t._commit_fraction(0.5)
    assert t.is_auto is False
    assert seen, "drag debe emitir valueChanged"


def test_double_click_resets_to_auto(qapp):
    t = RadialTuner(minimum=0.0, maximum=1.0, value=0.7, is_integer=False, auto=True)
    t.set_hint(0.4)
    t._commit_fraction(0.9)  # manual
    assert t.is_auto is False
    t.set_auto(True)  # equivalente al doble clic
    assert t.is_auto is True
    assert t.value() == pytest.approx(0.4, abs=0.02)


def test_set_range_keeps_auto_hint(qapp):
    t = RadialTuner(minimum=2000, maximum=24000, value=4000, is_integer=True, auto=True)
    t.set_hint(40000)
    t.set_range(2000, 600000)
    assert t.is_auto is True
    assert t.value() == 40000
