"""BETA1-UX2B: stepper −/+ y entrada numérica exacta del tuner."""
from __future__ import annotations

import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")

if HAS_QT:
    from PySide6.QtWidgets import QApplication, QSpinBox

    from hosts.DesktopHostPySide.widgets.radial_tuner import RadialTuner
    from hosts.DesktopHostPySide.widgets.stepper import BotanicalSpinBox


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_stepper_is_spinbox_with_compatible_api(qapp):
    spin = BotanicalSpinBox()
    # Sigue siendo un QSpinBox (los isinstance del código siguen funcionando).
    assert isinstance(spin, QSpinBox)
    spin.setRange(1, 10)
    spin.setValue(3)
    assert spin.value() == 3
    spin._step(+1)  # botón +
    assert spin.value() == 4
    spin._step(-1)  # botón −
    assert spin.value() == 3
    # No usa las flechas nativas.
    assert spin.buttonSymbols() == QSpinBox.ButtonSymbols.NoButtons


def test_stepper_clamps_to_range(qapp):
    spin = BotanicalSpinBox()
    spin.setRange(1, 3)
    spin.setValue(3)
    spin._step(+1)
    assert spin.value() == 3  # no pasa del máximo


def test_tuner_click_to_type_exact_value(qapp):
    tuner = RadialTuner(minimum=256, maximum=24000, value=2000, is_integer=True, auto=True)
    emitted = []
    tuner.valueChanged.connect(lambda v: emitted.append(v))
    tuner._begin_edit()
    assert tuner._editor is not None
    tuner._editor.setText("8000")
    tuner._commit_edit()
    assert tuner._editor is None
    assert not tuner.is_auto  # teclear deja el modo Auto
    assert abs(tuner.value() - 8000) < 1
    assert emitted and abs(emitted[-1] - 8000) < 1


def test_tuner_exact_value_clamped(qapp):
    tuner = RadialTuner(minimum=0.0, maximum=1.0, value=0.5, is_integer=False, auto=False)
    tuner._begin_edit()
    tuner._editor.setText("5")  # fuera de rango
    tuner._commit_edit()
    assert tuner.value() <= 1.0


def test_tuner_decimal_editor_uses_dot_not_locale_comma(qapp):
    # BETA1-UX2D regresión: el texto mostrado usa PUNTO, pero el validador
    # heredaba el locale (es-ES → COMA) y bloqueaba teclear el "." que se ve.
    # El editor y su validador deben usar locale C (punto) y aceptar "0.7".
    from PySide6.QtGui import QValidator

    tuner = RadialTuner(minimum=0.0, maximum=1.0, value=0.5, is_integer=False, auto=False)
    tuner._begin_edit()
    editor = tuner._editor
    assert editor.locale().decimalPoint() == "."
    validator = editor.validator()
    state, _txt, _pos = validator.validate("0.7", 3)
    assert state == QValidator.State.Acceptable
    editor.setText("0.7")
    tuner._commit_edit()
    assert abs(tuner.value() - 0.7) < 0.01
    assert not tuner.is_auto
