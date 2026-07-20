"""UI2-08 / BETA2-FOCO-37: franja de cultivo persistente — pie fino de la tarjeta.

Resumen mínimo del jardín de la entidad centrada (punto de estado + micro-barras de
métricas) MÁS los controles de riego minimalistas (Regar/Secar/Cultivar como iconos,
estilo del viejo rail). El punto PALPITA cuando falta regar. El chip verboso «Regar
ahora» se retiró (FOCO-37); «Sugerir X» vive ahora en el Cuaderno de Cultivo.
Sin QGraphicsEffect (regla del repo): el pulso se pinta en ``paintEvent``.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QWidget,
)

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK_MUTED,
    INK_SOFT,
    LINE_SOFT,
    TICK_INTERVAL,
)
from hosts.DesktopHostPySide.widgets.foco.cultivation_notebook import (
    _METRIC_ICONS,
    _METRICS,
    _STATUS_STYLES,
)

# (tool_id, icono SVG, tooltip). Réplica de los controles del viejo rail.
_ACTION_SPECS = (
    ("water", "tool_water", "Regar (diagnóstico IA de la entidad en foco)"),
    ("dry", "tool_dry", "Secar (sacar del ciclo de riego, sin IA)"),
    ("cultivate", "tool_cultivate", "Cultivar (volver al ciclo de riego, sin IA)"),
)
_ICON_BTN_STYLE = (
    "QPushButton { background: transparent; border: 1px solid transparent; "
    "border-radius: 12px; padding: 0; } "
    f"QPushButton:hover:enabled {{ background: {GOLD_TINT}; border: 1px solid {GOLD_SOFT}; }} "
    "QPushButton:disabled { background: transparent; }"
)


class _PulseDot(QWidget):
    """Punto de estado que PALPITA cuando falta regar (sin QGraphicsEffect)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor(INK_MUTED)
        self._pulsing = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL)
        self._timer.timeout.connect(self._tick)

    def set_state(self, color: str, *, pulsing: bool) -> None:
        self._color = QColor(color)
        self._pulsing = bool(pulsing)
        if self._pulsing and not self._timer.isActive():
            self._timer.start()
        elif not self._pulsing and self._timer.isActive():
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.14) % (2.0 * math.pi)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt signature)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        cx, cy = rect.width() / 2.0, rect.height() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        if self._pulsing:
            pulse = 0.5 + 0.5 * math.sin(self._phase)
            halo = QColor(self._color)
            halo.setAlpha(int(40 + 60 * pulse))
            halo_r = 5.0 + 1.5 * pulse
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(QRectF(cx - halo_r, cy - halo_r, halo_r * 2, halo_r * 2))
        painter.setBrush(QBrush(QColor(self._color)))
        painter.drawEllipse(QRectF(cx - 4.0, cy - 4.0, 8.0, 8.0))


class CultivationStrip(QFrame):
    """Una línea discreta: ◉ estado · ▂▂▂▂ métricas · [regar] [secar] [cultivar]."""

    waterClicked = Signal()  # noqa: N815 — convención Qt de señales
    dryClicked = Signal()  # noqa: N815 — convención Qt de señales
    cultivateClicked = Signal()  # noqa: N815 — convención Qt de señales

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cultivationStrip")
        self.setStyleSheet(
            "QFrame#cultivationStrip { background: transparent; "
            f"border: none; border-top: 1px solid {LINE_SOFT}; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 6, 2, 0)
        row.setSpacing(8)

        self.status_dot = _PulseDot(self)
        row.addWidget(self.status_dot)

        self.bars: dict[str, QProgressBar] = {}
        self._labels = dict(_METRICS)
        for metric_key, _label in _METRICS:
            # UI2-15: icono SVG identificador delante de cada micro-barra.
            glyph = QLabel(self)
            glyph.setPixmap(icons.pixmap(_METRIC_ICONS[metric_key], size=12, color=INK_MUTED))
            glyph.setFixedSize(14, 14)
            glyph.setStyleSheet("background: transparent; border: none;")
            glyph.setToolTip(self._labels[metric_key])
            row.addWidget(glyph)
            bar = QProgressBar(self)
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedSize(36, 6)
            bar.setStyleSheet(
                f"QProgressBar {{ background: {GOLD_TINT}; border: 1px solid {LINE_SOFT}; "
                "border-radius: 3px; } "
                f"QProgressBar::chunk {{ background: {GOLD}; border-radius: 3px; }}"
            )
            row.addWidget(bar)
            self.bars[metric_key] = bar
        row.addStretch(1)

        # BETA2-FOCO-37: controles de riego minimalistas (Regar/Secar/Cultivar).
        self._action_buttons: dict[str, QPushButton] = {}
        signal_of = {
            "water": self.waterClicked,
            "dry": self.dryClicked,
            "cultivate": self.cultivateClicked,
        }
        for tool_id, icon_name, tooltip in _ACTION_SPECS:
            btn = QPushButton(self)
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            color = GOLD_DEEP if tool_id == "water" else INK_SOFT
            btn.setIcon(icons.icon(icon_name, color=color, size=15))
            btn.setStyleSheet(_ICON_BTN_STYLE)
            btn.clicked.connect(signal_of[tool_id].emit)
            self._action_buttons[tool_id] = btn
            row.addWidget(btn)

        self._is_running = False
        self._status = ""
        self._is_ghost = False
        self.hide()

    def set_watering_running(self, running: bool) -> None:
        """Deshabilita «Regar» mientras se riega la central (evita relanzar)."""
        self._is_running = bool(running)
        self._sync_actions()

    def _sync_actions(self) -> None:
        secada = self._status == "secada"
        waterable = not secada and not self._is_ghost
        self._action_buttons["water"].setEnabled(waterable and not self._is_running)
        self._action_buttons["dry"].setEnabled(not secada and not self._is_ghost)
        # Cultivar solo tiene sentido para reactivar una entidad secada.
        self._action_buttons["cultivate"].setEnabled(secada)

    def set_report(self, report, *, is_ghost: bool = False) -> None:
        """Refresca punto (con pulso si falta regar), micro-barras y controles."""
        self._status = str(getattr(report, "status", "") or "")
        self._is_ghost = bool(is_ghost)
        color, status_text = _STATUS_STYLES.get(
            self._status, (INK_MUTED, self._status or "Sin lectura")
        )
        # BETA2-FOCO-37: el punto PALPITA cuando falta regar (y no es fantasma).
        self.status_dot.set_state(
            color, pulsing=self._status == "falta_regar" and not self._is_ghost
        )
        self.status_dot.setToolTip(f"Estado del jardín: {status_text}")
        latest = getattr(report, "latest", None)
        stale = bool(getattr(report, "stale", False))
        for metric_key, bar in self.bars.items():
            score = None if latest is None else latest.scores.get(metric_key)
            label = self._labels.get(metric_key, metric_key)
            if score is None:
                bar.setValue(0)
                bar.setEnabled(False)
                bar.setToolTip(f"{label}: sin lectura (riega para diagnosticar)")
                continue
            bar.setValue(int(score))
            bar.setEnabled(not stale and self._status != "secada")
            explanation = (getattr(latest, "metric_explanations", {}) or {}).get(metric_key, "")
            suffix = " · lectura antigua" if stale else ""
            tooltip = f"{label}: {int(score)}%{suffix}"
            if explanation:
                tooltip = f"{tooltip}\n{explanation}"
            bar.setToolTip(tooltip)
        self._sync_actions()


__all__ = ["CultivationStrip"]
