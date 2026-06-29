"""Foco sin salto de layout + anillo de foco en QToolButton (BETA1-UX26).

No necesita QApplication: inspecciona el QSS renderizado (APP_STYLESHEET).
"""
from __future__ import annotations

import re

from hosts.DesktopHostPySide.widgets import design_system as ds

_QSS = ds.APP_STYLESHEET


def _padding(selector: str) -> tuple[int, int]:
    """Extrae (vertical, horizontal) del primer 'padding: Vpx Hpx' de una regla."""
    m = re.search(re.escape(selector) + r"\s*\{(.*?)\}", _QSS, re.S)
    assert m, f"regla no encontrada: {selector}"
    p = re.search(r"padding:\s*(\d+)px\s+(\d+)px", m.group(1))
    assert p, f"sin padding en {selector}"
    return int(p.group(1)), int(p.group(2))


def test_boton_compensa_padding_en_foco() -> None:
    base_v, base_h = _padding("QPushButton")
    foc_v, foc_h = _padding("QPushButton:focus")
    # border 1px→2px (+1 por lado) compensado con -1px de padding por eje.
    assert (foc_v, foc_h) == (base_v - 1, base_h - 1)
    assert "QPushButton:focus" in _QSS and "border: 2px" in _QSS


def test_inputs_compensan_padding_en_foco() -> None:
    base_sel = (
        "QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, "
        "QTableWidget, QSpinBox, QDoubleSpinBox"
    )
    base_v, base_h = _padding(base_sel)
    foc_v, foc_h = _padding(
        "QTextEdit:focus, QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus"
    )
    assert (foc_v, foc_h) == (base_v - 1, base_h - 1)


def test_toolbutton_tiene_foco_sin_cambiar_ancho_de_borde() -> None:
    # QToolButton:focus solo cambia el color del borde (no el ancho) → sin salto.
    m = re.search(r"QToolButton:focus\s*\{(.*?)\}", _QSS, re.S)
    assert m, "falta QToolButton:focus"
    body = m.group(1)
    assert "border-color" in body
    # No redefine el ancho del borde (nada de 'border: Npx').
    assert not re.search(r"border:\s*\d+px", body)
