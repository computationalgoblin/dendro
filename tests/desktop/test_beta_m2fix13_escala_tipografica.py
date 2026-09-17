"""BETA2-FIX-13 · TANDA C — que «Tamaño de fuente» agrande de verdad (G2-18).

    «Lo primero que hago yo en cualquier programa es buscar cómo agrandar la
    letra. Lo puse en Grande. No cambió absolutamente nada. Lo medí: 11 píxeles
    antes y 11 píxeles después.»  — Carmen, 58 años, gafas para leer.

El ajuste NO estaba desconectado: `_apply_live_preferences` existía, se llamaba y
emitía el `font-size` correcto. Lo que pasaba es que en Qt la hoja de estilo del
PROPIO widget gana a la del ancestro, y el host tenía ~190 `font-size:` literales
(55 de ellos exactamente a 11px). El arreglo es reescribir ESOS literales.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QFontMetrics  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from hosts.DesktopHostPySide.widgets import design_system as ds  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _escala_neutra():
    """Ningún test puede dejar la escala del módulo tocada para el siguiente."""
    yield
    ds.set_font_scale("medium")


def _alturas(raiz) -> list[int]:
    """Alto de fuente MEDIDO de cada etiqueta con texto (lo que ve el usuario)."""
    return [
        QFontMetrics(w.font()).height()
        for w in raiz.findChildren(QLabel)
        if w.styleSheet() and "font-size" in w.styleSheet()
    ]


def _cuaderno(qapp):
    from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import CultivationNotebook

    cuaderno = CultivationNotebook()
    qapp.processEvents()
    return cuaderno


# ── criterio 8 ─────────────────────────────────────────────────────────────


def test_beta_m2fix13_grande_agranda_el_cuaderno_de_cultivo(qapp):
    """La superficie donde Carmen trabajaba: métricas, filas de riesgo ⚠ y chips."""
    ds.set_font_scale("medium")
    cuaderno = _cuaderno(qapp)
    try:
        ds.apply_font_scale(cuaderno, include_root=True)
        medianos = _alturas(cuaderno)
        assert medianos, "el cuaderno no expone ninguna etiqueta con tamaño propio"

        ds.set_font_scale("large")
        ds.apply_font_scale(cuaderno, include_root=True)
        grandes = _alturas(cuaderno)

        assert len(grandes) == len(medianos)
        assert all(g >= m for g, m in zip(grandes, medianos, strict=True))
        assert sum(grandes) > sum(medianos), "«Grande» no agrandó NADA (el bug de Carmen)"
        # …y crece de verdad, no un píxel de cortesía: al menos 2 px en el cuerpo.
        assert max(grandes) >= max(medianos) + 2
    finally:
        cuaderno.deleteLater()
        qapp.processEvents()


def test_beta_m2fix13_grande_agranda_el_rotulo_de_foco_de_creacion(qapp):
    """`workspaces._focus_label` («Mostrando todo»): el rótulo de la barra superior
    de Creación, medido por la tester a 11 px antes y 11 px después."""
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    caja = QWidget()
    columna = QVBoxLayout(caja)
    etiqueta = QLabel("Mostrando todo")
    columna.addWidget(etiqueta)
    etiqueta.setStyleSheet(f"color: #6F6A42; font-size: {ds.TYPE_CAPTION_PX}px; padding: 0 8px;")
    try:
        ds.set_font_scale("medium")
        ds.apply_font_scale(caja, include_root=True)
        etiqueta.ensurePolished()
        antes = QFontMetrics(etiqueta.font()).height()
        assert etiqueta.font().pixelSize() == 11, "de partida el rótulo mide 11 px"

        ds.set_font_scale("large")
        ds.apply_font_scale(caja, include_root=True)
        etiqueta.ensurePolished()
        despues = QFontMetrics(etiqueta.font()).height()

        assert etiqueta.font().pixelSize() > 11, "el rótulo se quedó en 11 px con «Grande»"
        assert despues > antes, "el rótulo de foco sigue sin obedecer a «Grande»"
    finally:
        caja.deleteLater()
        qapp.processEvents()


# ── criterio 9 ─────────────────────────────────────────────────────────────


def test_beta_m2fix13_pequeno_encoge_pero_no_por_debajo_del_piso():
    ds.set_font_scale("small")
    pequeno = {rol: ds.fs(rol) for rol in ("h1", "h2", "body", "label", "caption")}
    ds.set_font_scale("medium")
    mediano = {rol: ds.fs(rol) for rol in pequeno}
    ds.set_font_scale("large")
    grande = {rol: ds.fs(rol) for rol in pequeno}

    # La escala no se aplana: pequeño < mediano < grande donde el piso lo permite.
    assert pequeno["body"] < mediano["body"] < grande["body"]
    assert pequeno["h1"] < mediano["h1"] < grande["h1"]
    # PISO del sistema: nada por debajo de TYPE_CAPTION_PX, ni en «Pequeño».
    assert all(px >= ds.TYPE_FLOOR_PX for px in pequeno.values()), pequeno
    assert ds.TYPE_FLOOR_PX == 11


def test_beta_m2fix13_la_escala_es_idempotente():
    """Reaplicar la misma preferencia N veces no compone tamaños (si lo hiciera,
    abrir Ajustes tres veces dejaría la app en tipografía de cartel)."""
    etiqueta = QLabel("x")
    etiqueta.setStyleSheet("font-size: 13px;")
    try:
        ds.set_font_scale("large")
        for _ in range(4):
            ds.apply_font_scale(etiqueta, include_root=True)
        assert re.search(r"font-size:\s*(\d+)px", etiqueta.styleSheet()).group(1) == str(
            ds.fs("body")
        )
        # …y volver a «Mediano» devuelve el tamaño original, no uno intermedio.
        ds.set_font_scale("medium")
        ds.apply_font_scale(etiqueta, include_root=True)
        assert "font-size: 13px" in etiqueta.styleSheet()
    finally:
        etiqueta.deleteLater()


def test_beta_m2fix13_un_widget_que_se_reestila_solo_no_se_descalibra():
    """Muchos widgets se reestilan por su cuenta (hover, estado). Su hoja NUEVA
    pasa a ser la base; nunca se reescala dos veces sobre la anterior."""
    etiqueta = QLabel("x")
    etiqueta.setStyleSheet("font-size: 13px;")
    try:
        ds.set_font_scale("large")
        ds.apply_font_scale(etiqueta, include_root=True)
        etiqueta.setStyleSheet("font-size: 12px;")  # el widget se reestila solo
        ds.apply_font_scale(etiqueta, include_root=True)
        assert f"font-size: {ds.fs('label')}px" in etiqueta.styleSheet()
    finally:
        etiqueta.deleteLater()


# ── criterio 10 — guarda estática ──────────────────────────────────────────

# Las siete rutas donde la tester midió. Son exactamente `_CREATION_SOURCES` de
# `test_pulido_harmony_static.py`.
_SUPERFICIES_DE_TRABAJO = [
    "hosts/DesktopHostPySide/views/workspaces.py",
    "hosts/DesktopHostPySide/widgets/foco/foco_view.py",
    "hosts/DesktopHostPySide/widgets/foco/cultivation_notebook.py",
    "hosts/DesktopHostPySide/widgets/foco/watering_panel.py",
    "hosts/DesktopHostPySide/widgets/foco/watering_authorize.py",
    "hosts/DesktopHostPySide/widgets/foco/foco_popover.py",
    "hosts/DesktopHostPySide/widgets/seed_notifications.py",
]

# Excepciones, por lista explícita y comentada. Hoy VACÍA: las siete superficies
# consumen la escala nombrada entera. Si alguna necesitara un píxel a mano, entra
# aquí con su razón — no se relaja el test.
_EXCEPCIONES_DE_PIXEL_LITERAL: dict[str, str] = {}

_FS_LITERAL = re.compile(r"font-size:\s*\d+\s*px")


def test_beta_m2fix13_sin_font_size_literal_en_superficies_de_trabajo():
    culpables = []
    for ruta in _SUPERFICIES_DE_TRABAJO:
        if ruta in _EXCEPCIONES_DE_PIXEL_LITERAL:
            continue
        fuente = Path(ruta).read_text(encoding="utf-8")
        for m in _FS_LITERAL.finditer(fuente):
            linea = fuente[: m.start()].count("\n") + 1
            culpables.append(f"{ruta}:{linea} → {m.group(0)}")
    assert not culpables, (
        "píxeles literales en una superficie de trabajo (usa la escala nombrada "
        "TYPE_*_PX; si no, «Grande» no llega): " + " · ".join(culpables)
    )
