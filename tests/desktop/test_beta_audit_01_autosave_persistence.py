"""BETA-AUDIT-01: el autoguardado del formulario debe llegar al DISCO.

Antes de este ticket, editar una ficha solo mutaba el ``Project`` en memoria:
``EntityService.update_entity`` termina en ``Ok(found)`` sin llamar a ``store.save``,
y nada en la ruta del formulario disparaba ``request_save_silent``. Una caida del
proceso (sin cerrar la ventana, que si guarda por dialogo) perdia la sesion entera.

Estos tests cierran esa via: mutan por CONTROLADOR (la ruta comun de todas las
superficies de edicion, no solo de los tres formularios), asientan el guardado
diferido y releen el fichero desde disco con un ProjectService limpio.
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
from packages.domain.relation import NarrativeRelation  # noqa: E402
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


def _fixture_project(path):
    """Proyecto en disco con una entidad y una relacion. Devuelve (eid, rid)."""
    svc = ProjectService()
    assert isinstance(svc.create(name="Mundo autosave"), Ok)
    a = NarrativeEntity(name="Heroe")
    b = NarrativeEntity(name="Villano")
    svc.active_project.entities.extend([a, b])
    rel = NarrativeRelation(source_id=a.id, target_id=b.id)
    svc.active_project.relations.append(rel)
    assert isinstance(svc.save(path), Ok)
    return a.id, rel.id


def _reread(path):
    """Relee el proyecto DESDE DISCO con un servicio limpio (sin compartir memoria)."""
    svc = ProjectService()
    assert isinstance(svc.open(path), Ok)
    return svc.active_project


def _window(path):
    w = MainWindow()
    w._open_project_path(str(path))
    return w


def _close(w, app):
    w.controller.close()
    w.close()
    w.deleteLater()
    app.processEvents()


def test_entity_edit_reaches_disk_without_explicit_save(app, tmp_path):
    path = tmp_path / "e.json"
    eid, _ = _fixture_project(path)
    w = _window(path)
    try:
        assert isinstance(w.ec.update(eid, {"name": "Heroe editado"}), Ok)
        # Nadie pulsa Guardar ni cierra la ventana: solo se asienta el diferido.
        w._flush_autosave()
        assert {e.name for e in _reread(path).entities} == {"Heroe editado", "Villano"}
    finally:
        _close(w, app)


def test_relation_edit_reaches_disk(app, tmp_path):
    path = tmp_path / "r.json"
    _, rid = _fixture_project(path)
    w = _window(path)
    try:
        assert isinstance(w.rc.update(rid, {"description": "vinculo probado"}), Ok)
        w._flush_autosave()
        rel = _reread(path).relations[0]
        assert getattr(rel, "description", "") == "vinculo probado"
    finally:
        _close(w, app)


def test_entity_delete_reaches_disk(app, tmp_path):
    """No solo los formularios: cualquier mutacion por controlador persiste."""
    path = tmp_path / "d.json"
    eid, _ = _fixture_project(path)
    w = _window(path)
    try:
        w.ec.delete(eid)
        w._flush_autosave()
        assert {e.name for e in _reread(path).entities} == {"Villano"}
    finally:
        _close(w, app)


def test_burst_of_edits_coalesces_into_one_disk_write(app, tmp_path):
    """Una rafaga de teclas no puede producir una escritura por tecla."""
    path = tmp_path / "b.json"
    eid, _ = _fixture_project(path)
    w = _window(path)
    try:
        saves = {"n": 0}
        original = w.controller.save

        def counting_save(*a, **k):
            saves["n"] += 1
            return original(*a, **k)

        w.controller.save = counting_save
        for i in range(12):
            assert isinstance(w.ec.update(eid, {"name": f"Heroe {i}"}), Ok)
        assert saves["n"] == 0, "el guardado debe ser diferido, no por pulsacion"
        w._flush_autosave()
        assert saves["n"] == 1, "la rafaga debe coalescer en UN solo guardado"
        assert {e.name for e in _reread(path).entities} == {"Heroe 11", "Villano"}
    finally:
        _close(w, app)


def test_edit_registers_an_undo_point(app, tmp_path):
    """Efecto colateral del ticket: editar texto genera punto de deshacer."""
    path = tmp_path / "u.json"
    eid, _ = _fixture_project(path)
    w = _window(path)
    try:
        assert not w._undo_history.can_undo()
        assert isinstance(w.ec.update(eid, {"name": "Heroe con historia"}), Ok)
        w._flush_autosave()
        assert w._undo_history.can_undo(), "el guardado asentado debe registrar snapshot"
        w._undo()
        assert {e.name for e in w.controller.ps.active_project.entities} == {
            "Heroe",
            "Villano",
        }
    finally:
        _close(w, app)


def test_ctrl_s_saves_the_active_project(app, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    path = tmp_path / "s.json"
    eid, _ = _fixture_project(path)
    w = _window(path)
    try:
        assert isinstance(w.ec.update(eid, {"name": "Guardado a mano"}), Ok)
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier
        )
        w.keyPressEvent(event)
        assert event.isAccepted(), "Ctrl+S debe consumirse en MainWindow"
        assert {e.name for e in _reread(path).entities} == {"Guardado a mano", "Villano"}
    finally:
        _close(w, app)


def test_ctrl_z_still_works_after_adding_ctrl_s(app, tmp_path):
    """No regresion: Ctrl+S no puede robarle el evento a Ctrl+Z / Ctrl+Y."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    path = tmp_path / "z.json"
    eid, _ = _fixture_project(path)
    w = _window(path)
    try:
        assert isinstance(w.ec.update(eid, {"name": "Antes de deshacer"}), Ok)
        w._flush_autosave()
        undo = QKeyEvent(
            QKeyEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
        )
        w.keyPressEvent(undo)
        assert undo.isAccepted()
        assert {e.name for e in w.controller.ps.active_project.entities} == {
            "Heroe",
            "Villano",
        }
    finally:
        _close(w, app)


def test_no_disk_write_without_active_project(app, tmp_path):
    """Sin proyecto activo el diferido no debe explotar ni escribir nada."""
    w = MainWindow()
    try:
        w._schedule_silent_save()
        assert w._flush_autosave() is True  # no-op seguro
    finally:
        _close(w, app)
