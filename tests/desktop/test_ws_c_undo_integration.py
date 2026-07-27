"""BETA-CIERRE WS-C: deshacer/rehacer end-to-end sobre MainWindow.

Verifica el ciclo real: cargar (fija la base) → mutar + autoguardar (registra) →
Ctrl+Z restaura el estado anterior → Ctrl+Y lo reaplica. La restauración usa el
mismo ida-y-vuelta que la persistencia (Project.to_dict/from_dict).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402
from hosts.DesktopHostPySide.main_window import MainWindow  # noqa: E402
from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _isolated_and_nonmodal(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")
    yes = QMessageBox.StandardButton.Yes
    for name in ("question", "warning", "information", "critical", "about"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: yes))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)


def _fixture_project(path) -> None:
    svc = ProjectService()
    assert isinstance(svc.create(name="Mundo undo"), Ok)
    svc.active_project.entities.append(NarrativeEntity(name="Héroe"))
    assert isinstance(svc.save(path), Ok)


def _names(w):
    return {e.name for e in w.controller.ps.active_project.entities}


def test_undo_redo_round_trip(app, tmp_path):
    path = tmp_path / "u.json"
    _fixture_project(path)
    w = MainWindow()
    try:
        w._open_project_path(str(path))  # base del historial = estado cargado
        assert _names(w) == {"Héroe"}
        assert not w._undo_history.can_undo()

        # Mutación + autoguardado asentado → registra el nuevo estado.
        w.controller.ps.active_project.entities.append(NarrativeEntity(name="Villano"))
        assert w._save_active_project_silent() is True
        assert _names(w) == {"Héroe", "Villano"}
        assert w._undo_history.can_undo()

        # Ctrl+Z → vuelve al estado cargado (Villano desaparece).
        w._undo()
        assert _names(w) == {"Héroe"}
        assert w._undo_history.can_redo()

        # Ctrl+Y → reaplica.
        w._redo()
        assert _names(w) == {"Héroe", "Villano"}

        # La restauración persistió: reabrir el fichero da el estado rehecho.
        reopened = ProjectService()
        assert isinstance(reopened.open(path), Ok)
        assert {e.name for e in reopened.active_project.entities} == {"Héroe", "Villano"}
    finally:
        w.controller.close()
        w.close()
        w.deleteLater()
        app.processEvents()


def test_delete_cascade_is_reversible(app, tmp_path):
    # Un borrado que cascada (entidad + su relación) se revierte ENTERO por
    # snapshot — el punto débil de un undo por-comando.
    from packages.domain.relation import NarrativeRelation

    path = tmp_path / "c.json"
    svc = ProjectService()
    assert isinstance(svc.create(name="Cascada"), Ok)
    a = NarrativeEntity(name="A")
    b = NarrativeEntity(name="B")
    svc.active_project.entities.extend([a, b])
    svc.active_project.relations.append(
        NarrativeRelation(source_id=a.id, target_id=b.id)  # tipo por defecto
    )
    assert isinstance(svc.save(path), Ok)

    w = MainWindow()
    try:
        w._open_project_path(str(path))
        proj = w.controller.ps.active_project
        assert len(proj.relations) == 1
        # Borra A + su relación (cascada) y asienta.
        proj.entities = [e for e in proj.entities if e.name != "A"]
        proj.relations = []
        assert w._save_active_project_silent() is True
        assert len(w.controller.ps.active_project.entities) == 1
        # Ctrl+Z restaura A y la relación juntas.
        w._undo()
        restored = w.controller.ps.active_project
        assert {e.name for e in restored.entities} == {"A", "B"}
        assert len(restored.relations) == 1
    finally:
        w.controller.close()
        w.close()
        w.deleteLater()
        app.processEvents()
