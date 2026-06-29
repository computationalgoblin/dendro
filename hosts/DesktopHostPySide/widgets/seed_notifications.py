"""Notificaciones de semillas (Fase A): círculos GOLD palpitantes abajo-derecha.

Sustituyen al indicador «Tareas N» y al panel de jobs. Cuando un job IA culmina,
por cada candidato creado brota un círculo del color del botón «Crear» que palpita
hasta que el usuario lo revisa (acepta/rechaza). Al pulsarlo se emite
``reviewRequested(candidate_id)`` para abrir el panel de revisión. Hay una variante
de error (job fallido) que se descarta al pulsarla.

El palpitar se pinta en ``paintEvent`` (sin QGraphicsEffect, que vacía widgets
dinámicos). La capa se ancla a la esquina inferior derecha del padre y se reubica
al redimensionar (patrón de eventFilter, como _AtmosphereOverlay/ModalOverlay).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    INK_SOFT,
    SURFACE_HI,
    TICK_INTERVAL,
)

_ERROR_COLOR = "#C0392B"
_DOT_DIAMETER = 34
_MARGIN = 18


class SeedNotification(QWidget):
    """Un círculo palpitante. Emite ``clicked(candidate_id)`` al pulsarlo."""

    clicked = Signal(str)

    def __init__(
        self,
        candidate_id: str,
        label: str = "",
        *,
        kind: str = "candidate",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.candidate_id = candidate_id
        self.kind = kind
        self._accent = QColor(_ERROR_COLOR if kind == "error" else GOLD)
        self._phase = 0.0
        # SEM02: estado de marchitado (al rechazar): encoge y se apaga.
        self._withering = False
        self._wither_t = 0.0
        self._on_withered = None
        self.setFixedSize(_DOT_DIAMETER + 8, _DOT_DIAMETER + 8)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if label:
            self.setToolTip(label)
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL)  # cadencia única del design system
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        if self._withering:
            self._wither_t += 0.14  # ~0.4 s de marchitado
            if self._wither_t >= 1.0:
                self._timer.stop()
                cb, self._on_withered = self._on_withered, None
                if cb is not None:
                    cb()
                return
            self.update()
            return
        self._phase = (self._phase + 0.12) % (2.0 * math.pi)
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def start_wither(self, on_done=None) -> None:
        """Marchita el círculo (encoge + se apaga) y al terminar llama on_done."""
        if self._withering:
            return
        self._withering = True
        self._wither_t = 0.0
        self._on_withered = on_done
        if not self._timer.isActive():
            self._timer.start()

    def mousePressEvent(self, event):  # noqa: N802 (Qt signature)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.candidate_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, _event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        cx, cy = rect.width() / 2.0, rect.height() / 2.0

        # SEM02: marchitado — disco gris que encoge y se desvanece.
        if self._withering:
            t = min(1.0, self._wither_t)
            core_r = (_DOT_DIAMETER / 2.0 - 1.0) * (1.0 - 0.55 * t)
            faded = QColor(INK_SOFT)
            faded.setAlpha(int(200 * (1.0 - t)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(faded))
            painter.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))
            return

        pulse = 0.5 + 0.5 * math.sin(self._phase)  # 0..1

        # Halo palpitante (anillo difuso que crece y se atenúa).
        halo_r = (_DOT_DIAMETER / 2.0) + 3.0 * pulse
        halo = QColor(self._accent)
        halo.setAlpha(int(40 + 50 * pulse))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(QRectF(cx - halo_r, cy - halo_r, halo_r * 2, halo_r * 2))

        # Disco principal.
        core_r = _DOT_DIAMETER / 2.0 - 1.0
        painter.setBrush(QBrush(self._accent))
        painter.setPen(QPen(QColor(SURFACE_HI), 1.5))
        painter.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))

        # Marca interior (semilla / aspa de error).
        painter.setPen(QPen(QColor(SURFACE_HI), 2.0))
        if self.kind == "error":
            o = core_r * 0.45
            painter.drawLine(int(cx - o), int(cy - o), int(cx + o), int(cy + o))
            painter.drawLine(int(cx - o), int(cy + o), int(cx + o), int(cy - o))
        else:
            painter.setBrush(QBrush(QColor(INK_SOFT)))
            seed_r = core_r * 0.28
            painter.drawEllipse(QRectF(cx - seed_r, cy - seed_r, seed_r * 2, seed_r * 2))


class SeedNotificationLayer(QWidget):
    """Pila de notificaciones anclada a la esquina inferior derecha del padre."""

    reviewRequested = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("seedNotificationLayer")
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("QWidget#seedNotificationLayer { background: transparent; }")
        self._notifications: dict[str, SeedNotification] = {}
        self._bottom_offset = 0  # px extra para librar la command bar inferior
        # SEM04: si el host fija un callback, él ancla la capa (encima del cluster
        # de botones derecho) en vez del anclaje propio a la esquina, para no
        # solapar los botones ni perder los clics.
        self._reflow_cb = None
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(8)
        self._box.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        if parent is not None:
            parent.installEventFilter(self)
        self.hide()

    # ── API ────────────────────────────────────────────────────────────────

    @property
    def notifications(self) -> dict[str, SeedNotification]:
        return dict(self._notifications)

    def add(self, candidate_id: str, label: str = "", *, kind: str = "candidate") -> None:
        if candidate_id in self._notifications:
            return
        dot = SeedNotification(candidate_id, label, kind=kind, parent=self)
        dot.clicked.connect(self._on_clicked)
        self._notifications[candidate_id] = dot
        self._box.addWidget(dot, alignment=Qt.AlignmentFlag.AlignRight)
        self._reflow()

    def remove(self, candidate_id: str, *, withered: bool = False) -> None:
        # SEM02: ``withered`` reproduce la animación de marchitado antes de quitar
        # la notificación (al rechazar el candidato). Las de error se quitan ya.
        dot = self._notifications.get(candidate_id)
        if dot is None:
            return
        if withered and dot.kind != "error":
            dot.start_wither(lambda cid=candidate_id: self._finalize_remove(cid))
            return
        self._finalize_remove(candidate_id)

    def _finalize_remove(self, candidate_id: str) -> None:
        dot = self._notifications.pop(candidate_id, None)
        if dot is None:
            return
        dot.stop()
        self._box.removeWidget(dot)
        dot.setParent(None)
        dot.deleteLater()
        self._reflow()

    def clear(self) -> None:
        for candidate_id in list(self._notifications):
            self.remove(candidate_id)

    def has(self, candidate_id: str) -> bool:
        return candidate_id in self._notifications

    def set_bottom_offset(self, px: int) -> None:
        """Margen inferior extra (p. ej. para no solapar la command bar)."""
        self._bottom_offset = max(0, int(px))
        self._reposition()

    def set_reflow_callback(self, cb) -> None:
        """SEM04: el host se encarga de anclar la capa (encima del cluster derecho)."""
        self._reflow_cb = cb

    def reanchor(self) -> None:
        """Recoloca la capa; el host la llama tras mover sus clusters."""
        self.adjustSize()
        if self._notifications:
            self.show()
            self.raise_()  # por encima de los clusters de botones

    # ── geometría ────────────────────────────────────────────────────────

    def _on_clicked(self, candidate_id: str) -> None:
        # Las notificaciones de candidato abren su revisión; las de error se
        # descartan al pulsarlas.
        dot = self._notifications.get(candidate_id)
        if dot is not None and dot.kind == "error":
            self.remove(candidate_id)
            return
        self.reviewRequested.emit(candidate_id)

    def _reflow(self) -> None:
        if not self._notifications:
            self.hide()
            return
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()

    def _reposition(self) -> None:
        # SEM04: el host ancla (encima del cluster derecho) si fijó callback;
        # si no, anclaje propio a la esquina inferior derecha (fallback/tests).
        if self._reflow_cb is not None:
            self._reflow_cb()
        else:
            self._anchor()

    def _anchor(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        x = parent.width() - self.width() - _MARGIN
        y = parent.height() - self.height() - _MARGIN - self._bottom_offset
        self.move(max(0, x), max(0, y))

    def eventFilter(self, obj, event):  # noqa: N802 (Qt signature)
        if obj is self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
        ):
            self._reposition()
        return super().eventFilter(obj, event)


__all__ = ["SeedNotificationLayer", "SeedNotification"]
