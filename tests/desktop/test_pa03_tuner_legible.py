"""PA03: el número del RadialTuner nunca desborda el círculo + renombrado."""

from __future__ import annotations

import pytest

from hosts.DesktopHostPySide.widgets.radial_tuner import RadialTuner, abbreviate_int


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app


@pytest.mark.parametrize(
    "value,expected",
    [(256, "256"), (2000, "2k"), (2800, "2.8k"), (24000, "24k"), (600000, "600k")],
)
def test_abbreviate_int(value, expected):
    assert abbreviate_int(value) == expected


def test_large_value_renders_without_overflow(qapp):
    from PySide6.QtGui import QFontMetrics

    # Valor grande en manual: el texto compactado debe caber en el círculo.
    t = RadialTuner(minimum=2000, maximum=600000, value=600000, is_integer=True, auto=False)
    pixmap = t.grab()  # fuerza paintEvent sin excepción
    assert pixmap.width() >= t._diameter

    text = abbreviate_int(t.value())
    inner = max(8, t._diameter - 8)
    # Existe un tamaño de fuente >=6 con el que el texto cabe (lo que hace paintEvent).
    font = t.font()
    size = 11
    font.setPointSize(size)
    while size > 6 and QFontMetrics(font).horizontalAdvance(text) > inner:
        size -= 1
        font.setPointSize(size)
    assert QFontMetrics(font).horizontalAdvance(text) <= inner
