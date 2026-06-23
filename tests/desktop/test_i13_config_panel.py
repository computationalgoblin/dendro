"""I13 (desktop) — tarjeta + panel de revisión de la configuración propuesta."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.app_context import AppContext  # noqa: E402
from hosts.DesktopHostPySide.views.import_export_view import ImportExportView  # noqa: E402
from hosts.DesktopHostPySide.widgets.import_project_config_panel import (  # noqa: E402
    ImportProjectConfigPanel,
)
from packages.domain.project import Project  # noqa: E402
from packages.domain.result import Ok  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _proposal(applied=False):
    return {
        "chronology": {"mode": "vague_periods", "calendar_name": "Eras", "present_year": 1200,
                       "eras": [{"name": "Antigua", "start_year": 0, "end_year": 800}]},
        "entity_temporal": [{"name": "Eldrin", "birth_year": 900, "nature": "mortal"}],
        "config": {"tone": "épico", "genre": "fantasía",
                   "taxonomy": {"allowed_entity_types": ["personaje"]}},
        "applied": applied,
    }


class _FakeIC:
    def __init__(self, proposal):
        self._proposal = proposal
        self.applied = None
        self.discarded = None
        self.updated = None

    def _basket(self):
        return type("B", (), {"id": "b1", "source_id": "s1", "segments": [],
                              "import_candidates": [], "import_mode": "canon",
                              "metadata": {"project_config_suggestion": self._proposal}})()

    def list_baskets(self):
        return Ok([self._basket()])

    def apply_project_config_suggestion(self, basket_id):
        self.applied = basket_id
        return Ok({"chronology": True})

    def update_project_config_suggestion(self, basket_id, edits):
        self.updated = (basket_id, edits)
        return Ok(self._proposal)

    def discard_project_config_suggestion(self, basket_id):
        self.discarded = basket_id
        return Ok(True)


class _Ctrl:
    def __init__(self, proj):
        self.ps = type("PS", (), {"active_project": proj, "_current_path": Path("/tmp/x.json")})()


def _view(qapp, proposal):
    view = ImportExportView(AppContext(), _Ctrl(Project(name="V")))
    view.ic = _FakeIC(proposal)
    return view


# ── Tarjeta en la vista ───────────────────────────────────────────────────────


def test_has_config_suggestion_respects_applied(qapp):
    view = _view(qapp, _proposal(applied=False))
    basket = view.ic._basket()
    assert view._has_config_suggestion(basket) is True
    view.ic._proposal["applied"] = True
    assert view._has_config_suggestion(basket) is False


def test_config_card_built_with_title(qapp):
    view = _view(qapp, _proposal())
    card = view._make_config_card(view.ic._basket())
    assert "Configuración propuesta" in card.title.text()


def test_refresh_renders_config_card(qapp):
    view = _view(qapp, _proposal())
    view.refresh()
    assert view.cards_grid.count() >= 1  # la tarjeta de config se renderiza


def test_accept_config_calls_controller(qapp):
    view = _view(qapp, _proposal())
    view._accept_config("b1")
    assert view.ic.applied == "b1"


def test_discard_config_calls_controller(qapp):
    view = _view(qapp, _proposal())
    view._discard_config("b1")
    assert view.ic.discarded == "b1"


def test_open_config_panel_sets_drawer(qapp):
    view = _view(qapp, _proposal())
    view.ctx.drawer = type("D", (), {"set_content": lambda self, w, title="": setattr(self, "content", w),
                                     "open": lambda self: setattr(self, "opened", True),
                                     "close": lambda self: None})()
    view._open_config_panel("b1")
    assert isinstance(view.ctx.drawer.content, ImportProjectConfigPanel)


# ── Panel ─────────────────────────────────────────────────────────────────────


class _PanelCtrl:
    def __init__(self):
        self.updated = None
        self.applied = None
        self.discarded = None

    def update_project_config_suggestion(self, basket_id, edits):
        self.updated = (basket_id, edits)
        return Ok({})

    def apply_project_config_suggestion(self, basket_id):
        self.applied = basket_id
        return Ok({"chronology": True})

    def discard_project_config_suggestion(self, basket_id):
        self.discarded = basket_id
        return Ok(True)


def test_panel_accept_updates_then_applies(qapp):
    ctrl = _PanelCtrl()
    decisions = []
    panel = ImportProjectConfigPanel(_proposal(), ctrl, basket_id="b1",
                                     on_decision=decisions.append)
    panel.name_edit.setText("Calendario Editado")
    panel._accept()
    assert ctrl.updated is not None
    assert ctrl.updated[1]["calendar_name"] == "Calendario Editado"
    assert ctrl.applied == "b1"
    assert decisions == ["accept"]


def test_panel_discard_calls_controller(qapp):
    ctrl = _PanelCtrl()
    panel = ImportProjectConfigPanel(_proposal(), ctrl, basket_id="b1")
    panel._discard()
    assert ctrl.discarded == "b1"


def test_panel_shows_eras_and_entities(qapp):
    # No debe lanzar al construir con propuesta rica; refleja modo en el combo.
    panel = ImportProjectConfigPanel(_proposal(), _PanelCtrl(), basket_id="b1")
    assert panel.mode_combo.currentData() == "vague_periods"
    assert panel.year_edit.text() == "1200"
