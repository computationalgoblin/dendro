"""BETA2-UI2-10: pill temporal — años tecleables, Presente sano y embudo.

- Los campos desde/hasta aplican el rango (clamp + swap) al lienzo.
- "Presente" con año configurado hace UNA sola reconstrucción al año correcto
  (antes activar el toggle disparaba un salto intermedio al valor viejo del
  slider); sin año configurado el botón queda deshabilitado (nada de saltar
  al año 0 con el grafo vacío).
- El año presente tecleado solo EMITE ``presentYearEdited`` (persiste el
  workspace vía era_controller — pin de fuente).
- El badge del embudo refleja los filtros activos.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    HAS_QT = True
except Exception:  # noqa: BLE001
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")

_WORKSPACES = Path("hosts/DesktopHostPySide/views/workspaces.py")


@pytest.fixture()
def qapp():
    return QApplication.instance() or QApplication([])


def _widget(*, present_year=None, entities=()):
    from hosts.DesktopHostPySide.widgets.graph_canvas import GraphCanvasWidget

    chronology = (
        SimpleNamespace(present_year=present_year, eras=[], metadata={})
        if present_year is not None
        else None
    )
    project = SimpleNamespace(
        world_layers=[],
        entities=list(entities),
        relations=[],
        causal_milestones=[],
        project_chronology=chronology,
    )
    ctx = SimpleNamespace(
        project_controller=SimpleNamespace(ps=SimpleNamespace(active_project=project)),
        advanced_mode=False,
        creation_layout_mode="concentric_rings",
        creation_focused_ring_id="",
        selected_entity_id="",
        save_preferences=lambda: None,
        log=lambda *args, **kwargs: None,
    )
    widget = GraphCanvasWidget(ctx)
    widget.resize(1200, 800)
    return widget


def _life(birth, death=None):
    return SimpleNamespace(birth_year=birth, death_year=death)


class TestPresentButton:
    def test_disabled_without_configured_present(self, qapp):
        widget = _widget(entities=[_life(0, 100)])
        widget._sync_time_bar()
        assert widget._time_present_year is None
        assert not widget._time_present_btn.isEnabled()

        # Pulsarlo no hace nada: la vista sigue atemporal (nada de año 0).
        widget._on_time_present()
        assert widget.canvas.view_range() is None
        widget.deleteLater()

    def test_present_jump_is_single_rebuild_at_right_year(self, qapp):
        widget = _widget(present_year=50, entities=[_life(0, 100)])
        widget._sync_time_bar()
        assert widget._time_present_btn.isEnabled()
        assert not widget._time_toggle.isChecked()

        calls = []
        original = widget.canvas.set_view_range

        def spying_set_view_range(lo, hi=None):
            calls.append((lo, hi))
            return original(lo, hi)

        widget.canvas.set_view_range = spying_set_view_range  # type: ignore[method-assign]
        widget._on_time_present()

        # UNA sola llamada, directa al presente — sin salto intermedio al
        # valor viejo del slider (el toggle se activó con señales bloqueadas).
        assert calls == [(50, 50)]
        assert widget.canvas.view_range() == (50, 50)
        assert widget._time_toggle.isChecked()
        assert widget._time_from_edit.text() == "50"
        assert widget._time_to_edit.text() == "50"
        widget.deleteLater()


class TestYearEdits:
    def test_typed_years_apply_clamped_and_swapped(self, qapp):
        widget = _widget(present_year=50, entities=[_life(0, 100)])
        widget._sync_time_bar()
        widget._time_toggle.setChecked(True)

        widget._time_from_edit.setText("80")
        widget._time_to_edit.setText("20")
        widget._on_year_edited()  # desde > hasta → swap
        assert widget.canvas.view_range() == (20, 80)

        widget._time_from_edit.setText("-500")
        widget._time_to_edit.setText("900")
        widget._on_year_edited()  # fuera de límites → clamp al rango del proyecto
        assert widget.canvas.view_range() == (0, 100)
        widget.deleteLater()

    def test_readout_swaps_with_temporal_mode(self, qapp):
        widget = _widget(present_year=50, entities=[_life(0, 100)])
        widget._sync_time_bar()
        # Atemporal: rótulo visible, campos ocultos.
        assert widget._time_readout.isVisibleTo(widget._time_bar)
        assert not widget._time_from_edit.isVisibleTo(widget._time_bar)

        widget._time_toggle.setChecked(True)
        assert not widget._time_readout.isVisibleTo(widget._time_bar)
        assert widget._time_from_edit.isVisibleTo(widget._time_bar)
        assert widget._time_to_edit.isVisibleTo(widget._time_bar)

        widget._time_toggle.setChecked(False)
        assert widget.canvas.view_range() is None
        assert widget._time_readout.isVisibleTo(widget._time_bar)
        widget.deleteLater()


class TestPresentYearEdit:
    def test_typed_present_only_emits_signal(self, qapp):
        widget = _widget(present_year=50, entities=[_life(0, 100)])
        widget._sync_time_bar()
        received = []
        widget.presentYearEdited.connect(received.append)

        widget._present_edit.setText("77")
        widget._on_present_year_edit()
        assert received == [77]
        # El estado local no cambia hasta que el workspace persista y refresque.
        assert widget._time_present_year == 50

        # Mismo valor que el presente conocido → sin emisión redundante.
        widget._present_edit.setText("50")
        widget._on_present_year_edit()
        assert received == [77]
        widget.deleteLater()

    def test_workspace_persists_via_era_controller(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "self.graph.presentYearEdited.connect(self._on_present_year_edited)" in source
        assert "controller.set_present_year(int(year))" in source


class TestFilterFunnel:
    def test_badge_reflects_active_count(self, qapp):
        widget = _widget(entities=[_life(0, 100)])
        widget._sync_time_bar()
        anchor = widget.filter_anchor()
        assert anchor is widget._time_filter_btn

        widget.set_filter_badge_count(0)
        assert not widget._filter_badge.isVisibleTo(anchor)
        widget.set_filter_badge_count(3)
        assert widget._filter_badge.isVisibleTo(anchor)
        assert widget._filter_badge.text() == "3"
        widget.set_filter_badge_count(0)
        assert not widget._filter_badge.isVisibleTo(anchor)
        widget.deleteLater()

    def test_funnel_emits_filter_requested(self, qapp):
        widget = _widget(entities=[_life(0, 100)])
        fired = []
        widget.filterRequested.connect(lambda: fired.append(True))
        widget._time_filter_btn.click()
        assert fired == [True]
        widget.deleteLater()

    def test_workspace_wires_popover_and_indicator(self):
        source = _WORKSPACES.read_text(encoding="utf-8")
        assert "self.graph.filterRequested.connect(self._open_filter_popover)" in source
        assert "popover.open_below(self.graph.filter_anchor())" in source
        assert "self.graph.set_filter_badge_count(self.graph.active_filter_count())" in source
