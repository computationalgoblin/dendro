"""BETA2-UI2-10: búsqueda con Ctrl+B en Mapa/Cronología y "Crear era…".

- La tecla 'd' y toda la cadena ``searchRequested`` desaparecieron del lienzo;
  la barra flotante unificada se abre con Ctrl+B (mismo atajo que la paleta
  del Foco), con QShortcuts anclados a graph/chrono — nunca al workspace
  (FocoView es hijo y ya tiene el suyo: dos matches serían ambiguos).
- El panel de búsqueda del drawer y el panel de filtros del drawer se
  retiraron (botones incluidos).
- La Cronología ofrece "Crear era…" en su menú contextual (señal
  ``eraCreateRequested`` cableada a ``_open_era_create_panel``).

Cableado verificado con pins de fuente (patrón de la casa) + señales reales.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

_GRAPH = Path("hosts/DesktopHostPySide/widgets/graph_canvas.py")
_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")
_CHRONO = Path("hosts/DesktopHostPySide/widgets/chrono_canvas.py")
_FOCO = Path("hosts/DesktopHostPySide/widgets/foco/foco_view.py")


class TestSearchShortcut:
    def test_key_d_chain_removed_from_canvas(self):
        source = _GRAPH.read_text(encoding="utf-8")
        assert "Key_D:" not in source  # el bloque `if key == Qt.Key.Key_D:` murió
        assert "searchRequested" not in source

    def test_ctrl_b_shortcuts_anchored_to_graph_and_chrono(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "for host in (self.graph, self.chrono):" in source
        assert 'QShortcut(QKeySequence("Ctrl+B"), host)' in source
        assert "Qt.ShortcutContext.WidgetWithChildrenShortcut" in source
        assert "shortcut.activated.connect(self._open_search_overlay)" in source
        # NUNCA en el workspace entero: colisionaría con el Ctrl+B del Foco.
        assert 'QShortcut(QKeySequence("Ctrl+B"), self)' not in source

    def test_foco_keeps_its_own_ctrl_b(self):
        source = _FOCO.read_text(encoding="utf-8")
        assert 'QKeySequence("Ctrl+B")' in source

    def test_drawer_search_and_filter_panels_removed(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "class CreationSearchPanel" not in source
        assert "class CreationFilterPanel" not in source
        assert "def _open_search_panel" not in source
        assert "def _open_filter_panel" not in source
        assert "_build_float_cluster" not in source  # el cluster izquierdo murió
        assert "_float_left" not in source
        # La barra flotante unificada sigue viva (Ctrl+B la abre).
        assert "class _FloatingSearchBar" in source
        assert "def _open_search_overlay" in source


class TestCreateEraFromChrono:
    def test_signal_exists_and_menu_offers_create_era(self):
        source = _CHRONO.read_text(encoding="utf-8")
        assert "eraCreateRequested = Signal()" in source
        assert 'menu.addAction("Crear era…")' in source

    def test_view_emits_era_create_requested(self):
        QApplication.instance() or QApplication([])
        from hosts.DesktopHostPySide.widgets.chrono_canvas import ChronoCanvasView

        view = ChronoCanvasView()
        received = []
        view.eraCreateRequested.connect(lambda: received.append(True))
        view.eraCreateRequested.emit()
        assert received == [True]
        view.deleteLater()

    def test_workspace_wires_create_era(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "self.chrono.eraCreateRequested.connect(self._open_era_create_panel)" in source
