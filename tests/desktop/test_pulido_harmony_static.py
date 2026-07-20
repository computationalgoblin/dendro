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

def test_new_tokens_and_helpers_are_used():
    ds = _read("hosts/DesktopHostPySide/widgets/design_system.py")
    assert "RADIUS_CAPSULE" in ds and "def overline_label" in ds and "class ElidedLabel" in ds
    workspaces = _read("hosts/DesktopHostPySide/views/workspaces.py")
    assert "RADIUS_CAPSULE" in workspaces and "ElidedLabel" in workspaces
    foco_view = _read("hosts/DesktopHostPySide/widgets/foco/foco_view.py")
    assert "ElidedLabel" in foco_view
