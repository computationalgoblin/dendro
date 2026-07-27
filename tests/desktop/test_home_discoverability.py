"""BETA2-SHIP-02: el primer paso del usuario es descubrible.

Auditoría de lanzamiento 2026-07-21: crear/abrir proyecto y Ajustes vivían tras
iconos sin etiqueta; los recientes se persistían sin mostrarse; el estado vacío
de Foco no ofrecía acción. HomeView se instancia real (solo necesita AppContext);
FocoView y el cableado del workspace se validan por FUENTE (patrón de la casa).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.views.home_view import HomeView

_FOCO = Path("hosts/DesktopHostPySide/widgets/foco/foco_view.py")
_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")
_MAIN_WINDOW = Path("hosts/DesktopHostPySide/main_window.py")


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


def _home(recents=None):
    ctx = AppContext()
    ctx.recent_projects = list(recents or [])
    return HomeView(ctx), ctx


# ── QSS del Home: sin hojas de estilo inválidas (SHIP-07) ────────────────────


def test_home_has_no_invalid_stylesheets(_app):
    """SHIP-07: HomeNode tenía un `}}` literal (línea plain-string dentro de una
    concatenación de f-strings) → Qt descartaba TODA la hoja y la tarjeta perdía
    bordes redondeados y hover. Guarda contra esa clase de fallo en todo el Home."""
    from PySide6.QtCore import qInstallMessageHandler

    warnings: list[str] = []
    prev = qInstallMessageHandler(lambda mode, ctx, msg: warnings.append(msg))
    try:
        _home()
    finally:
        qInstallMessageHandler(prev)
    bad = [w for w in warnings if "parse stylesheet" in w.lower()]
    assert not bad, f"QSS inválido al construir el Home: {bad}"


# ── Botones primarios con etiqueta ───────────────────────────────────────────


def test_primary_buttons_have_labels(_app):
    home, _ = _home()
    assert "Ajustes" in home._btn_config.text()
    assert "proyecto" in home._btn_project.text().lower()


# ── Recientes visibles y funcionales ─────────────────────────────────────────


def test_recents_render_only_existing_paths(_app, tmp_path):
    real = tmp_path / "Mi Mundo.json"
    real.write_text("{}", encoding="utf-8")
    home, _ = _home([str(real), str(tmp_path / "borrado.json")])
    home.refresh_recents()
    texts = [
        home._recents_layout.itemAt(i).widget().text()
        for i in range(home._recents_layout.count())
    ]
    assert any("Mi Mundo" in t for t in texts)
    assert not any("borrado" in t for t in texts)
    assert home._recents_title.isVisibleTo(home)


def test_recents_hidden_when_empty(_app):
    home, _ = _home()
    home.refresh_recents()
    assert home._recents_layout.count() == 0
    assert not home._recents_title.isVisibleTo(home)


def test_recent_click_invokes_open_recent_callback(_app, tmp_path):
    real = tmp_path / "Mi Mundo.json"
    real.write_text("{}", encoding="utf-8")
    home, _ = _home([str(real)])
    home.refresh_recents()
    opened: list[str] = []
    home.register_callback("open_recent", opened.append)
    button = home._recents_layout.itemAt(0).widget()
    assert isinstance(button, QPushButton)
    button.click()
    assert opened == [str(real)]


# ── Foco: el vacío invita a actuar (validación por fuente) ───────────────────


def test_foco_empty_state_has_cta():
    src = _FOCO.read_text(encoding="utf-8")
    assert "createFirstRequested = Signal()" in src
    empty = src.split("self._empty = EmptyState(")[1].split(")")[0]
    assert 'action_text="Crear primera entidad"' in empty
    assert "on_action=self.createFirstRequested.emit" in empty


def test_workspace_wires_foco_cta_to_creation_flow():
    src = _WORKSPACES.read_text(encoding="utf-8")
    assert "self.foco.createFirstRequested.connect(self._create_entity_on_graph)" in src


# ── MainWindow: apertura por ruta cableada ───────────────────────────────────


def test_main_window_wires_open_recent():
    src = _MAIN_WINDOW.read_text(encoding="utf-8")
    assert 'register_callback("open_recent", self._open_project_path)' in src
    # WS-C añadió el kwarg offer_restore; la firma sigue empezando igual.
    assert "def _open_project_path(self, path: str" in src
    # El refresco de recientes repuebla el Home tras abrir/guardar.
    body = src.split("def _refresh_recent_project_option(self)")[1].split("\n    def ")[0]
    assert "self.home_view.refresh_recents()" in body
