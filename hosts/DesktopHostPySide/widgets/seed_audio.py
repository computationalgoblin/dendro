"""Campana zen para las notificaciones de semillas (Fase A).

Cuando un job IA culmina y brotan candidatos, suena una pequeña campana por cada
uno: una nota aleatoria dentro de la escala de Re# menor (D#m), escalonadas con
delay (arpegio) y con cola de reverb. La síntesis es propia (timbre de campana,
inarmónica, ataque rápido y decay largo) — distinta del pad ambiental del Home,
pero en la misma tonalidad.

Robusto: si QtMultimedia no está disponible el módulo funciona como no-op y nunca
rompe el flujo del job. La nota se sintetiza una vez por tono y se cachea a WAV.
"""

from __future__ import annotations

import math
import random
import struct
import tempfile
import wave
from pathlib import Path

from PySide6.QtCore import QTimer

try:  # QtMultimedia viene con PySide6, pero lo protegemos igual.
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QSoundEffect

    _HAS_AUDIO = True
except Exception:  # noqa: BLE001 — sin audio, las semillas siguen funcionando
    _HAS_AUDIO = False


# Re# menor natural: D# E#(F) F# G# A# B C# → semitonos 0 2 3 5 7 8 10.
D_SHARP_MINOR_SEMITONES: tuple[int, ...] = (0, 2, 3, 5, 7, 8, 10)
# Registro de campana: D#5 como raíz (brillante pero no estridente).
_ROOT_MIDI = 39 + 24  # D#5
_RATE = 16000
_BELL_SECONDS = 2.6


def is_in_d_sharp_minor(midi: int) -> bool:
    """True si la nota MIDI pertenece a la escala de Re# menor (pura, testable)."""
    return ((int(midi) - _ROOT_MIDI) % 12) in D_SHARP_MINOR_SEMITONES


def random_bell_midi(rng: random.Random | None = None) -> int:
    """Devuelve una nota MIDI aleatoria dentro de D#m en el registro de campana."""
    r = rng or random
    return _ROOT_MIDI + r.choice(D_SHARP_MINOR_SEMITONES)


class ZenBell:
    """Reproductor de campanas zen, cacheado y seguro sin audio."""

    def __init__(self, *, volume: float = 0.16) -> None:
        self._volume = float(volume)
        self._rng = random.Random()
        self._effects: dict[int, object] = {}  # midi → QSoundEffect
        self._enabled = True

    @property
    def available(self) -> bool:
        return bool(_HAS_AUDIO and self._enabled)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def play(self, midi: int | None = None) -> None:
        """Tañe una campana (una nota en D#m). No-op seguro si no hay audio."""
        if not self.available:
            return
        note = random_bell_midi(self._rng) if midi is None else int(midi)
        try:
            effect = self._effects.get(note)
            if effect is None:
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(_render_bell(note)))
                self._effects[note] = effect
            effect.setVolume(self._volume)
            effect.play()
        except Exception:  # noqa: BLE001 — el sonido nunca rompe el flujo
            return

    def play_arpeggio(self, count: int, *, stagger_ms: int = 220, max_notes: int = 8) -> None:
        """Tañe ``count`` campanas escalonadas (arpegio), acotado a ``max_notes``."""
        if not self.available or count <= 0:
            return
        notes = max(1, min(int(count), int(max_notes)))
        for index in range(notes):
            QTimer.singleShot(index * int(stagger_ms), self.play)


def _render_bell(midi: int) -> str:
    """Sintetiza una campana inarmónica con reverb y la cachea a WAV temporal."""
    path = Path(tempfile.gettempdir()) / f"dendro_bell_{midi}.wav"
    if path.exists():
        return str(path)
    rate = _RATE
    total = int(_BELL_SECONDS * rate)
    freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
    two_pi = 2.0 * math.pi
    attack = max(1, int(0.004 * rate))  # ataque rápido (golpe de campana)
    tau = 1.1  # s — decay exponencial largo
    # Parciales inarmónicos típicos de campana (ratios + amplitudes decrecientes).
    partials = ((1.0, 0.55), (2.01, 0.30), (2.78, 0.18), (4.07, 0.10), (5.43, 0.06))
    dry = [0.0] * total
    for ratio, amp in partials:
        w = two_pi * freq * ratio / rate
        for n in range(total):
            env = (n / attack) if n < attack else math.exp(-(n - attack) / (tau * rate))
            dry[n] += amp * env * math.sin(w * n)
    # Reverb: combs con retroalimentación (cola zen).
    for delay_s, feedback in ((0.137, 0.30), (0.211, 0.24)):
        d = int(delay_s * rate)
        for n in range(d, total):
            dry[n] += feedback * dry[n - d]
    peak = max(0.0001, max(abs(s) for s in dry))
    scale = 0.8 / peak
    frames = bytearray()
    for sample in dry:
        frames += struct.pack("<h", int(max(-0.95, min(0.95, sample * scale)) * 32767))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))
    return str(path)


__all__ = [
    "ZenBell",
    "is_in_d_sharp_minor",
    "random_bell_midi",
    "D_SHARP_MINOR_SEMITONES",
]
