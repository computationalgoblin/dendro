"""BETA-CIERRE WS-I / B5: identidad del distribuible presente (icono + versión).

Guarda estática: el exe debe llevar icono de Dendro y recurso de versión (para que
Properties→Detalles muestre ProductName/Version en vez de quedar en blanco, y el
taskbar/alt-tab muestren la marca). El build real lo valida el job Windows de CI.
"""

from __future__ import annotations

import struct
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ICO = _ROOT / "hosts" / "DesktopHostPySide" / "assets" / "dendro.ico"
_VER = _ROOT / "packaging" / "version_info.txt"
_SPEC = _ROOT / "packaging" / "dendro.spec"
_MAIN = _ROOT / "hosts" / "DesktopHostPySide" / "main.py"


def test_dendro_icon_exists_and_is_valid_ico():
    assert _ICO.exists(), "falta hosts/DesktopHostPySide/assets/dendro.ico (WS-I/B5)"
    data = _ICO.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert reserved == 0 and kind == 1 and count >= 1, "dendro.ico no es un ICO válido"


def test_version_info_present_and_names_dendro():
    assert _VER.exists(), "falta packaging/version_info.txt (WS-I/B5)"
    txt = _VER.read_text(encoding="utf-8")
    assert "ProductName" in txt and "Dendro" in txt and "ProductVersion" in txt


def test_spec_wires_icon_and_version():
    spec = _SPEC.read_text(encoding="utf-8")
    assert "icon=_icon" in spec and "version=_version" in spec


def test_main_sets_window_icon():
    assert "setWindowIcon" in _MAIN.read_text(encoding="utf-8")
