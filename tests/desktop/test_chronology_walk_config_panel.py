"""CRON — panel de configuración del recorrido (offscreen)."""

from __future__ import annotations

import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HAS_QT = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 no disponible")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_config_panel_emits_selected_config():
    _app()
    from hosts.DesktopHostPySide.widgets.chronology_walk_config_panel import (
        ChronologyWalkConfigPanel,
    )
    from packages.domain.chronology_walk import (
        WalkAggressiveness,
        WalkDepth,
        WalkDirection,
        WalkMode,
    )

    panel = ChronologyWalkConfigPanel("hito-1", start_title="La Caída")
    captured = {}
    panel.submitted.connect(lambda cfg: captured.update(cfg))

    # Selecciona valores no-default para comprobar el mapeo.
    panel._direction.setCurrentIndex(1)  # PAST
    panel._mode.setCurrentIndex(1)  # CONSISTENCIA
    panel._depth.setCurrentIndex(2)  # PROFUNDA
    panel._aggressiveness.setCurrentIndex(1)  # SENALAR
    panel._on_submit()

    # Qt aplana los str-Enum al cruzar Signal(dict); el servicio acepta ambos y
    # un str-Enum compara igual a su valor, así que se compara por valor.
    assert captured["start_milestone_id"] == "hito-1"
    assert captured["direction"] == WalkDirection.PAST
    assert captured["mode"] == WalkMode.CONSISTENCIA
    assert captured["depth"] == WalkDepth.PROFUNDA
    assert captured["aggressiveness"] == WalkAggressiveness.SENALAR


def test_config_panel_defaults_are_mixto_future():
    _app()
    from hosts.DesktopHostPySide.widgets.chronology_walk_config_panel import (
        ChronologyWalkConfigPanel,
    )
    from packages.domain.chronology_walk import WalkDirection, WalkMode

    panel = ChronologyWalkConfigPanel("hito-1")
    cfg = panel.config()
    assert cfg["direction"] is WalkDirection.FUTURE
    assert cfg["mode"] is WalkMode.MIXTO
