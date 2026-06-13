"""BETA1-G08 — Atmósfera de fondo para los lienzos (concéntrico y cronológico).

Hojas a la deriva mecidas por una brisa lentísima. MUY sutil y de fondo: se
dibuja en ``drawBackground`` (detrás de TODO) y en coordenadas de viewport, así
que no se mueve con el zoom ni el pan y apenas distrae. Decorativa y barata
(~11 elipses translúcidas, ~18 fps). Respeta el movimiento reducido del ctx.

Uso desde una QGraphicsView::

    self._atmo = CanvasAtmosphere(self, ctx=None)
    # en drawBackground(painter, rect):  super(); self._atmo.paint(painter)
    # en showEvent: self._atmo.start()   ·  en hideEvent: self._atmo.stop()
"""
from __future__ import annotations

import math
import random
from typing import Any

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter

# Tono cálido (savia/oliva) — siempre muy translúcido
_LEAF_RGB = (150, 139, 95)


class CanvasAtmosphere:
    """Estado + pintura de las hojas de fondo de un lienzo."""

    def __init__(self, view, *, ctx: Any = None, count: int = 11):
        self._view = view
        self._ctx = ctx
        self._count = max(1, int(count))
        self._rng = random.Random(11)
        self._leaves: list[dict] = []
        self._phase = 0.0
        self._timer = QTimer(view)
        self._timer.setInterval(55)  # ~18 fps: brisa, no carreras
        self._timer.timeout.connect(self._tick)

    # ── configuración ────────────────────────────────────────────────────

    def set_context(self, ctx: Any) -> None:
        self._ctx = ctx

    def _motion_enabled(self) -> bool:
        if self._ctx is None:
            return True
        try:
            return self._ctx.animation_duration(100) > 0
        except Exception:  # noqa: BLE001
            return True

    # ── ciclo de vida ────────────────────────────────────────────────────

    def start(self) -> None:
        self._ensure()
        if self._motion_enabled() and not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    # ── simulación ───────────────────────────────────────────────────────

    def _spawn(self) -> dict:
        return {
            "x": self._rng.uniform(0.0, 1.0),
            "y": self._rng.uniform(0.0, 1.0),
            "size": self._rng.uniform(5.0, 11.0),
            "rot": self._rng.uniform(0.0, math.tau),
            "vrot": self._rng.uniform(-0.010, 0.010),
            "drift": self._rng.uniform(0.6, 1.5),
            "sway": self._rng.uniform(0.0, math.tau),
            "alpha": self._rng.uniform(0.05, 0.13),
        }

    def _ensure(self) -> None:
        if not self._leaves:
            self._leaves = [self._spawn() for _ in range(self._count)]

    def _tick(self) -> None:
        self._ensure()
        self._phase += 0.012
        # Brisa lenta hacia la derecha, con vaivén global muy suave.
        wind = 0.00020 * math.sin(self._phase) + 0.00009
        for leaf in self._leaves:
            leaf["sway"] += 0.02
            leaf["x"] += leaf["drift"] * wind + 0.00006 * math.sin(leaf["sway"])
            leaf["y"] += leaf["drift"] * 0.00016 + 0.00004 * math.cos(leaf["sway"] * 0.7)
            leaf["rot"] += leaf["vrot"]
            # Reciclaje al salir por la derecha o por abajo.
            if leaf["x"] > 1.06:
                leaf["x"] = -0.06
                leaf["y"] = self._rng.uniform(0.0, 1.0)
            if leaf["y"] > 1.06:
                leaf["y"] = -0.06
                leaf["x"] = self._rng.uniform(0.0, 1.0)
        viewport = self._view.viewport()
        if viewport is not None:
            viewport.update()

    # ── pintura (en coordenadas de viewport) ─────────────────────────────

    def paint(self, painter: QPainter) -> None:
        viewport = self._view.viewport()
        if viewport is None:
            return
        width, height = viewport.width(), viewport.height()
        if width <= 0 or height <= 0:
            return
        self._ensure()
        painter.save()
        painter.resetTransform()  # de coords de escena a píxeles de viewport
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        for leaf in self._leaves:
            x = leaf["x"] * width
            y = leaf["y"] * height
            color = QColor(_LEAF_RGB[0], _LEAF_RGB[1], _LEAF_RGB[2], int(leaf["alpha"] * 255))
            painter.setBrush(color)
            painter.save()
            painter.translate(x, y)
            painter.rotate(math.degrees(leaf["rot"]))
            size = leaf["size"]
            painter.drawEllipse(QPointF(0.0, 0.0), size, size * 0.42)
            painter.restore()
        painter.restore()


__all__ = ["CanvasAtmosphere"]
