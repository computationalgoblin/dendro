"""BETA-CIERRE WS-H / B6: smoke e2e headless del runtime desktop.

Arranca `MainWindow` (con preferencias AISLADAS para no auto-cargar el proyecto real del
dev y con los diálogos modales neutralizados), abre por la vía REAL de MainWindow un
proyecto-fixture creado en disco, navega a Creación y comprueba que el proyecto viajó a
las vistas. Cubre el cableado MainWindow→controllers→services→views que los tests de
widget aislados no ejercitan y que estaba SIN cobertura (toda épica en «pend. smoke
usuario»). Es la puerta automatizada que sustituye a la auditoría manual de 14 superficies.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402
from hosts.DesktopHostPySide.main_window import _IDX_CREATION, MainWindow  # noqa: E402
from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _isolated_and_nonmodal(tmp_path, monkeypatch):
    # Prefs en fichero temporal vacío → sin auto-carga del proyecto real del dev.
    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")
    # Neutraliza los diálogos modales (guardar-al-cerrar, avisos): offscreen bloquearían.
    yes = QMessageBox.StandardButton.Yes
    for name in ("question", "warning", "information", "critical", "about"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: yes))
    # exec() de una instancia de QMessageBox (p.ej. el diálogo Acerca de) bloquearía.
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)


def _fixture_project(path) -> None:
    """Crea un proyecto-fixture en disco con una entidad (servicio aparte del window)."""
    svc = ProjectService()
    assert isinstance(svc.create(name="Mundo e2e"), Ok)
    svc.active_project.entities.append(NarrativeEntity(name="Héroe"))
    assert isinstance(svc.save(path), Ok)


def test_e2e_boot_open_navigate(app, tmp_path):
    path = tmp_path / "mundo.json"
    _fixture_project(path)

    w = MainWindow()
    try:
        # 1) Arrancó todo el shell en Home, sin proyecto (prefs aisladas).
        assert w.windowTitle() == "Dendro"
        assert w.ctx.last_project_path == ""
        assert hasattr(w, "creation_workspace")
        assert w.controller.ps.active_project is None

        # 2) Abre el proyecto por la vía real de MainWindow (empuja a todas las vistas).
        w._open_project_path(str(path))
        loaded = w.controller.ps.active_project
        assert loaded is not None
        assert loaded.name == "Mundo e2e"
        assert any(e.name == "Héroe" for e in loaded.entities)

        # 3) Con proyecto cargado, la navegación a Creación entra (sin proyecto se bloquea).
        w._go_space(_IDX_CREATION)
        assert w.stack.currentIndex() == _IDX_CREATION

        # 4) El diálogo "Acerca de" (con acceso a registros, WS-O) se abre sin romper.
        w._open_about_dialog()

        # 5) WS-D: el proyecto de ejemplo tiene puerta en Home y se abre.
        assert w._bundled_sample_path() is not None
        assert not w.home_view._btn_sample.isHidden()
        # WS-D: la copia-al-abrir va a una carpeta escribible; en el test la
        # aislamos a tmp_path (no ensuciar ~/Dendro del dev).
        w._sample_workspace_dir = lambda: tmp_path / "sample_ws"
        w._open_sample_project()
        sample_proj = w.controller.ps.active_project
        assert sample_proj is not None and "Almendros" in (sample_proj.name or "")
        # Se abrió la COPIA escribible, no el original de solo-lectura.
        assert str(tmp_path / "sample_ws") in (w.controller.current_path or "")
    finally:
        w.controller.close()  # sin proyecto activo → closeEvent no abre modal
        w.close()
        w.deleteLater()
        app.processEvents()
