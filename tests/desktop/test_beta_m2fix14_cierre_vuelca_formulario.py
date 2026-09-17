"""BETA2-FIX-14 (G2-23): cerrar dentro de los 800 ms perdía la frase.

Los formularios de detalle tienen su PROPIO antirrebote de 800 ms. `closeEvent`
paraba solo el suyo (el de la ventana) y llamaba a `_save_active_project()`, que
persiste el modelo tal como está EN MEMORIA: la edición del formulario todavía no
se le había aplicado. Una carrera de 800 ms que el usuario no sabe que corre —
midió tres casos y el «cierro rápido» perdía la frase aunque respondiera «Guardar».

Además `foco_view._flush_form_autosave` solo mira `self._form_panel`: el panel de
hito (con su propio temporizador de 800 ms) no lo volcaba NADIE, nunca.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402
from hosts.DesktopHostPySide.main_window import MainWindow  # noqa: E402
from hosts.DesktopHostPySide.widgets.milestone_detail_panel import (  # noqa: E402
    MilestoneDetailPanel,
)
from hosts.DesktopHostPySide.widgets.node_detail_panel import NodeDetailPanel  # noqa: E402
from packages.application.project_service import ProjectService  # noqa: E402
from packages.domain.causal_milestone import CausalMilestone  # noqa: E402
from packages.domain.entity import NarrativeEntity  # noqa: E402
from packages.domain.result import Ok  # noqa: E402

_FRASE = "La pigmentera guardó el añil bajo el suelo."


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)


def _answer(monkeypatch, button):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: button))
    for name in ("warning", "information", "critical", "about"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: button))


def _fixture_project(path):
    svc = ProjectService()
    assert isinstance(svc.create(name="Mundo que se cierra"), Ok)
    entidad = NarrativeEntity(name="Rosa")
    svc.active_project.entities.append(entidad)
    hito = CausalMilestone(title="La Guerra de los Tintes", year=1492)
    svc.active_project.causal_milestones.append(hito)
    assert isinstance(svc.save(path), Ok)
    return entidad.id, hito.id


def _reread(path):
    svc = ProjectService()
    assert isinstance(svc.open(path), Ok)
    return svc.active_project


def _window(path):
    w = MainWindow()
    w._open_project_path(str(path))
    return w


def _close(w, app):
    try:
        w.controller.close()
    except Exception:  # noqa: BLE001 — el proyecto pudo cerrarse ya
        pass
    w.close()
    w.deleteLater()
    app.processEvents()


def _montar_ficha(w, entity_id):
    """Formulario REAL de entidad, colgado de la ventana (como el editor de Foco)."""
    panel = NodeDetailPanel(
        w.ctx,
        w.ec,
        entity_id,
        relation_controller=w.rc,
        variant="foco",
    )
    panel.setParent(w)
    return panel


def test_beta_m2fix14_close_event_vuelca_el_autoguardado_del_formulario(
    app, tmp_path, monkeypatch
):
    """Caso A de la tester: escribir y cerrar en <800 ms respondiendo «Guardar»."""
    path = tmp_path / "a.json"
    eid, _ = _fixture_project(path)
    w = _window(path)
    try:
        panel = _montar_ficha(w, eid)
        panel.brief_edit.setPlainText(_FRASE)
        assert panel._autosave_timer.isActive(), "el antirrebote de 800 ms debe estar armado"

        _answer(monkeypatch, QMessageBox.StandardButton.Save)
        evento = QCloseEvent()
        w.closeEvent(evento)

        assert evento.isAccepted()
        entidad = next(e for e in _reread(path).entities if e.id == eid)
        assert entidad.brief_description == _FRASE, (
            "cerrar dentro de los 800 ms seguía perdiendo lo último escrito"
        )
    finally:
        _close(w, app)


def test_beta_m2fix14_close_event_con_descartar_no_guarda(app, tmp_path, monkeypatch):
    """Caso C (control): «Descartar» tiene que seguir descartando."""
    path = tmp_path / "c.json"
    eid, _ = _fixture_project(path)
    w = _window(path)
    try:
        panel = _montar_ficha(w, eid)
        panel.brief_edit.setPlainText(_FRASE)

        _answer(monkeypatch, QMessageBox.StandardButton.Discard)
        w.closeEvent(QCloseEvent())

        entidad = next(e for e in _reread(path).entities if e.id == eid)
        assert entidad.brief_description != _FRASE, "«Descartar» no puede escribir a disco"
    finally:
        _close(w, app)


def test_beta_m2fix14_close_event_vuelca_tambien_el_panel_de_hito(app, tmp_path, monkeypatch):
    """El temporizador de 800 ms del panel de hito no lo volcaba NADIE, nunca."""
    path = tmp_path / "h.json"
    _, hid = _fixture_project(path)
    w = _window(path)
    try:
        workspace = w.creation_workspace
        controller = workspace._milestone_ctrl
        assert controller is not None
        panel = MilestoneDetailPanel(w.ctx, controller, hid, entity_controller=w.ec)
        panel.setParent(w)
        panel.summary_edit.setPlainText(_FRASE)
        assert panel._autosave_timer.isActive()

        _answer(monkeypatch, QMessageBox.StandardButton.Save)
        w.closeEvent(QCloseEvent())

        hito = next(h for h in _reread(path).causal_milestones if h.id == hid)
        assert hito.description == _FRASE
    finally:
        _close(w, app)


def test_beta_m2fix14_close_event_sin_proyecto_sigue_saliendo_sin_dialogo(
    app, tmp_path, monkeypatch
):
    """No romper i78: sin proyecto activo se sale sin preguntar nada."""
    preguntas = {"n": 0}

    def _contar(*a, **k):
        preguntas["n"] += 1
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "question", staticmethod(_contar))
    w = MainWindow()
    try:
        assert w._get_active_project() is None
        evento = QCloseEvent()
        w.closeEvent(evento)
        assert evento.isAccepted()
        assert preguntas["n"] == 0, "sin proyecto no puede haber diálogo de guardado"
    finally:
        _close(w, app)


def test_beta_m2fix14_el_barrido_es_generico_y_cuenta_lo_que_vuelca(app, tmp_path):
    """El barrido cubre CUALQUIER panel con antirrebote, no solo el de Foco."""
    path = tmp_path / "g.json"
    eid, hid = _fixture_project(path)
    w = _window(path)
    try:
        ficha = _montar_ficha(w, eid)
        hito_panel = MilestoneDetailPanel(
            w.ctx, w.creation_workspace._milestone_ctrl, hid, entity_controller=w.ec
        )
        hito_panel.setParent(w)
        ficha.brief_edit.setPlainText(_FRASE)
        hito_panel.summary_edit.setPlainText(_FRASE)

        volcados = w._flush_pending_form_autosaves()

        assert volcados == 2, "los dos formularios pendientes deben volcarse"
        assert not ficha._autosave_timer.isActive()
        assert not hito_panel._autosave_timer.isActive()
        # Idempotente: sin temporizadores armados no vuelca nada.
        assert w._flush_pending_form_autosaves() == 0
    finally:
        _close(w, app)


def test_beta_m2fix14_el_volcado_va_antes_de_preguntar(app, tmp_path, monkeypatch):
    """Si se vuelca DESPUÉS de preguntar, el diálogo miente sobre lo que hay en disco."""
    path = tmp_path / "o.json"
    eid, _ = _fixture_project(path)
    w = _window(path)
    orden: list[str] = []
    try:
        panel = _montar_ficha(w, eid)
        panel.brief_edit.setPlainText(_FRASE)

        original = w.ec.update

        def _espia(*a, **k):
            orden.append("volcado")
            return original(*a, **k)

        monkeypatch.setattr(w.ec, "update", _espia)

        def _pregunta(*a, **k):
            orden.append("dialogo")
            return QMessageBox.StandardButton.Discard

        monkeypatch.setattr(QMessageBox, "question", staticmethod(_pregunta))
        w.closeEvent(QCloseEvent())

        assert orden[:2] == ["volcado", "dialogo"], orden
    finally:
        _close(w, app)


def test_beta_m2fix14_qcloseevent_es_el_tipo_correcto():
    """Guardarraíl del propio test: `QCloseEvent` es un evento de cierre real."""
    assert QCloseEvent().type() == QEvent.Type.Close
