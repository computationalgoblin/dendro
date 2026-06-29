"""Campana de germinación más cálida/zen (BETA1-UX27)."""
from __future__ import annotations

import wave

from hosts.DesktopHostPySide.widgets import seed_audio as sa


def test_registro_raiz() -> None:
    # UX33: D#5 (63) — más agudo que D#4, manteniendo el procesado cálido.
    assert sa._ROOT_MIDI == 63


def test_escala_sigue_siendo_d_sharp_minor() -> None:
    assert sa.is_in_d_sharp_minor(sa._ROOT_MIDI)
    for _ in range(20):
        assert sa.is_in_d_sharp_minor(sa.random_bell_midi())


def test_render_bell_produce_wav_valido_y_no_vacio() -> None:
    path = sa._render_bell(sa._ROOT_MIDI)
    assert "dendro_bell_v4_" in path  # versión de caché nueva
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == sa._RATE
        assert w.getnframes() > sa._RATE  # > 1 s de cola
