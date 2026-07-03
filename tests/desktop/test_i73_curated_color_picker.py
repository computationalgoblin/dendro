"""I73 (desktop) — CuratedColorPicker: selector de color embebido con paleta curada."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from hosts.DesktopHostPySide.widgets.curated_color_picker import (  # noqa: E402
    CURATED_COLORS,
    CuratedColorPicker,
)


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_palette_is_curated_and_nonempty():
    assert len(CURATED_COLORS) >= 12
    assert all(c.startswith("#") and len(c) == 7 for c in CURATED_COLORS)
    assert len(set(CURATED_COLORS)) == len(CURATED_COLORS)  # sin duplicados


def test_choosing_emits_and_closes(qapp):
    picker = CuratedColorPicker(current=CURATED_COLORS[0])
    chosen: list[str] = []
    picker.colorChosen.connect(chosen.append)
    picker._choose("#6E8B3D")
    assert chosen == ["#6E8B3D"]
    assert picker.isHidden()  # se cierra al elegir


def test_is_not_a_native_dialog(qapp):
    from PySide6.QtCore import Qt

    picker = CuratedColorPicker()
    # Es un popover embebido (Qt.Popup), no un diálogo del SO que se salga de la app.
    assert bool(picker.windowFlags() & Qt.WindowType.Popup)
