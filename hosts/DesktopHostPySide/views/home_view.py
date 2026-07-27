"""HomeView — Dendro home portal (BETA 1: single Creación card).

Normal mode is intentionally non-technical: no schema, no provider status, no
counts, no raw IDs. Project/config actions are grouped behind quiet icon buttons
placed at the bottom corners of the home surface.

BETA1-A04 note: originally a three-space portal (B31). Gallery/Session cards
were disconnected in A01; some internal helpers (_BranchLine, gallery/session
tones) remain classified as LEGACY INTERNO — see
docs/architecture/A03_legacy_classification.md.
"""
from __future__ import annotations

import math
import random
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QPropertyAnimation, QEasingCurve, QPointF, QSize, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    Badge,
    make_scroll_area,
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    INK,
    INK_MUTED,
    INK_OLIVE_SOFT,
    INK_SOFT,
    INK_STRONG,
    LINE,
    LINE_MUTED,
    SESSION_INK,
    SESSION_LINE,
    SURFACE_HI,
    WHITE,
)

try:  # BETA1-F01: QtMultimedia viene con PySide6, pero protegemos el import
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QSoundEffect
    _HAS_AUDIO = True
except Exception:  # noqa: BLE001 — sin audio, el Home sigue intacto
    _HAS_AUDIO = False


class _AmbientMusic:
    """BETA1-F01: música GENERATIVA procedural en Re# menor, apagada por
    defecto.

    No hay loop: un conductor (QTimer) improvisa para siempre.
    - Tres voces de acorde (tríadas de la tonalidad: i, III, iv, v, VI, VII)
      en registro grave/medio, desplegadas de forma arpegiada y muy pausada
      (un acorde cada 8-13 s).
    - Una cuarta voz aguda improvisa de vez en cuando frases breves sobre la
      pentatónica de Re# menor (no puede sonar mal).
    - Cada nota se sintetiza UNA vez y se cachea a WAV (temp): seno cálido
      con parcial suave y desafinación, ataque lento, decay exponencial
      largo, paso-bajo de un polo (filtrado) y reverb por combs con
      retroalimentación. Reproducción con QSoundEffect, volumen bajo."""

    _RATE = 12000  # suficiente para un pad oscuro y filtrado; síntesis barata
    _NOTE_SECONDS = 5.5
    _CHORD_VOLUME = 0.17
    _MELODY_VOLUME = 0.10

    # Re# menor natural: D# E#(F) F# G# A# B C#  → semitonos 0 2 3 5 7 8 10
    _ROOT_MIDI = 39  # D#2
    # Tríadas (grados) calmadas, sesgadas a i/VI/III
    _CHORDS = (
        (0, 3, 7),    # i   D#m
        (3, 7, 10),   # III F#
        (8, 0, 3),    # VI  B   (B, D#, F#)
        (5, 8, 0),    # iv  G#m (G#, B, D#)
        (7, 10, 2),   # v   A#m (A#, C#, E#)
        (10, 2, 5),   # VII C#  (C#, E#, G#)
    )
    _CHORD_WEIGHTS = (4, 3, 3, 2, 1, 2)
    # Pentatónica menor de D# para la voz que improvisa: D# F# G# A# C#
    _MELODY_DEGREES = (0, 3, 5, 7, 10)

    def __init__(self):
        self._playing = False
        self._effects: dict[int, object] = {}  # midi → QSoundEffect
        self._rng = random.Random()
        self._chord_timer = None
        self._melody_timer = None
        self._current_chord = 0

    def is_playing(self) -> bool:
        return self._playing

    def toggle(self) -> bool:
        if not _HAS_AUDIO:
            return False
        if self._playing:
            self.stop()
            return False
        self._playing = True
        if self._chord_timer is None:
            self._chord_timer = QTimer()
            self._chord_timer.setSingleShot(True)
            self._chord_timer.timeout.connect(self._next_chord)
            self._melody_timer = QTimer()
            self._melody_timer.setSingleShot(True)
            self._melody_timer.timeout.connect(self._melody_phrase)
        self._next_chord()  # primer acorde inmediato
        self._melody_timer.start(self._rng.randint(6000, 12000))
        return True

    def stop(self):
        self._playing = False
        if self._chord_timer is not None:
            self._chord_timer.stop()
            self._melody_timer.stop()
        for effect in self._effects.values():
            effect.stop()

    # ── conductor ────────────────────────────────────────────────────────

    def _next_chord(self):
        if not self._playing:
            return
        choices = [i for i in range(len(self._CHORDS)) if i != self._current_chord]
        weights = [self._CHORD_WEIGHTS[i] for i in choices]
        self._current_chord = self._rng.choices(choices, weights=weights, k=1)[0]
        degrees = self._CHORDS[self._current_chord]
        # Voicing: raíz grave (oct 0), tercera y quinta en el registro medio
        midis = (
            self._ROOT_MIDI + degrees[0],
            self._ROOT_MIDI + 12 + degrees[1],
            self._ROOT_MIDI + 12 + degrees[2] + (12 if degrees[2] < degrees[1] else 0),
        )
        delay = 0
        for midi in midis:  # despliegue arpegiado, muy pausado
            delay += self._rng.randint(250, 1100)
            QTimer.singleShot(delay, lambda m=midi: self._play_note(m, self._CHORD_VOLUME))
        self._chord_timer.start(self._rng.randint(8000, 13000))

    def _melody_phrase(self):
        if not self._playing:
            return
        if self._rng.random() < 0.75:  # a veces, simplemente silencio
            count = self._rng.randint(1, 3)
            delay = 0
            last = None
            for _ in range(count):
                degree = self._rng.choice([d for d in self._MELODY_DEGREES if d != last])
                last = degree
                midi = self._ROOT_MIDI + 36 + degree  # D#5 y alrededores
                delay += self._rng.randint(700, 1600)
                QTimer.singleShot(delay, lambda m=midi: self._play_note(m, self._MELODY_VOLUME))
        self._melody_timer.start(self._rng.randint(7000, 15000))

    def _play_note(self, midi: int, volume: float):
        if not self._playing:
            return
        effect = self._effects.get(midi)
        if effect is None:
            path = self._render_note(midi)
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(path))
            self._effects[midi] = effect
        effect.setVolume(volume)
        effect.play()

    # ── síntesis (una vez por nota, cacheada) ────────────────────────────

    def _render_note(self, midi: int) -> str:
        import struct
        import tempfile
        import wave
        from pathlib import Path

        path = Path(tempfile.gettempdir()) / f"dendro_note_{midi}_v2.wav"
        if path.exists():
            return str(path)
        rate = self._RATE
        total = int(self._NOTE_SECONDS * rate)
        freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        two_pi = 2.0 * math.pi
        attack = int(0.55 * rate)
        tau = 1.9  # s — decay largo
        # 1) oscilador cálido + envolvente
        dry = [0.0] * total
        w1 = two_pi * freq / rate
        w2 = two_pi * freq * 2.0 / rate          # parcial suave (octava)
        w3 = two_pi * freq * 1.004 / rate        # desafinación leve
        for n in range(total):
            env = (n / attack) if n < attack else math.exp(-(n - attack) / (tau * rate))
            dry[n] = env * (
                0.62 * math.sin(w1 * n)
                + 0.18 * math.sin(w2 * n)
                + 0.30 * math.sin(w3 * n)
            )
        # 2) paso-bajo de un polo (filtrado, oscurece)
        cutoff = 900.0
        alpha = 1.0 / (1.0 + rate / (two_pi * cutoff))
        prev = 0.0
        for n in range(total):
            prev += alpha * (dry[n] - prev)
            dry[n] = prev
        # 3) reverb: tres combs con retroalimentación (colas largas)
        for delay_s, feedback in ((0.149, 0.34), (0.211, 0.28), (0.293, 0.22)):
            d = int(delay_s * rate)
            for n in range(d, total):
                dry[n] += feedback * dry[n - d]
        # normalizar con techo suave
        peak = max(0.0001, max(abs(s) for s in dry))
        scale = 0.82 / peak
        frames = bytearray()
        for sample in dry:
            frames += struct.pack("<h", int(max(-0.95, min(0.95, sample * scale)) * 32767))
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(bytes(frames))
        return str(path)


class _AtmosphereOverlay(QWidget):
    """BETA1-F01: atmósfera del Home — hojas a la deriva y raíces orgánicas
    de baja opacidad.

    Decorativa y barata: transparente al ratón, repaint ~25 fps SOLO mientras
    el Home está visible, y si el contexto pide movimiento reducido
    (animation_duration → 0) no hay timer: solo las raíces estáticas.
    Se dibuja DEBAJO de las cards (lower())."""

    _LEAF_COUNT = 18

    def __init__(self, parent: QWidget, *, ctx=None):
        super().__init__(parent)
        self._ctx = ctx
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._rng = random.Random(7)
        self._leaves = [self._spawn_leaf(initial=True) for _ in range(self._LEAF_COUNT)]
        self._phase = 0.0
        # BETA1-F01 (viento): el cursor actúa como corriente — las hojas
        # cercanas reciben un impulso según la velocidad del ratón.
        self._last_mouse: QPointF | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._advance)
        parent.setMouseTracking(True)
        parent.installEventFilter(self)
        self.setGeometry(parent.rect())
        self.lower()

    # ── ciclo de vida ────────────────────────────────────────────────────

    def _animations_enabled(self) -> bool:
        ctx = self._ctx
        if ctx is None or not hasattr(ctx, "animation_duration"):
            return True
        try:
            return int(ctx.animation_duration(100)) > 0
        except Exception:  # noqa: BLE001 — la atmósfera jamás debe romper el Home
            return True

    def eventFilter(self, watched, event):
        if watched is self.parent():
            if event.type() == QEvent.Type.Resize:
                self.setGeometry(self.parent().rect())
            elif event.type() == QEvent.Type.Show:
                if self._animations_enabled() and not self._timer.isActive():
                    self._timer.start()
            elif event.type() == QEvent.Type.Hide:
                self._timer.stop()
                self._last_mouse = None
            elif event.type() == QEvent.Type.MouseMove:
                if self._animations_enabled():
                    self._apply_wind(QPointF(event.position()))
            elif event.type() == QEvent.Type.Leave:
                self._last_mouse = None
        return False

    def _apply_wind(self, mouse_pos: QPointF):
        """El ratón es una corriente: su velocidad empuja a las hojas
        cercanas con caída cuadrática por distancia. Las hojas grandes
        (más 'masa') reaccionan menos."""
        last = self._last_mouse
        self._last_mouse = QPointF(mouse_pos)
        if last is None:
            return
        delta_x = mouse_pos.x() - last.x()
        delta_y = mouse_pos.y() - last.y()
        speed = math.hypot(delta_x, delta_y)
        if speed < 0.5:
            return
        # Limitar ráfagas (saltos de cursor) para que nada salga disparado
        if speed > 80.0:
            scale = 80.0 / speed
            delta_x *= scale
            delta_y *= scale
        width = max(1, self.width())
        height = max(1, self.height())
        radius = 230.0
        for index, leaf in enumerate(self._leaves):
            sway_x = leaf["sway"] * math.sin(self._phase * leaf["sway_speed"] * 2.0 + index)
            leaf_x = (leaf["x"] + sway_x) * width
            leaf_y = leaf["y"] * height
            dist = math.hypot(leaf_x - mouse_pos.x(), leaf_y - mouse_pos.y())
            if dist >= radius:
                continue
            falloff = (1.0 - dist / radius) ** 2
            mass = leaf["size"] / 9.0  # hojas grandes, más inercia
            gain = 0.03 * falloff / mass
            leaf["wx"] += (delta_x / width) * gain * 4.0
            leaf["wy"] += (delta_y / height) * gain * 4.0
            # giro extra al pasar la corriente
            leaf["spin"] += (delta_x - delta_y) * 0.35 * falloff

    # ── partículas ───────────────────────────────────────────────────────

    def _spawn_leaf(self, *, initial: bool = False) -> dict:
        rng = self._rng
        return {
            "x": rng.uniform(0.02, 0.98),
            "y": rng.uniform(0.0, 1.0) if initial else -0.06,
            "speed": rng.uniform(0.018, 0.042),  # fracción de alto / s
            "sway": rng.uniform(0.008, 0.03),
            "sway_speed": rng.uniform(0.35, 1.0),
            "size": rng.uniform(7.0, 13.0),
            "angle": rng.uniform(0.0, 360.0),
            "spin": rng.uniform(-22.0, 22.0),
            "alpha": rng.randint(26, 48),
            # velocidad de viento (impulsos del cursor), decae sola
            "wx": 0.0,
            "wy": 0.0,
        }

    def _advance(self):
        dt = 0.04
        self._phase += dt
        for leaf in self._leaves:
            leaf["y"] += leaf["speed"] * dt + leaf["wy"]
            leaf["x"] += leaf["wx"]
            # la corriente decae: la hoja recupera su deriva tranquila
            # (0.93 → estela más larga, la ráfaga se siente)
            leaf["wx"] *= 0.93
            leaf["wy"] *= 0.93
            leaf["spin"] = max(-60.0, min(60.0, leaf["spin"] * 0.985))
            leaf["angle"] = (leaf["angle"] + leaf["spin"] * dt) % 360.0
            # envoltura horizontal: el viento puede sacarla por un lado
            if leaf["x"] < -0.06:
                leaf["x"] = 1.05
            elif leaf["x"] > 1.06:
                leaf["x"] = -0.05
            if leaf["y"] > 1.08:
                leaf.update(self._spawn_leaf())
            elif leaf["y"] < -0.12:  # el viento la subió demasiado
                leaf["y"] = -0.1
                leaf["wy"] = 0.0
        self.update()

    # ── pintura ──────────────────────────────────────────────────────────

    def paintEvent(self, event):  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = max(1, self.width())
        height = max(1, self.height())
        self._paint_roots(painter, width, height)
        if self._animations_enabled():
            self._paint_leaves(painter, width, height)
        painter.end()

    def _paint_roots(self, painter: QPainter, width: int, height: int):
        """Líneas orgánicas que suben desde la base, casi imperceptibles."""
        pen = QPen(QColor(111, 106, 66, 20), 1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for index, base in enumerate((0.16, 0.5, 0.86)):
            path = QPainterPath(QPointF(width * base, float(height)))
            wobble = (index - 1) * 0.06
            path.cubicTo(
                QPointF(width * (base + wobble), height * 0.72),
                QPointF(width * (base - wobble * 1.4), height * 0.46),
                QPointF(width * (base + wobble * 0.6), height * 0.18),
            )
            painter.drawPath(path)
            # ramificación secundaria
            branch = QPainterPath(QPointF(width * base, height * 0.62))
            branch.quadTo(
                QPointF(width * (base + 0.05 + wobble), height * 0.5),
                QPointF(width * (base + 0.09 + wobble), height * 0.34),
            )
            painter.drawPath(branch)

    def _paint_leaves(self, painter: QPainter, width: int, height: int):
        painter.setPen(Qt.PenStyle.NoPen)
        for index, leaf in enumerate(self._leaves):
            sway_x = leaf["sway"] * math.sin(self._phase * leaf["sway_speed"] * 2.0 + index)
            x = (leaf["x"] + sway_x) * width
            y = leaf["y"] * height
            painter.save()
            painter.translate(x, y)
            painter.rotate(leaf["angle"])
            painter.setBrush(QColor(122, 115, 61, leaf["alpha"]))
            size = leaf["size"]
            painter.drawEllipse(QPointF(0.0, 0.0), size, size * 0.42)
            painter.restore()


class HomeNode(QFrame):
    """Soft clickable node for a Dendro product space (BETA 1: Creación)."""

    def __init__(self, title: str, subtitle: str, icon_name: str, tone: str, ctx=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._ctx = ctx
        self.setObjectName("dendroNode")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(230, 230)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._tone = tone
        self._fg_default = ""
        self._bg_default = ""
        self._border_default = ""
        self._apply_tone_style(tone)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)
        layout.addStretch(1)

        self._icon = QLabel()
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("background: transparent; border: none;")
        icon_color = self._fg_default or GOLD
        self._icon.setPixmap(icons.pixmap(icon_name, size=40, color=icon_color))
        layout.addWidget(self._icon)

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(
            f"font-size: 24px; font-weight: 700; color: {self._fg_default}; "
            "font-family: Georgia, 'Courier New', serif; background: transparent; border: none;"
        )
        layout.addWidget(self._title_label)

        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setStyleSheet(
            f"font-size: 13px; color: {INK_SOFT}; background: transparent; border: none;"
        )
        layout.addWidget(self._subtitle_label)

        # Worldbuilding indicator placeholder (hidden by default)
        self._wb_label = QLabel("Capas")
        self._wb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wb_label.setStyleSheet(
            f"font-size: 11px; color: {INK_OLIVE_SOFT}; background: transparent; border: none; "
            "margin-top: 2px;"
        )
        self._wb_label.setVisible(False)
        layout.addWidget(self._wb_label)

        layout.addStretch(1)

        self._hint = QLabel("E N T R A R")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {GOLD_DEEP}; background: transparent; "
            f"border: none; letter-spacing: 3px;"
        )
        layout.addWidget(self._hint)

        # Opacity effect for dimmed state and zoom animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

    def _apply_tone_style(self, tone: str):
        tones = {
            "creation": (SURFACE_HI, GOLD_DEEP, GOLD_SOFT),
            "gallery": ("#F3F5EE", "#6E7B59", "#B5BBA5"),
            "session": ("#F6F1E8", SESSION_INK, SESSION_LINE),
        }
        bg, fg, border = tones.get(tone, tones["creation"])
        self._bg_default = bg
        self._fg_default = fg
        self._border_default = border
        self.setStyleSheet(
            f"QFrame#dendroNode {{ background: {bg}; border: 1px solid {border}; "
            f"border-radius: 36px; }} "
            f"QFrame#dendroNode:hover {{ background: {WHITE}; border: 2px solid {GOLD}; }}"
        )

    def set_dimmed(self, dimmed: bool):
        """Set dimmed/disabled appearance when no project is loaded."""
        if dimmed:
            self._opacity_effect.setOpacity(0.45)
            self._subtitle_label.setText("Abre o crea un proyecto")
        else:
            self._opacity_effect.setOpacity(1.0)

    def set_worldbuilding_indicator(self, active: bool):
        """Show or hide the worldbuilding 'Capas' indicator."""
        self._wb_label.setVisible(active)

    def animate_zoom_in(self, on_finished: Callable):
        """Fade to 0.6 opacity over 250ms, then call on_finished."""
        self._opacity_effect.setOpacity(1.0)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        duration = self._ctx.animation_duration(250) if self._ctx else 250
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.6)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(on_finished)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def animate_restore(self):
        """Restore opacity back to 1.0."""
        self._opacity_effect.setOpacity(0.6)
        anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        duration = self._ctx.animation_duration(200) if self._ctx else 200
        anim.setDuration(duration)
        anim.setStartValue(0.6)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class QuietIconButton(QPushButton):
    """Small grouped action button used on the Home surface.

    When constructed with a glyph only (icon_only=True), renders as a round
    32x32 button with the glyph centred and no text label.
    """

    def __init__(
        self,
        glyph: str = "",
        label: str = "",
        icon_only: bool = False,
        parent: QWidget | None = None,
        *,
        icon_name: str | None = None,
    ):
        if icon_only:
            super().__init__(glyph, parent)
        else:
            super().__init__(f"{glyph} {label}" if label else glyph, parent)
        self._icon_only = icon_only
        self._icon_name = icon_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if icon_only:
            self.setFixedSize(QSize(34, 34))
            self.setStyleSheet(
                f"QPushButton {{ background: {SURFACE_HI}; border: 1px solid {LINE}; "
                f"border-radius: 17px; padding: 0px; color: {INK_SOFT}; font-size: 16px; }} "
                f"QPushButton:hover {{ background: {WHITE}; border: 1px solid {GOLD}; color: {INK_STRONG}; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ background: {SURFACE_HI}; border: 1px solid {LINE}; "
                f"border-radius: 18px; padding: 8px 14px; color: {INK_SOFT}; font-size: 12px; font-weight: 600; }} "
                f"QPushButton:hover {{ background: {WHITE}; border: 1px solid {GOLD}; color: {INK_STRONG}; }}"
            )
        if icon_name:
            icons.set_button_icon(self, icon_name, color=INK_SOFT, size=18 if icon_only else 16)
            # SHIP-02: set_button_icon limpia el texto; un botón con etiqueta la conserva.
            if not icon_only and label:
                self.setText(label)


class _BranchLine(QFrame):
    """Visual connector (thin vertical line) between the cards and a central hub."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(2)
        self.setMinimumHeight(24)
        self.setStyleSheet(f"background: {LINE_MUTED}; border: none;")


class HomeView(QWidget):
    """Dendro home: Creación space + grouped configuration (BETA 1)."""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._callbacks: dict[str, Callable] = {}
        self._current_project_type: str = "otro"
        self._current_worldbuilding: bool = False
        self._project_loaded: bool = False
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget()
        content.setObjectName("dendroHome")
        content.setStyleSheet(
            "QWidget#dendroHome { background: qlineargradient(x1:0,y1:0,x2:0.6,y2:1, "
            "stop:0 #F1EAD9, stop:0.5 #E8E1CF, stop:1 #DBD2BB); }"
        )
        # BETA1-F01: atmósfera (hojas + raíces) detrás de las cards; no
        # intercepta el ratón y se pausa cuando el Home no está visible.
        self._atmosphere = _AtmosphereOverlay(content, ctx=self.ctx)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(64, 42, 64, 34)
        layout.setSpacing(20)

        # ---- Top: title area ----
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self._project_label = QLabel("Dendro")
        self._project_label.setStyleSheet(
            f"font-size: 44px; font-weight: 700; color: {INK_STRONG}; letter-spacing: 0.5px; "
            f"font-family: Georgia, 'Iowan Old Style', serif; background: transparent; border: none;"
        )
        title_box.addWidget(self._project_label)
        self._subtitle_label = QLabel("Un escritorio tranquilo para crear mundos y relatos.")
        self._subtitle_label.setStyleSheet(f"font-size: 14px; color: {INK_SOFT}; background: transparent; border: none;")
        title_box.addWidget(self._subtitle_label)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"font-size: 12px; color: {INK_MUTED}; background: transparent; border: none;")
        title_box.addWidget(self._status_label)
        # PA02: el botón "Continuar con X" se eliminó — el último proyecto se
        # auto-carga al arrancar, así que es redundante.
        # SHIP-02: recientes visibles — ctx.recent_projects se persistía pero no se
        # mostraba; cambiar de proyecto exigía encontrar el panel de proyecto.
        self._recents_title = QLabel("Proyectos recientes")
        self._recents_title.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {INK_MUTED}; letter-spacing: 1px; "
            f"background: transparent; border: none; margin-top: 10px;"
        )
        self._recents_title.setVisible(False)
        title_box.addWidget(self._recents_title)
        self._recents_layout = QVBoxLayout()
        self._recents_layout.setSpacing(2)
        title_box.addLayout(self._recents_layout)
        layout.addLayout(title_box)
        self.refresh_recents()

        # Advanced indicator (kept from original, hidden by default)
        self._advanced_indicator = Badge("Avanzado", "warning")
        self._advanced_indicator.setVisible(False)
        layout.addWidget(self._advanced_indicator)

        layout.addStretch(1)

        # ---- Middle: node cards ----
        # BETA1-A01: only the Creation card is part of the runtime.
        # Gallery/Session cards removed from Home (their workspaces are
        # disconnected from the stack in MainWindow).

        cards_container = QVBoxLayout()
        cards_container.setSpacing(0)
        cards_container.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Horizontal wrapper to centre cards
        cards_row = QHBoxLayout()
        cards_row.addStretch(1)

        cards_col = QVBoxLayout()
        cards_col.setSpacing(0)
        cards_col.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.creation_card = HomeNode(
            "Creación",
            "Grafo, entidades, relaciones y semillas narrativas.",
            "creation",
            "creation",
            ctx=self.ctx,
        )

        self.creation_card.mousePressEvent = lambda event: self._navigate("creation")
        self.creation_card.setToolTip("Entrar en Creación: grafo, hojas, ramas, relaciones y sugerencias IA")

        cards_col.addWidget(self.creation_card, 3)

        cards_row.addLayout(cards_col)
        cards_row.addStretch(1)
        layout.addLayout(cards_row, stretch=4)

        layout.addStretch(1)

        # ---- Bottom: icon-only buttons at corners ----
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)

        # SHIP-02: acciones primarias CON etiqueta — los iconos sueltos eran
        # indescubribles para un usuario nuevo.
        self._btn_config = QuietIconButton(label="Ajustes", icon_name="settings")
        self._btn_config.setToolTip("Apariencia, proveedor de IA y preferencias")
        self._btn_config.clicked.connect(lambda: self._action("config_menu"))
        bottom_row.addWidget(self._btn_config)

        # SHIP-04: identidad — versión y qué es Dendro, siempre a un clic.
        self._btn_about = QuietIconButton("ⓘ", "Acerca de")
        self._btn_about.setToolTip("Versión y créditos de Dendro")
        self._btn_about.clicked.connect(lambda: self._action("about"))
        bottom_row.addWidget(self._btn_about)

        # SHIP-07: el visor de Memoria/wiki del proyecto no tenía ninguna puerta
        # (callback registrado sin disparador). Ahora es alcanzable.
        self._btn_memory = QuietIconButton("❀", "Memoria")
        self._btn_memory.setToolTip("Ver y gestionar la wiki de Memoria del proyecto")
        self._btn_memory.clicked.connect(lambda: self._action("memory_menu"))
        bottom_row.addWidget(self._btn_memory)

        # BETA1-F01: música ambiental — opcional, APAGADA por defecto,
        # control visible y discreto. Si QtMultimedia no está, no aparece.
        self._music = _AmbientMusic() if _HAS_AUDIO else None
        if self._music is not None:
            self._btn_music = QuietIconButton(icon_only=True, icon_name="music")
            self._btn_music.setToolTip("Música ambiental (apagada)")
            self._btn_music.clicked.connect(self._toggle_music)
            bottom_row.addWidget(self._btn_music)

        bottom_row.addStretch(1)

        # WS-D: puerta al proyecto de ejemplo — el asset viaja junto al exe pero no
        # tenía superficie; un primer arranque quedaba en un Home vacío. Oculto hasta
        # que MainWindow confirma que el ejemplo existe (set_sample_available).
        self._btn_sample = QuietIconButton(label="Abrir ejemplo", icon_name="project")
        self._btn_sample.setToolTip("Explora «La Flor de los Almendros», un proyecto de muestra")
        self._btn_sample.clicked.connect(lambda: self._action("open_sample"))
        self._btn_sample.setVisible(False)
        bottom_row.addWidget(self._btn_sample)

        self._btn_project = QuietIconButton(label="Nuevo / abrir proyecto", icon_name="project")
        self._btn_project.setToolTip("Crear un proyecto nuevo o abrir uno existente")
        self._btn_project.clicked.connect(lambda: self._action("project_menu"))
        bottom_row.addWidget(self._btn_project)

        layout.addLayout(bottom_row)

        root.addWidget(make_scroll_area(content))

        # Whole-view fade effect for animate_arrival
        self._fade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fade)
        self._fade.setOpacity(1.0)

    def _branch_line(self) -> QFrame:
        """Return a thin vertical connector line between cards."""
        line = QFrame()
        line.setFixedHeight(18)
        line.setMinimumWidth(2)
        line.setMaximumWidth(60)
        line.setStyleSheet("background: transparent; border: none;")
        # Use a label with a decorative glyph for the branch
        inner = QHBoxLayout(line)
        inner.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("┃")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"font-size: 18px; color: {LINE_MUTED}; background: transparent; border: none;"
        )
        inner.addWidget(lbl)
        return line

    # ------------------------------------------------------------------
    # Dynamic visibility
    # ------------------------------------------------------------------

    def update_project_visibility(self, project_type: str | None, worldbuilding_active: bool):
        """Update card indicators based on project metadata.

        BETA1-A01: only the Creation card exists on Home, so project_type no
        longer toggles card visibility. Rules kept:
          - worldbuilding_active → show "🌐 Capas" on creation card
          - No project loaded → card visible but dimmed
        """
        self._current_project_type = project_type or "otro"
        self._current_worldbuilding = worldbuilding_active

        # Worldbuilding indicator on creation card
        self.creation_card.set_worldbuilding_indicator(worldbuilding_active)

        # If no project is loaded, dim the card
        self.creation_card.set_dimmed(not self._project_loaded)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def register_callback(self, name: str, callback: Callable):
        self._callbacks[name] = callback

    def set_sample_available(self, available: bool) -> None:
        """WS-D: muestra «Abrir ejemplo» solo si el proyecto de muestra está presente."""
        if hasattr(self, "_btn_sample"):
            self._btn_sample.setVisible(bool(available))

    def refresh_recents(self) -> None:
        """SHIP-02: repuebla la lista de proyectos recientes (hasta 5, solo existentes)."""
        while self._recents_layout.count():
            item = self._recents_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        recents = [p for p in (self.ctx.recent_projects or []) if Path(p).exists()][:5]
        self._recents_title.setVisible(bool(recents))
        for path in recents:
            btn = QPushButton(f"↳ {Path(path).stem}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(path)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; text-align: left; "
                f"color: {INK_SOFT}; font-size: 13px; padding: 2px 0px; }} "
                f"QPushButton:hover {{ color: {INK_STRONG}; text-decoration: underline; }}"
            )
            btn.clicked.connect(lambda _=False, p=path: self._open_recent(p))
            self._recents_layout.addWidget(btn)

    def _open_recent(self, path: str) -> None:
        cb = self._callbacks.get("open_recent")
        if cb:
            cb(path)

    def set_advanced_mode(self, enabled: bool):
        # T05: Always hidden from UI — advanced mode kept internal only
        self._advanced_indicator.setVisible(False)

    # ------------------------------------------------------------------
    # Animations
    # ------------------------------------------------------------------

    def animate_arrival(self):
        """Restore all cards to full visibility (called when returning to Home).

        We reset the parent fade to 1.0 immediately (no animation) to avoid
        compounding opacity effects with the MainWindow stack-level animation
        and the per-card opacity effects. Cards that were left at 0.6 opacity
        from a previous zoom-in are restored to full opacity directly.
        """
        # Reset parent fade immediately — the MainWindow stack animation
        # already provides a fade-in; an additional parent fade would compound
        # (multiplicative) with card-level effects making cards invisible.
        if hasattr(self, '_fade') and self._fade:
            self._fade.setOpacity(1.0)

        # Force all visible cards to full opacity immediately.
        # Cards may be at 0.6 from a previous animate_zoom_in that never
        # finished its restore cycle.
        for card in (self.creation_card,):
            if card.isVisible() and hasattr(card, '_opacity_effect'):
                card._opacity_effect.setOpacity(1.0)

    def _animate_card_zoom(self, card: HomeNode, space: str):
        """Zoom/fade the card, then navigate once the animation finishes."""
        card.animate_zoom_in(lambda: self._do_navigate(space))

    def _do_navigate(self, space: str):
        cb = self._callbacks.get(f"navigate_{space}")
        if cb:
            cb()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate(self, space: str):
        # BETA1-A01: only Creation is navigable from Home
        if space == "creation" and not self._project_loaded:
            self._status_label.setText("Abre o crea un proyecto para entrar en Creación.")
            return
        card = {
            "creation": self.creation_card,
        }.get(space)
        if card and card.isVisible():
            self._animate_card_zoom(card, space)
        else:
            # Fallback: navigate immediately
            self._do_navigate(space)

    def _action(self, action: str):
        cb = self._callbacks.get(action)
        if cb:
            cb()

    def _toggle_music(self):
        """BETA1-F01: alternar la música ambiental (síntesis local)."""
        if self._music is None:
            return
        try:
            playing = self._music.toggle()
        except Exception as exc:  # noqa: BLE001 — el audio jamás rompe el Home
            self.ctx.log("error", f"Música ambiental no disponible: {exc}")
            return
        self._btn_music.setToolTip(
            "Música ambiental (sonando — click para apagar)" if playing
            else "Música ambiental (apagada)"
        )
        # marca visual del estado: el icono se tiñe de oro al sonar.
        icons.set_button_icon(
            self._btn_music, "music", color=GOLD if playing else INK_SOFT, size=18
        )

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self):
        pc = self.ctx.project_controller
        p = pc.ps.active_project if pc else None

        if p is None:
            self._project_loaded = False
            self._project_label.setText("Dendro")
            self._subtitle_label.setText("Un escritorio tranquilo para crear mundos y relatos.")
            self._status_label.setText("Abre o crea un proyecto para comenzar.")
            self.update_project_visibility(None, False)
            return

        self._project_loaded = True
        name = getattr(p, "name", "Sin nombre") or "Sin nombre"
        project_type = getattr(p, "project_type", "otro") or "otro"
        worldbuilding_active = getattr(p, "worldbuilding_active", False) or False

        self._project_label.setText("Dendro")
        self._subtitle_label.setText(name)
        self._status_label.setText("Proyecto activo")
        self.update_project_visibility(project_type, worldbuilding_active)
