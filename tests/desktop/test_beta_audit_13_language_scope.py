"""BETA-AUDIT-13: el idioma sólo promete lo que de verdad cambia.

Ajustes → Apariencia ofrecía un combo «Idioma» (Español / English) que **no traducía
nada**: no hay `QTranslator`, ni `installTranslator`, ni ficheros `.ts` en todo el
host. Elegir «English» dejaba la interfaz entera en español. Su único consumidor real
era el system prompt del mini-chat.

Decisión de producto (2026-08-02): no se implementa i18n en una beta en español; el
control se mueve a la pestaña IA como «Idioma del asistente», que es lo que hace.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

import hosts.DesktopHostPySide.app_context as ac  # noqa: E402
from hosts.DesktopHostPySide.widgets.settings_panels import (  # noqa: E402
    _build_appearance_tab,
    _build_ia_tab,
)

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _preferencias_aisladas(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "PREFERENCES_PATH", tmp_path / "settings.json")


def _textos_de_combos(widget) -> list[str]:
    salida = []
    for combo in widget.findChildren(QComboBox):
        salida.extend(combo.itemText(i) for i in range(combo.count()))
    return salida


def test_apariencia_ya_no_ofrece_idioma(qapp):
    tab = _build_appearance_tab(ac.AppContext())
    try:
        opciones = _textos_de_combos(tab)
        assert "English" not in opciones, (
            "Apariencia sigue ofreciendo un idioma que no traduce la interfaz"
        )
    finally:
        tab.deleteLater()
        qapp.processEvents()


def test_guardar_apariencia_no_pisa_el_idioma(qapp):
    ctx = ac.AppContext()
    ctx.language = "en"
    tab = _build_appearance_tab(ctx)
    try:
        guardar = [b for b in tab.findChildren(type(tab)) if False]  # noqa: F841
        from PySide6.QtWidgets import QPushButton

        for boton in tab.findChildren(QPushButton):
            if "Guardar" in boton.text():
                boton.click()
                break
        assert ctx.language == "en", (
            "guardar Apariencia reseteó un idioma que ya no le corresponde gobernar"
        )
    finally:
        tab.deleteLater()
        qapp.processEvents()


def test_la_pestana_ia_gobierna_el_idioma_del_asistente(qapp):
    ctx = ac.AppContext()
    ctx.language = "es"
    tab = _build_ia_tab(ctx, ai_controller=None, on_status=None)
    try:
        combos = [
            c
            for c in tab.findChildren(QComboBox)
            if "English" in [c.itemText(i) for i in range(c.count())]
        ]
        assert combos, "la pestaña IA no expone el idioma del asistente"
        combos[0].setCurrentIndex(1)  # English
        from PySide6.QtWidgets import QPushButton

        for boton in tab.findChildren(QPushButton):
            if "Guardar" in boton.text():
                boton.click()
                break
        assert ctx.language == "en", "cambiar el idioma del asistente no persistió"
    finally:
        tab.deleteLater()
        qapp.processEvents()


def test_sigue_sin_haber_infraestructura_de_traduccion():
    """Si algún día se añade i18n de verdad, este test avisa de que hay que revisitar."""
    salida = subprocess.run(
        # Uso REAL, no menciones en comentarios (este propio fichero la nombra).
        ["git", "grep", "-l", "-E", r"QTranslator\(|installTranslator\(", "--", "hosts", "packages"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )
    assert not salida.stdout.strip(), (
        "apareció infraestructura de traducción: revisar la decisión de BETA-AUDIT-13"
    )


def test_los_presets_estan_todos_en_espanol():
    from packages.domain.creative_presets import CREATIVE_PRESETS

    assert CREATIVE_PRESETS["weird_mystery"]["label"] == "Misterio extraño"
    # La clave es dato persistido en proyectos existentes: no puede cambiar.
    assert "weird_mystery" in CREATIVE_PRESETS
