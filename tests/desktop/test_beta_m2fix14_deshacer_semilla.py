"""BETA2-FIX-14 (G2-22): aceptar una semilla no dejaba punto de deshacer.

`CandidateController` era la ÚNICA clase de controlador que no heredaba de
`MutationNotifier`. La cadena rota, en orden: sin `on_mutated` → sin `_dirty` → sin
autoguardado → sin `_record_undo_snapshot` (el único llamador de la pila de deshacer)
→ `UndoHistory.can_undo()` False. Una escritora lo midió: «Aceptar tardó 0,04 s;
arrepentirme, infinito».

Efecto colateral verificado y peor: los candidatos que estadía un job de IA ya pagado
(`_auto_stage_and_notify` → `controller.create`) vivían solo en RAM hasta que otra cosa
guardase — un fallo del proceso se llevaba por delante una llamada facturada (GUI-19).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402
from hosts.DesktopHostPySide.controllers.mutation_hook import MutationNotifier  # noqa: E402
from hosts.DesktopHostPySide.main_window import MainWindow  # noqa: E402
from packages.application.candidate_service import CandidateService  # noqa: E402
from packages.application.entity_service import EntityService  # noqa: E402
from packages.application.project_service import ProjectService  # noqa: E402
from packages.application.relation_service import RelationService  # noqa: E402
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


def _fixture_project(path, *, candidatos=1):
    """Proyecto EN DISCO con una entidad y N candidatos pendientes."""
    svc = ProjectService()
    assert isinstance(svc.create(name="Mundo con semillas"), Ok)
    svc.active_project.entities.append(NarrativeEntity(name="Rosa"))
    cs = CandidateService(
        project_service=svc,
        entity_service=EntityService(svc),
        relation_service=RelationService(svc),
    )
    ids = []
    for n in range(candidatos):
        res = cs.create_candidate(
            {
                "title": f"Semilla {n}",
                "candidate_type": "entidad",
                "proposed_data": {"name": f"Brote {n}", "entity_type": "personaje"},
            }
        )
        assert isinstance(res, Ok), res
        ids.append(res.value.id)
    assert isinstance(svc.save(path), Ok)
    return ids


def _window(path):
    w = MainWindow()
    w._open_project_path(str(path))
    return w


def _close(w, app):
    w.controller.close()
    w.close()
    w.deleteLater()
    app.processEvents()


def _reread(path):
    svc = ProjectService()
    assert isinstance(svc.open(path), Ok)
    return svc.active_project


def test_beta_m2fix14_el_controlador_de_candidatos_avisa_de_sus_mutaciones():
    """La raíz: era la única clase de controlador que no heredaba el aviso."""
    from hosts.DesktopHostPySide.controllers.candidate_controller import CandidateController

    assert issubclass(CandidateController, MutationNotifier)


def test_beta_m2fix14_aceptar_semilla_marca_sucio_y_registra_instantanea(app, tmp_path):
    path = tmp_path / "s.json"
    (cid,) = _fixture_project(path)
    w = _window(path)
    try:
        assert w._dirty is False
        assert isinstance(w.cc.accept(cid), Ok)
        assert w._dirty is True, "aceptar una semilla no marcaba el proyecto sucio"
        assert w._flush_autosave() is True
        assert w._undo_history.can_undo() is True, (
            "sin instantánea Ctrl+Z no llega: es lo que midió la tester (can_undo=False)"
        )
        # Y llegó al disco sin que el usuario haga nada más.
        assert "Brote 0" in {e.name for e in _reread(path).entities}
    finally:
        _close(w, app)


def test_beta_m2fix14_ctrl_z_revierte_la_aceptacion(app, tmp_path):
    path = tmp_path / "u.json"
    (cid,) = _fixture_project(path)
    w = _window(path)
    try:
        antes = len(w.controller.ps.active_project.entities)
        assert isinstance(w.cc.accept(cid), Ok)
        w._flush_autosave()
        assert len(w.controller.ps.active_project.entities) == antes + 1

        w._undo()

        proyecto = w.controller.ps.active_project
        assert len(proyecto.entities) == antes, "deshacer no retiró la entidad florecida"
        pendientes = [
            c for c in proyecto.candidates if str(getattr(c.state, "value", c.state)) == "pendiente"
        ]
        assert [c.id for c in pendientes] == [cid], "la semilla debe volver a pendiente"
    finally:
        _close(w, app)


def test_beta_m2fix14_estadiar_candidatos_de_un_job_persiste(app, tmp_path):
    """Una llamada de IA ya pagada no puede vivir solo en RAM (GUI-19)."""
    path = tmp_path / "j.json"
    _fixture_project(path, candidatos=0)
    w = _window(path)
    try:
        workspace = w.creation_workspace
        assert w._dirty is False

        class _Job:
            id = "job-de-prueba"
            message = ""
            result = {
                "candidates": [
                    {
                        "title": "Semilla A",
                        "candidate_type": "entidad",
                        "proposed_data": {"name": "Aitor", "entity_type": "personaje"},
                    },
                    {
                        "title": "Semilla B",
                        "candidate_type": "entidad",
                        "proposed_data": {"name": "Vera", "entity_type": "personaje"},
                    },
                ]
            }

        creados = workspace._auto_stage_and_notify(_Job())
        assert len(creados) == 2
        assert w._dirty is True, "el resultado de un job de IA vivía solo en RAM"
        w._flush_autosave()
        titulos = {c.title for c in _reread(path).candidates}
        assert {"Semilla A", "Semilla B"} <= titulos
    finally:
        _close(w, app)


def test_beta_m2fix14_rechazar_tambien_marca_sucio(app, tmp_path):
    path = tmp_path / "r.json"
    (cid,) = _fixture_project(path)
    w = _window(path)
    try:
        assert isinstance(w.cc.reject(cid), Ok)
        assert w._dirty is True, "rechazar también es una decisión que hay que persistir"
        w._flush_autosave()
        estados = {
            c.id: str(getattr(c.state, "value", c.state)) for c in _reread(path).candidates
        }
        assert estados[cid] == "rechazado"
    finally:
        _close(w, app)


def test_beta_m2fix14_los_dialogos_de_borrado_no_prometen_irreversibilidad():
    """Los tres decían «Esta acción no se puede deshacer» — y Ctrl+Z la deshacía."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    for relativo in (
        "hosts/DesktopHostPySide/views/workspaces.py",
        "hosts/DesktopHostPySide/widgets/graph_canvas.py",
    ):
        texto = (raiz / relativo).read_text(encoding="utf-8")
        assert "no se puede deshacer" not in texto, f"{relativo} sigue mintiendo"

    from hosts.DesktopHostPySide.widgets.design_system import AVISO_DESHACER_BORRADO

    assert "Ctrl+Z" in AVISO_DESHACER_BORRADO
    # El resto del microcopy (qué se lleva por delante) se conserva palabra por
    # palabra: dos testers lo señalaron como el mejor del producto.
    workspaces = (raiz / "hosts/DesktopHostPySide/views/workspaces.py").read_text(
        encoding="utf-8"
    )
    assert "Se quitarán también sus relaciones." in workspaces


def test_beta_m2fix14_ctrl_z_inmediato_no_cae_en_nada_que_deshacer(app, tmp_path):
    """El diálogo promete Ctrl+Z: tiene que valer también dentro de los 1.500 ms."""
    path = tmp_path / "i.json"
    (cid,) = _fixture_project(path)
    w = _window(path)
    try:
        antes = len(w.controller.ps.active_project.entities)
        assert isinstance(w.cc.accept(cid), Ok)
        # SIN esperar al antirrebote: es la ventana en la que la promesa fallaba.
        assert w._autosave_timer.isActive()

        w._undo()

        assert len(w.controller.ps.active_project.entities) == antes
    finally:
        _close(w, app)


def test_beta_m2fix14_sin_ruta_de_proyecto_tambien_hay_deshacer(app, tmp_path):
    """La promesa del diálogo tiene que ser verdad en un proyecto aún sin guardar."""
    w = MainWindow()
    try:
        assert isinstance(w.controller.ps.create(name="Sin ruta"), Ok)
        w.controller.current_path = ""
        w.reset_undo_history()
        w._undo_project_id = getattr(w.controller.ps.active_project, "id", None)
        assert isinstance(w.ec.create({"name": "Efímera", "entity_type": "personaje"}), Ok)
        w._flush_autosave()  # no escribe (no hay ruta) pero SÍ registra instantánea
        assert w._undo_history.can_undo() is True
        w._undo()
        assert [e.name for e in w.controller.ps.active_project.entities] == []
    finally:
        _close(w, app)
