"""UX3 · Descubribilidad: el placeholder del input sigue a Acción×Ámbito.

Test ligero: instancia CreationWorkspace sin __init__ (patrón __new__ usado en el
resto de tests desktop) y verifica que `_update_command_placeholder` deriva el texto
de `example_for_command` (fuente única en command_expansion).
"""
from __future__ import annotations

import pytest

from packages.application.ai_jobs import CommandAction, CommandScope
from packages.application.command_expansion import example_for_command

try:
    from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit
    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _combo(value: str) -> QComboBox:
    combo = QComboBox()
    combo.addItem("etiqueta", value)
    combo.setCurrentIndex(0)
    return combo


def _stub(action: CommandAction, scope: CommandScope):
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    ws = CreationWorkspace.__new__(CreationWorkspace)
    ws._command_input = QLineEdit()
    ws._action_selector = _combo(action.value)
    ws._scope_selector = _combo(scope.value)
    return ws


def test_placeholder_follows_action_and_scope(qapp):
    ws = _stub(CommandAction.CREAR, CommandScope.HOJA)
    ws._update_command_placeholder()
    placeholder = ws._command_input.placeholderText()
    assert example_for_command(CommandAction.CREAR, CommandScope.HOJA) in placeholder
    assert "@" in placeholder  # recuerda la sintaxis de menciones


def test_placeholder_changes_with_scope(qapp):
    hoja = _stub(CommandAction.CREAR, CommandScope.HOJA)
    hoja._update_command_placeholder()
    relacion = _stub(CommandAction.CREAR, CommandScope.RELACION)
    relacion._update_command_placeholder()
    assert hoja._command_input.placeholderText() != relacion._command_input.placeholderText()


def test_placeholder_missing_input_is_noop(qapp):
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    ws = CreationWorkspace.__new__(CreationWorkspace)
    ws._command_input = None  # antes de construir la barra
    ws._update_command_placeholder()  # no debe lanzar


# ── UX3: coachmark de 1ª vez + caption del stepper ───────────────────────


def test_coachmark_steps_anchor_to_the_right_widgets(qapp):
    from PySide6.QtWidgets import QLineEdit, QPushButton

    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    ws = CreationWorkspace.__new__(CreationWorkspace)
    ws._action_selector = _combo("crear")
    ws._command_input = QLineEdit()
    ws._command_preview_btn = QPushButton("Vista previa")
    steps = ws._ai_coachmark_steps()
    assert len(steps) == 3
    assert steps[0][0] is ws._action_selector
    assert steps[1][0] is ws._command_input
    assert steps[2][0] is ws._command_preview_btn
    assert all(text.strip() for _, text in steps)


def test_coachmark_is_noop_when_already_shown(qapp):
    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    ws = CreationWorkspace.__new__(CreationWorkspace)
    ws._ai_coachmark_shown = True
    # No debe intentar leer settings ni construir nada (sin AttributeError).
    ws._maybe_show_ai_coachmark()


def test_coachmark_pending_flag_roundtrips(qapp):
    from PySide6.QtCore import QSettings

    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace

    ws = CreationWorkspace.__new__(CreationWorkspace)
    settings = QSettings("Dendro", "DesktopHost")
    previous = settings.value(CreationWorkspace._AI_COACHMARK_KEY)
    try:
        settings.remove(CreationWorkspace._AI_COACHMARK_KEY)
        assert ws._ai_coachmark_pending() is True
        ws._mark_ai_coachmark_seen()
        assert ws._ai_coachmark_pending() is False
    finally:
        if previous is None:
            settings.remove(CreationWorkspace._AI_COACHMARK_KEY)
        else:
            settings.setValue(CreationWorkspace._AI_COACHMARK_KEY, previous)


def test_count_caption_box_toggles_with_visibility(qapp):
    from PySide6.QtWidgets import QWidget

    from hosts.DesktopHostPySide.views.workspaces import CreationWorkspace
    from hosts.DesktopHostPySide.widgets.stepper import BotanicalSpinBox

    ws = CreationWorkspace.__new__(CreationWorkspace)
    ws._action_selector = _combo("crear")
    ws._scope_selector = _combo("hoja")
    ws._count_spin = BotanicalSpinBox()
    ws._count_spin_box = QWidget()  # contenedor con caption (simulado)
    ws._update_count_visibility()
    assert not ws._count_spin_box.isHidden()  # Crear/Hoja → visible
    # Cambiar a una acción que no usa contador → se oculta el contenedor entero.
    ws._action_selector = _combo("analizar")
    ws._update_count_visibility()
    assert ws._count_spin_box.isHidden()
