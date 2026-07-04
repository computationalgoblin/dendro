"""BETA2-FOCO-17: tema claro forzado (texto legible) y tooltips estilados.

En Windows 11 con modo oscuro, Qt aplicaba una QPalette oscura: el texto de
inputs sin ``color`` en QSS (p. ej. el line-edit interno de un QComboBox
editable) se veía blanco sobre pergamino, y los tooltips salían ilegibles
(la causa raíz de la supresión global de BETA1-F00, ahora retirada).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication, QComboBox

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

_HOST_DIR = Path(__file__).resolve().parents[2] / "hosts" / "DesktopHostPySide"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class TestLightTheme:
    def test_apply_light_theme_pins_ink_on_parchment(self, qapp):
        from hosts.DesktopHostPySide.widgets.design_system import (
            INK,
            PAPER,
            SURFACE_HI,
            apply_light_theme,
        )

        apply_light_theme(qapp)
        palette = qapp.palette()

        assert palette.color(QPalette.ColorRole.Text).name().upper() == INK.upper()
        assert palette.color(QPalette.ColorRole.WindowText).name().upper() == INK.upper()
        assert palette.color(QPalette.ColorRole.Window).name().upper() == PAPER.upper()
        assert (
            palette.color(QPalette.ColorRole.ToolTipBase).name().upper()
            == SURFACE_HI.upper()
        )
        assert palette.color(QPalette.ColorRole.ToolTipText).name().upper() == INK.upper()

    def test_editable_combo_line_edit_inherits_dark_ink(self, qapp):
        from hosts.DesktopHostPySide.widgets.design_system import (
            APP_STYLESHEET,
            INK,
            apply_light_theme,
        )

        apply_light_theme(qapp)
        combo = QComboBox()
        combo.setEditable(True)
        combo.setStyleSheet(APP_STYLESHEET)
        line = combo.lineEdit()
        assert line is not None
        # Con la paleta clara aplicada, el texto efectivo del line-edit interno
        # es tinta (antes: blanco de la paleta oscura del SO).
        assert line.palette().color(QPalette.ColorRole.Text).name().upper() == INK.upper()
        combo.deleteLater()

    def test_qss_styles_combo_line_edit_and_tooltips(self, qapp):
        from hosts.DesktopHostPySide.widgets.design_system import APP_STYLESHEET

        assert "QComboBox QLineEdit" in APP_STYLESHEET
        assert "QToolTip" in APP_STYLESHEET


class TestTooltipSuppressionRetired:
    def test_main_applies_light_theme_and_drops_suppressor(self):
        source = (_HOST_DIR / "main.py").read_text(encoding="utf-8")
        assert "apply_light_theme(app)" in source
        assert "install_tooltip_suppression" not in source

    def test_main_window_no_longer_installs_suppressor(self):
        source = (_HOST_DIR / "main_window.py").read_text(encoding="utf-8")
        assert "install_tooltip_suppression" not in source

    def test_foco_rail_tooltips_reach_the_user(self, qapp):
        # El rail define tooltips; sin el supresor global instalado por la app,
        # el evento ToolTip ya no se traga. (El supresor solo actúa si alguien
        # lo instala explícitamente.)
        suppressor = getattr(qapp, "_dendro_tooltip_suppressor", None)
        assert suppressor is None

        from PySide6.QtWidgets import QPushButton

        from hosts.DesktopHostPySide.widgets.foco.foco_tool_rail import FocoToolRail

        rail = FocoToolRail()
        tips = [b.toolTip() for b in rail.findChildren(QPushButton)]
        assert tips and all(tips), "todas las herramientas del rail llevan tooltip"
        rail.deleteLater()
