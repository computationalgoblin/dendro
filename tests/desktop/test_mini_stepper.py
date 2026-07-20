"""BETA2-CAL-07 — MiniStepper: spinner minimalista escribible.

El número debe verse siempre y poder teclearse; `‹›`/`−+` incrementan; el rango
acota; la señal `valueChanged` sólo salta cuando el valor cambia.
"""

from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

if HAS_QT:
    from hosts.DesktopHostPySide.widgets.mini_stepper import MiniStepper


pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_type_a_value(qapp):
    s = MiniStepper(minimum=1, maximum=100, value=10)
    s._edit.setText("42")
    s._on_edited()
    assert s.value() == 42


def test_buttons_step_and_clamp(qapp):
    s = MiniStepper(minimum=1, maximum=3, value=1)
    seen = []
    s.valueChanged.connect(lambda v: seen.append(v))
    s._plus.click()
    s._plus.click()
    s._plus.click()  # clamp en 3, sin nueva señal
    assert s.value() == 3
    assert seen == [2, 3]
    assert s._plus.isEnabled() is False  # tope superior


def test_minus_disabled_at_minimum(qapp):
    s = MiniStepper(minimum=5, maximum=10, value=5)
    assert s._minus.isEnabled() is False
    s._plus.click()
    assert s._minus.isEnabled() is True


def test_typed_over_range_clamps(qapp):
    s = MiniStepper(minimum=1, maximum=50, value=10)
    s._edit.setText("999")
    s._on_edited()
    assert s.value() == 50


def test_setvalue_emits_only_on_change(qapp):
    s = MiniStepper(minimum=0, maximum=10, value=4)
    seen = []
    s.valueChanged.connect(lambda v: seen.append(v))
    s.setValue(4)  # mismo valor → sin señal
    assert seen == []
    s.setValue(7)
    assert seen == [7]


def test_setrange_reclamps_without_spurious_signal(qapp):
    s = MiniStepper(minimum=0, maximum=100, value=80)
    seen = []
    s.valueChanged.connect(lambda v: seen.append(v))
    s.setRange(0, 50)  # 80 → 50
    assert s.value() == 50
    assert s.maximum() == 50
    assert seen == [50]


def test_blocksignals_suppresses_emit(qapp):
    s = MiniStepper(minimum=0, maximum=10, value=1)
    seen = []
    s.valueChanged.connect(lambda v: seen.append(v))
    s.blockSignals(True)
    s.setValue(9)
    s.blockSignals(False)
    assert s.value() == 9
    assert seen == []  # sincronización programática no dispara
