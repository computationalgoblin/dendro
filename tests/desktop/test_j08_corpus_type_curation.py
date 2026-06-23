"""BETA1-J08 — el inspector del corpus ofrece tipos curados SIN perder el tipo
actual de entidades de tipo oculto (data-safety).

El combo del inspector no es editable; si la entidad tiene un tipo oculto
(evento, nota, legacy…) y el combo solo ofreciera los curados, al guardar se
reescribiría al primer tipo curado. El inspector debe SIEMPRE incluir el tipo
actual aunque esté oculto.
"""
from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")

if HAS_QT:
    from PySide6.QtWidgets import QApplication

    from hosts.DesktopHostPySide.app_context import AppContext
    from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
    from hosts.DesktopHostPySide.views.corpus_view import CorpusView
    from packages.application.project_service import ProjectService
    from packages.domain.entity_taxonomy import OFFERED_ENTITY_TYPES
    from packages.domain.result import Ok


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _view():
    ps = ProjectService()
    assert isinstance(ps.create("J08-CORPUS"), Ok)
    ctx = AppContext()
    ctx.set_advanced_mode(False)
    ctx.project_controller = SimpleNamespace(ps=ps)
    ctx.drawer = None
    ec = EntityController(ps)
    return CorpusView(ctx, ec), ec


def _type_options(view, entity):
    fields = {f["name"]: f for f in view._entity_fields(entity)}
    return fields["entity_type"]["options"]


def test_curated_type_for_normal_entity(qapp):
    view, ec = _view()
    p = ec.create({"name": "P", "entity_type": "personaje"}).value
    opts = _type_options(view, p)
    assert opts == [t.value for t in OFFERED_ENTITY_TYPES]
    assert "nota" not in opts and "evento" not in opts


def test_hidden_current_type_is_preserved(qapp):
    # Una entidad de tipo oculto conserva su tipo en el inspector (no se pierde).
    view, ec = _view()
    nota = ec.create({"name": "Vieja", "entity_type": "nota"}).value
    opts = _type_options(view, nota)
    assert "nota" in opts  # preservado
    assert opts[0] == "nota"  # como valor actual, queda seleccionable
    # y además ofrece los curados
    assert "personaje" in opts
