"""BETA-CIERRE WS-J: el overline aplica el tracking DE VERDAD (QFont), no con un
``letter-spacing`` de QSS que Qt ignora en silencio.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_overline_uppercases_and_tracks(app):
    from hosts.DesktopHostPySide.widgets.design_system import overline_label

    lbl = overline_label("sección")
    assert lbl.text() == "SECCIÓN"  # mayúsculas en Python (no el text-transform inerte)
    font = lbl.font()
    assert font.letterSpacingType() == QFont.SpacingType.AbsoluteSpacing
    assert font.letterSpacing() == 1.0  # el tracking se aplica de verdad
    # El QSS ya no arrastra el prop que Qt ignora.
    assert "letter-spacing" not in lbl.styleSheet()


def test_overline_qss_block_has_no_dead_props():
    from pathlib import Path

    ds = Path("hosts/DesktopHostPySide/widgets/design_system.py").read_text(encoding="utf-8")
    block = ds.split("QLabel#overline {{")[1].split("}}")[0]
    assert "letter-spacing" not in block
    assert "text-transform" not in block
