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

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QMenu, QPushButton, QVBoxLayout, QWidget

from hosts.DesktopHostPySide.widgets import icons
from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_DEEP,
    GOLD_PRESS,
    INK_INVERSE,
    INK_SOFT,
    SURFACE_HI,
    TICK_INTERVAL,
)

_ERROR_COLOR = "#C0392B"
_DOT_DIAMETER = 34
_MARGIN = 18
_PILL_HEIGHT = 30  # BETA2-PULIDO-01: ambas píldoras (🌱/💧) miden lo mismo


def _pill_style(base: str, hover: str) -> str:
    """BETA2-PULIDO-01: QSS único de las píldoras del rincón (🌱 y 💧) —
    mismo radio, padding, tipografía y feedback de hover/pressed."""
    return (
        f"QPushButton {{ background: {base}; color: {INK_INVERSE}; border: none; "
        f"border-radius: 15px; padding: 0px 14px; font-weight: 700; font-size: 12px; }} "
        f"QPushButton:hover {{ background: {hover}; }} "
        f"QPushButton:pressed {{ background: {GOLD_PRESS}; }}"
    )


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
        # BETA2-FOCO-34: el aviso «cultivo» (entidad regada, revisar) usa el tono
        # del riego (GOLD_DEEP) para leerse como parte del jardín, no como semilla.
        if kind == "error":
            accent = _ERROR_COLOR
        elif kind == "cultivo":
            accent = GOLD_DEEP
        else:
            accent = GOLD
        self._accent = QColor(accent)
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

        # Marca interior (semilla / aspa de error / gota de cultivo).
        painter.setPen(QPen(QColor(SURFACE_HI), 2.0))
        if self.kind == "error":
            o = core_r * 0.45
            painter.drawLine(int(cx - o), int(cy - o), int(cx + o), int(cy + o))
            painter.drawLine(int(cx - o), int(cy + o), int(cx + o), int(cy - o))
        elif self.kind == "cultivo":
            # Gota (riego): revisar la entidad actualizada en Cultivo.
            r = core_r * 0.5
            path = QPainterPath()
            path.moveTo(cx, cy - r)
            path.cubicTo(cx + r * 1.05, cy, cx + r * 0.7, cy + r, cx, cy + r)
            path.cubicTo(cx - r * 0.7, cy + r, cx - r * 1.05, cy, cx, cy - r)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(SURFACE_HI)))
            painter.drawPath(path)
        else:
            painter.setBrush(QBrush(QColor(INK_SOFT)))
            seed_r = core_r * 0.28
            painter.drawEllipse(QRectF(cx - seed_r, cy - seed_r, seed_r * 2, seed_r * 2))


class SeedNotificationLayer(QWidget):
    """Pila de notificaciones anclada a la esquina inferior derecha del padre."""

    reviewRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    # BETA2-JARDIN-03: recorrido de sedientas — emite la siguiente entidad por
    # regar (la más antigua primero). UI2-04: vive en el clic derecho del badge.
    thirstyRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    # UI2-04: clic primario del badge — regar TODAS las sedientas (el workspace
    # pasa la lista por la autorización visible antes de lanzar el lote).
    waterAllRequested = Signal(list)  # noqa: N815 — convención Qt de señales
    # BETA2-FOCO-34: clic en un aviso «cultivo» — enfocar la entidad regada y
    # abrir su pestaña Cultivo para revisar el diagnóstico recién generado.
    cultivoReviewRequested = Signal(str)  # noqa: N815 — convención Qt de señales
    # BETA2-FOCO-35: clic en el badge «Regando x/y» durante un lote — pedir el
    # popover de detalle del progreso (en vez de lanzar otro riego).
    waterProgressRequested = Signal()  # noqa: N815 — convención Qt de señales

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
        # BETA2-UX-07: los candidatos ya NO germinan como N dots aquí (esa es la
        # superficie primaria del lienzo). El rincón muestra UN badge de conteo
        # sutil; los objetos SeedNotification se conservan ocultos (API + wither).
        self._count_badge = QPushButton(self)
        self._count_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._count_badge.setStyleSheet(_pill_style(GOLD, GOLD_DEEP))
        self._count_badge.clicked.connect(self._on_count_clicked)
        self._count_badge.hide()
        self._box.addWidget(self._count_badge, alignment=Qt.AlignmentFlag.AlignRight)
        # BETA2-FOCO-36: badge de avisos de Cultivo AGREGADOS (un contador en vez
        # de un dot por entidad regada). Clic → revisar el más antiguo.
        self._cultivo_badge = QPushButton(self)
        self._cultivo_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cultivo_badge.setStyleSheet(_pill_style(GOLD_DEEP, GOLD))
        self._cultivo_badge.clicked.connect(self._on_cultivo_clicked)
        self._cultivo_badge.hide()
        self._box.addWidget(self._cultivo_badge, alignment=Qt.AlignmentFlag.AlignRight)
        # BETA2-JARDIN-03: badge hermano «💧 N» — salud global del jardín
        # (entidades por regar). Mismo lenguaje de píldora, tono más profundo.
        self._thirsty_ids: list[str] = []
        # BETA2-FOCO-34: regables totales (falta_regar + regada). El badge no
        # desaparece tras regar; con solo regadas muestra «Regar de nuevo».
        self._waterable_ids: list[str] = []
        self._thirsty_idx = 0
        self._watering_done = 0
        self._watering_total = 0
        self._water_badge = QPushButton(self)
        self._water_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._water_badge.setStyleSheet(_pill_style(GOLD_DEEP, GOLD))
        # UI2-04: gota SVG teñida del sistema de iconos (adiós emoji 💧 azul,
        # que dependía de la fuente del sistema y rompía la paleta).
        self._water_badge.setIcon(icons.icon("tool_water", color=INK_INVERSE, size=14))
        self._water_badge.setIconSize(QSize(14, 14))
        self._water_badge.clicked.connect(self._on_water_clicked)
        self._water_badge.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._water_badge.customContextMenuRequested.connect(self._on_water_menu)
        self._water_badge.hide()
        self._box.addWidget(self._water_badge, alignment=Qt.AlignmentFlag.AlignRight)
        # BETA2-PULIDO-01: ranuras ESTABLES — misma altura fija y conservar el
        # hueco al ocultarse: 🌱 vive siempre en la ranura superior y 💧 en la
        # inferior, así la esquina no «baila» al aparecer/desaparecer una.
        for badge in (self._count_badge, self._cultivo_badge, self._water_badge):
            badge.setFixedHeight(_PILL_HEIGHT)
            policy = badge.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            badge.setSizePolicy(policy)
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
        if kind == "error":
            # Los errores (transitorios) siguen como dot VISIBLE que se descarta
            # al pulsarlo.
            self._box.addWidget(dot, alignment=Qt.AlignmentFlag.AlignRight)
        else:
            # BETA2-UX-07/FOCO-36: candidatos (🌱) y avisos de cultivo (🔔) se
            # agregan en su badge de conteo; el objeto se conserva OCULTO.
            dot.hide()
        self._sync_count()
        self._sync_cultivo_badge()
        self._reflow()

    def _candidate_ids(self) -> list[str]:
        # Solo semillas: ni errores ni avisos de cultivo cuentan en el badge 🌱.
        return [cid for cid, dot in self._notifications.items() if dot.kind == "candidate"]

    def _cultivo_ids(self) -> list[str]:
        # BETA2-FOCO-36: entidades regadas pendientes de revisar en Cultivo.
        return [cid for cid, dot in self._notifications.items() if dot.kind == "cultivo"]

    def _sync_count(self) -> None:
        ids = self._candidate_ids()
        n = len(ids)
        if n:
            self._count_badge.setText(f"🌱 {n} " + ("semilla" if n == 1 else "semillas"))
            self._count_badge.setToolTip(
                "Semillas pendientes de revisar (germinan en el lienzo) — clic para abrir"
            )
            self._count_badge.show()
        else:
            self._count_badge.hide()

    def _on_count_clicked(self) -> None:
        # BETA2-UX-07: una sola entrada — abre la revisión de la más antigua; el
        # resto se revisa en la superficie primaria (semillas del lienzo).
        ids = self._candidate_ids()
        if ids:
            self.reviewRequested.emit(ids[0])

    def _sync_cultivo_badge(self) -> None:
        # BETA2-FOCO-36: un solo badge con contador para todos los avisos de Cultivo.
        n = len(self._cultivo_ids())
        if n:
            self._cultivo_badge.setText(f"🔔 {n} por revisar")
            self._cultivo_badge.setToolTip(
                "Entidades regadas por revisar en Cultivo — clic abre la más antigua"
            )
            self._cultivo_badge.show()
        else:
            self._cultivo_badge.hide()

    def _on_cultivo_clicked(self) -> None:
        # BETA2-FOCO-36: abre la revisión de la entidad regada más antigua y la
        # descarta (decrementa el contador).
        ids = self._cultivo_ids()
        if ids:
            oldest = ids[0]
            self.cultivoReviewRequested.emit(oldest)
            self.remove(oldest)

    # ── BETA2-JARDIN-03: sedientas ─────────────────────────────────────────

    @property
    def thirsty_ids(self) -> list[str]:
        return list(self._thirsty_ids)

    def set_thirsty(self, entity_ids: list[str]) -> None:
        """Compat: sedientas == regables (comportamiento previo a FOCO-34)."""
        self.set_waterable(entity_ids, entity_ids)

    def set_waterable(self, thirsty_ids: list[str], waterable_ids: list[str]) -> None:
        """BETA2-FOCO-34: fija sedientas (``falta_regar``) y regables totales
        (incluye ``regada``). El badge no desaparece tras regar: con solo regadas
        muestra «Regar de nuevo». El índice del recorrido sobrevive a refrescos."""
        self._thirsty_ids = [str(entity_id) for entity_id in (thirsty_ids or []) if entity_id]
        self._waterable_ids = [str(entity_id) for entity_id in (waterable_ids or []) if entity_id]
        if self._thirsty_ids:
            self._thirsty_idx %= len(self._thirsty_ids)
        else:
            self._thirsty_idx = 0
        self._sync_water_badge()
        self._reflow()

    def set_watering_progress(self, done: int, total: int) -> None:
        """UI2-04: progreso del lote de riego en la propia píldora («Regando
        D/T…», deshabilitada); (0, 0) restaura el conteo de sedientas."""
        self._watering_done = max(0, int(done))
        self._watering_total = max(0, int(total))
        self._sync_water_badge()
        self._reflow()

    def _sync_water_badge(self) -> None:
        if self._watering_total > 0:
            self._water_badge.setText(
                f"Regando {self._watering_done}/{self._watering_total}…"
            )
            # BETA2-FOCO-35: clicable en lote → abre el popover de progreso.
            self._water_badge.setToolTip("Riego en curso — clic para ver el detalle del lote")
            self._water_badge.setEnabled(True)
            self._water_badge.show()
            return
        self._water_badge.setEnabled(True)
        if self._thirsty_ids:
            n = len(self._thirsty_ids)
            self._water_badge.setText(f"{n} por regar")
            self._water_badge.setToolTip(
                "Entidades sedientas del jardín — clic: regar todas (con autorización) · "
                "clic derecho: recorrerlas en Foco"
            )
            self._water_badge.show()
        elif self._waterable_ids:
            # BETA2-FOCO-34: nada sediento, pero hay regadas → permitir re-regar.
            n = len(self._waterable_ids)
            self._water_badge.setText(f"Regar de nuevo ({n})")
            self._water_badge.setToolTip(
                "Todas regadas — clic: volver a regar (con autorización) para un "
                "diagnóstico fresco"
            )
            self._water_badge.show()
        else:
            self._water_badge.hide()

    def _on_water_clicked(self) -> None:
        # BETA2-FOCO-35: durante un lote el clic abre el popover de progreso (no
        # lanza otro riego).
        if self._watering_total > 0:
            self.waterProgressRequested.emit()
            return
        # UI2-04/FOCO-34: regar las sedientas si las hay; si no, re-regar todas
        # las regables (diagnóstico fresco). Autorización en el host.
        ids = self._thirsty_ids or self._waterable_ids
        if not ids:
            return
        self.waterAllRequested.emit(list(ids))

    def emit_next_thirsty(self) -> None:
        """Recorrido de sedientas (JARDIN-03): emite la siguiente, cíclico."""
        if not self._thirsty_ids:
            return
        entity_id = self._thirsty_ids[self._thirsty_idx % len(self._thirsty_ids)]
        self._thirsty_idx = (self._thirsty_idx + 1) % len(self._thirsty_ids)
        self.thirstyRequested.emit(entity_id)

    def _on_water_menu(self, pos) -> None:
        if not self._thirsty_ids or self._watering_total > 0:
            return
        menu = QMenu(self._water_badge)
        action = menu.addAction("Recorrer sedientas en Foco (una a una)")
        action.triggered.connect(self.emit_next_thirsty)
        menu.exec(self._water_badge.mapToGlobal(pos))

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
        if dot.kind == "error":
            self._box.removeWidget(dot)  # candidatos/cultivo no estaban montados (badge)
        dot.setParent(None)
        dot.deleteLater()
        self._sync_count()
        self._sync_cultivo_badge()
        self._reflow()

    def clear(self) -> None:
        for candidate_id in list(self._notifications):
            self.remove(candidate_id)

    def has(self, candidate_id: str) -> bool:
        return candidate_id in self._notifications

    def progress_anchor(self) -> QPushButton:
        """BETA2-FOCO-35: ancla (el badge 💧) para el popover de progreso del lote."""
        return self._water_badge

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
        if self._notifications or self._thirsty_ids or self._waterable_ids:
            self.show()
            self.raise_()  # por encima de los clusters de botones

    # ── geometría ────────────────────────────────────────────────────────

    def _on_clicked(self, candidate_id: str) -> None:
        # Candidatos → revisión; errores → se descartan; cultivo → enfoca la
        # entidad y abre Cultivo, luego se descarta (BETA2-FOCO-34).
        dot = self._notifications.get(candidate_id)
        if dot is not None and dot.kind == "error":
            self.remove(candidate_id)
            return
        if dot is not None and dot.kind == "cultivo":
            self.cultivoReviewRequested.emit(candidate_id)
            self.remove(candidate_id)
            return
        self.reviewRequested.emit(candidate_id)

    def _reflow(self) -> None:
        if not self._notifications and not self._thirsty_ids and not self._waterable_ids:
            self.hide()
            return
        # BETA2-PULIDO-01: activar el layout ANTES de medir — sin esto,
        # adjustSize puede leer la altura vieja (una píldora) y el anclaje del
        # host coloca la capa pisando la píldora Guardar.
        self._box.activate()
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        # Asentamiento diferido: re-ancla una vez con la geometría definitiva
        # (los show() recién hechos publican LayoutRequest asíncronos).
        QTimer.singleShot(0, self._settle)

    def _settle(self) -> None:
        """BETA2-PULIDO-01: segunda pasada de anclaje tras asentar el layout."""
        if not self.isVisible():
            return
        self._box.activate()
        self.adjustSize()
        self._reposition()

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
