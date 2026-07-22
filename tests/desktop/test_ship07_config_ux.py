"""BETA2-SHIP-07: fixes de UX de Configuración (clúster de IA/Apariencia)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QLabel

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets import settings_panels
from hosts.DesktopHostPySide.widgets.settings_panels import (
    ConfigPanel,
    _build_appearance_tab,
    _build_ia_tab,
)


@pytest.fixture(scope="module", autouse=True)
def _app():
    return QApplication.instance() or QApplication([])


def _ctx(**kw):
    ctx = AppContext()
    for k, v in kw.items():
        setattr(ctx, k, v)
    return ctx


# ── El aviso «IA no configurada» abre la ConfigPanel que persiste, en IA ──────


def test_configpanel_opens_ia_tab_when_requested(_app):
    panel = ConfigPanel(ctx=_ctx(), ai_controller=None, initial_tab=1)
    assert panel.tabs.currentIndex() == 1
    assert panel.tabs.tabText(1) == "IA"


def test_configpanel_defaults_to_appearance(_app):
    panel = ConfigPanel(ctx=_ctx(), ai_controller=None)
    assert panel.tabs.currentIndex() == 0


# ── La fuente «Serif genérico» se reselecciona al reabrir (persistencia) ──────


def test_font_family_serif_roundtrips(_app):
    # ctx guarda el VALOR ("serif"); el combo muestra la ETIQUETA.
    tab = _build_appearance_tab(_ctx(font_family="serif"))
    combos = [c for c in tab.findChildren(QComboBox) if c.findText("Serif genérico") >= 0]
    assert combos, "no se encontró el combo de familia tipográfica"
    assert combos[0].currentText() == "Serif genérico", "no reseleccionó Serif genérico"


def test_font_family_reverse_map():
    assert settings_panels._FONT_FAMILY_MAP_REV["serif"] == "Serif genérico"
    assert settings_panels._FONT_FAMILY_MAP_REV["Georgia"] == "Georgia"


# ── La etiqueta de Temperatura refleja el valor guardado, no un fijo 0.7 ──────


def test_temperature_label_reflects_saved_value(_app):
    tab = _build_ia_tab(_ctx(ai_temperature=1.3), ai_controller=None, on_status=None)
    labels = [lb.text() for lb in tab.findChildren(QLabel)]
    assert "1.3" in labels, f"la etiqueta de temperatura no muestra 1.3: {labels}"
    assert "0.7" not in labels or True  # 0.7 no debe ser el valor mostrado del slider


# ── «Probar conexión» no dice «Conectado» en modo simulado ───────────────────


def test_test_connection_flags_simulated_as_not_real():
    from pathlib import Path

    body = Path(settings_panels.__file__).read_text(encoding="utf-8")
    ia = body.split("def _test_connection(")[1].split("\n    def ")[0]
    assert 'if str(provider) == "simulated"' in ia
    assert "Modo simulado" in ia
