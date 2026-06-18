"""Semillas (Fase A): campana zen — helpers puros y no-op seguro sin audio."""

from __future__ import annotations

import random

import pytest

from hosts.DesktopHostPySide.widgets.seed_audio import (
    D_SHARP_MINOR_SEMITONES,
    ZenBell,
    is_in_d_sharp_minor,
    random_bell_midi,
)


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_scale_membership():
    # La raíz (D#5) y sus grados pertenecen; los de fuera de la escala no.
    root = 39 + 24
    for semis in D_SHARP_MINOR_SEMITONES:
        assert is_in_d_sharp_minor(root + semis)
    assert not is_in_d_sharp_minor(root + 1)  # E natural, fuera de D#m


def test_random_bell_midi_always_in_scale():
    rng = random.Random(0)
    for _ in range(50):
        assert is_in_d_sharp_minor(random_bell_midi(rng))


def test_disabled_bell_is_noop(qapp):
    bell = ZenBell()
    bell.set_enabled(False)
    assert bell.available is False
    # No debe sintetizar ni lanzar nada con audio deshabilitado.
    bell.play()
    bell.play_arpeggio(5)


def test_arpeggio_zero_count_is_noop(qapp):
    bell = ZenBell()
    bell.set_enabled(False)
    bell.play_arpeggio(0)
