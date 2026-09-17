"""BETA2-PULIDO-05: armonización — pin estático del sistema en la vista de Creación."""
from __future__ import annotations

from pathlib import Path

_CREATION_SOURCES = [
    "hosts/DesktopHostPySide/views/workspaces.py",
    "hosts/DesktopHostPySide/widgets/foco/foco_view.py",
    "hosts/DesktopHostPySide/widgets/foco/cultivation_notebook.py",
    "hosts/DesktopHostPySide/widgets/foco/watering_panel.py",
    "hosts/DesktopHostPySide/widgets/foco/watering_authorize.py",
    "hosts/DesktopHostPySide/widgets/foco/foco_popover.py",
    "hosts/DesktopHostPySide/widgets/seed_notifications.py",
]

def _read(path):
    return Path(path).read_text(encoding="utf-8")

def test_no_orphan_hex_for_tokenized_colors():
    for path in _CREATION_SOURCES:
        source = _read(path)
        assert "#FCF8EC" not in source, path   # INK_INVERSE
        assert "#5E5427" not in source, path   # GOLD_PRESS

def test_no_font_sizes_below_caption_floor():
    for path in _CREATION_SOURCES:
        source = _read(path)
        assert "font-size: 9px" not in source, path
        assert "font-size: 10px" not in source, path


def test_creation_sources_consume_the_named_type_scale():
    """BETA2-FIX-13 (G2-18): ni un `font-size:` literal en las
    superficies de trabajo.

    En Qt la hoja de estilo del propio widget gana a la del ancestro, así que un
    literal es exactamente lo que impedía que «Tamaño de fuente: Grande» agrandara
    nada donde se trabaja (11 px antes, 11 px después). La escala nombrada
    `TYPE_*_PX` del design system es la única vía.
    """
    import re

    literal = re.compile(r"font-size:\s*\d+\s*px")
    culpables = []
    for path in _CREATION_SOURCES:
        source = _read(path)
        culpables += [f"{path} → {m.group(0)}" for m in literal.finditer(source)]
    assert not culpables, "píxeles a mano en una superficie de trabajo: " + " · ".join(culpables)

def test_new_tokens_and_helpers_are_used():
    ds = _read("hosts/DesktopHostPySide/widgets/design_system.py")
    assert "RADIUS_CAPSULE" in ds and "def overline_label" in ds and "class ElidedLabel" in ds
    workspaces = _read("hosts/DesktopHostPySide/views/workspaces.py")
    assert "RADIUS_CAPSULE" in workspaces and "ElidedLabel" in workspaces
    foco_view = _read("hosts/DesktopHostPySide/widgets/foco/foco_view.py")
    assert "ElidedLabel" in foco_view
