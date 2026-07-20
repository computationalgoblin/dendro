"""FOCO-28: glifo rama/hoja, píldoras de modo en el banner y Tab entre modos.

El glifo se valida por render real; la lógica de nivel-workspace (eventFilter de
Tab, reparent de las píldoras al banner) se valida por comprobación de FUENTE
—patrón de la casa: CreationWorkspace no se instancia sin AppContext (ver
test_foco_seeds_zones)—.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")
_MAIN_WINDOW = Path("hosts/DesktopHostPySide/main_window.py")
_CHRONO = Path("hosts/DesktopHostPySide/widgets/chrono_canvas.py")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


class TestEntityGlyph:
    def test_branch_vs_leaf_glyph_name(self, qapp):
        from hosts.DesktopHostPySide.widgets.icons import entity_glyph_name

        # Rama (taxonomía is_branch): tipos organizativos + contenedor.
        for kind in (
            "faccion",
            "cultura",
            "religion",
            "institucion",
            "localizacion",
            "contenedor",
        ):
            assert entity_glyph_name(kind) == "entity_branch"
        # Hoja: seres y objetos.
        for kind in ("personaje", "criatura", "objeto", "tecnologia", "idioma"):
            assert entity_glyph_name(kind) == "entity_leaf"
        # Tipo personalizado desconocido ⇒ hoja.
        assert entity_glyph_name("tipo_raro") == "entity_leaf"

    def test_glyph_pixmap_renders(self, qapp):
        from hosts.DesktopHostPySide.widgets.icons import entity_glyph_pixmap

        px = entity_glyph_pixmap("faccion", size=16)
        assert not px.isNull()
        assert px.width() > 0


class TestModePillsInBanner:
    def test_workspace_exposes_toggle_and_no_longer_floats_it(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "def view_toggle_widget(self)" in source
        assert "return self._float_view_toggle" in source
        # Ya no se posiciona flotando el toggle en _position_floats.
        assert "toggle.move((self.width() - toggle.width()) // 2, 14)" not in source

    def test_banner_reparents_the_pills(self):
        source = _MAIN_WINDOW.read_text(encoding="utf-8")
        assert 'hasattr(workspace, "view_toggle_widget")' in source
        assert "nav_layout.addWidget(workspace.view_toggle_widget())" in source


class TestTabCyclesModes:
    def test_eventfilter_cycles_the_three_modes(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "def eventFilter(self, obj, event)" in source
        assert '_MODE_CYCLE = ("foco", "concentric", "chrono")' in source
        assert "Qt.Key.Key_Tab" in source
        assert "Qt.Key.Key_Backtab" in source
        # Filtro de app instalado/retirado con la Creación (los lienzos toman foco).
        assert "app.installEventFilter(self)" in source
        assert "app.removeEventFilter(self)" in source

    def test_chrono_era_cycle_moved_off_tab(self):
        source = _CHRONO.read_text(encoding="utf-8")
        # Las eras pasan a AvPág/RePág; Tab/Shift+Tab quedan para cambiar de modo.
        assert "Qt.Key.Key_PageDown" in source
        assert "Qt.Key.Key_PageUp" in source
        # Ya no se atrapa Tab con focusNextPrevChild.
        assert "def focusNextPrevChild" not in source
