"""Cronología LOCAL de la entidad en foco (BETA2-FOCO-10 · BETA2-CAL-08).

Banda compacta bajo el formulario (mismo ancho que el editor): lapso de
existencia con extremos ARRASTRABLES y los hitos de la entidad como rombos
clicables, con creación desde la propia banda. Emite las MISMAS firmas de señal
que la cronología global (``lifespanEdited(str, int, object)`` y
``milestoneCreateRequested(int, str)``) para reutilizar los slots existentes
del workspace — la UI nunca escribe persistencia directamente.

BETA2-CAL-08: dibuja además las **eras** del proyecto como fondo tintado (contexto)
y la **línea de presente**, y tiene **zoom (rueda) + pan (arrastrar el fondo) + fit
(doble clic / botón ⌂)** con una VENTANA de vista persistente. Por defecto encuadra
al lapso de la entidad; al alejar se llega a ver todo el calendario. Crear hitos pasa
al botón «+ hito» (el arrastre en vacío ahora desplaza, no crea rango).

No se incrusta ``ChronoCanvasView`` (3.2k líneas, project-wide): esta banda es
pintura propia con una escala lineal simple. La cronología global sigue siendo
el modo `Cronología`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QPushButton, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    CHRONO_ERA_TINTS,
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    INK_MUTED,
    INK_SOFT,
    LINE,
    LINE_SOFT,
    LINE_STRONG,
    SURFACE_HI,
)

_MARGIN_X = 46.0
_AXIS_Y = 40.0
_HANDLE_RADIUS = 6.0
_DIAMOND = 6.0
_MIN_SPAN_YEARS = 10
# BETA2-CAL-08: ventana de vista (zoom/pan).
_MIN_VIEW_SPAN = 4  # no se puede acercar más que ~4 años de ancho
_ZOOM_FACTOR = 1.25  # factor del span por paso de rueda


# UI2-14: separación del rombo fantasma de FIN respecto del inicio (px) —
# affordance con hover para fijar la finalización de un hito puntual.
_GHOST_END_OFFSET = 14.0


@dataclass(frozen=True)
class _MilestoneMark:
    milestone_id: str
    title: str
    year: int
    # FOCO-25: fin opcional (span derivado de la duración del hito) → barra.
    end_year: int | None = None


class FocoLifelineBand(QWidget):
    """Banda de vida + hitos de UNA entidad. Ajustable por arrastre + zoom/pan."""

    lifespanEdited = Signal(str, int, object)  # noqa: N815 — misma firma que la cronología global
    milestoneCreateRequested = Signal(int, str)  # noqa: N815 — mismo slot del workspace
    milestoneActivated = Signal(str)  # noqa: N815 — abre el panel adyacente del hito
    # FOCO-25: arrastrar el rombo de un hito reubica su año (persiste el consumidor).
    milestoneYearEdited = Signal(str, int)  # noqa: N815 — convención Qt de señales
    # UI2-14: arrastrar el rombo de FIN fija/edita la finalización del hito
    # (fin ≤ inicio ⇒ hito puntual; persiste el consumidor vía temporality).
    milestoneEndYearEdited = Signal(str, int)  # noqa: N815 — convención Qt
    # FOCO-26: señal conservada por compat del wiring; BETA2-CAL-08 retira el gesto
    # de "arrastrar en vacío = crear rango" (el arrastre en vacío ahora hace PAN),
    # así que la banda ya no la emite. Crear = «+ hito» + arrastrar el fin.
    milestoneRangeCreateRequested = Signal(int, int)  # noqa: N815 — convención Qt

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setMaximumHeight(64)
        self.setMouseTracking(True)
        self._entity_id = ""
        self._entity_name = ""
        self._birth: int | None = None
        self._death: int | None = None
        self._marks: list[_MilestoneMark] = []
        # BETA2-CAL-08: eras (contexto) + presente + ventana de vista.
        self._eras: list[Any] = []
        self._present_year: int | None = None
        self._view_low: float | None = None  # None ⇒ encuadre por defecto (lapso)
        self._view_high: float | None = None
        self._panning = False
        self._pan_last_x = 0.0
        self._drag_edge = ""  # "birth" | "death" | ""
        self._drag_year: int | None = None
        # FOCO-25: arrastre de hito — clic sin mover = abrir; arrastre = reubicar.
        self._drag_milestone_id = ""
        self._drag_milestone_moved = False
        self._drag_start_x = 0.0
        # UI2-14: qué extremo del hito se arrastra ("start" | "end").
        self._drag_milestone_edge = "start"
        # UI2-14: hover para el rombo fantasma de FIN de los hitos puntuales.
        self._hover_x: float | None = None
        # BETA2-FOCO-27: SOLO lectura (tarjeta de descripción) — sin arrastrar el
        # lapso ni crear hitos; el clic sobre un rombo solo ABRE el hito.
        self._read_only = False
        self._ro_click_id = ""
        # BETA2-FOCO-29: modo DUAL — el LAPSO se arrastra, pero los hitos no se
        # crean ni se arrastran en línea (se editan clicándolos → panel completo).
        self._lapso_only = False

        self._add_button = QPushButton("+ hito", self)
        self._add_button.setToolTip("Crear un hito ligado a esta entidad")
        self._add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_button.setFixedHeight(20)
        self._add_button.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {GOLD_SOFT}; "
            f"border-radius: 10px; color: {GOLD_DEEP}; font-size: 10px; padding: 0 8px; }} "
            "QPushButton:hover { background: rgba(255,255,255,0.6); }"
        )
        self._add_button.clicked.connect(self._request_create)

        # BETA2-CAL-08: botón discreto para reencuadrar al lapso (además del doble clic).
        self._fit_button = QPushButton("⌂", self)
        self._fit_button.setToolTip("Ajustar al lapso de la entidad")
        self._fit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fit_button.setFixedSize(20, 20)
        self._fit_button.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {LINE_STRONG}; "
            f"border-radius: 10px; color: {INK_SOFT}; font-size: 11px; padding: 0; }} "
            "QPushButton:hover { background: rgba(255,255,255,0.6); }"
        )
        self._fit_button.clicked.connect(self.fit)

    @property
    def _axis_y(self) -> float:
        """Eje anclado abajo: al crecer la banda (carriles) el hueco queda ARRIBA."""
        return float(self.height()) - 24.0

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def set_entity(
        self,
        entity: Any,
        milestones: list[Any] | None = None,
        eras: list[Any] | None = None,
        present_year: int | None = None,
    ) -> None:
        """Carga el lapso de la entidad y sus hitos (objetos CausalMilestone).

        BETA2-CAL-08: opcionalmente las eras del proyecto (contexto) y el año
        presente. Reencuadra la vista al lapso de la nueva entidad.
        """
        self._entity_id = str(getattr(entity, "id", "") or "")
        self._entity_name = str(getattr(entity, "name", "") or "")
        self._birth = getattr(entity, "birth_year", None)
        self._death = getattr(entity, "death_year", None)
        marks: list[_MilestoneMark] = []
        for milestone in milestones or []:
            year = getattr(milestone, "year", None)
            if year is None:
                continue
            # FOCO-25: fin derivado del lapso del hito (duración en años).
            end_year: int | None = None
            span_of = getattr(milestone, "as_temporal_span", None)
            if callable(span_of):
                end = getattr(span_of(), "end_year", None)
                if isinstance(end, int) and not isinstance(end, bool) and end > int(year):
                    end_year = int(end)
            marks.append(
                _MilestoneMark(
                    str(getattr(milestone, "id", "")),
                    str(getattr(milestone, "title", "")),
                    int(year),
                    end_year,
                )
            )
        marks.sort(key=lambda mark: (mark.year, mark.title))
        self._marks = marks
        if eras is not None:
            self._eras = list(eras)
        if present_year is not None:
            self._present_year = int(present_year) or None
        self._drag_edge = ""
        self._drag_year = None
        self._panning = False
        self._view_low = None  # reencuadrar al lapso de la nueva entidad
        self._view_high = None
        self._sync_height()  # FOCO-26: carriles anti-solape pueden pedir más alto
        self.update()

    def set_eras(self, eras: list[Any] | None, present_year: int | None = None) -> None:
        """BETA2-CAL-08: fija las eras de contexto y (opcional) el año presente."""
        self._eras = list(eras or [])
        self._present_year = int(present_year) or None if present_year is not None else None
        self.update()

    def entity_id(self) -> str:
        return self._entity_id

    def span(self) -> tuple[int | None, int | None]:
        return (self._birth, self._death)

    def milestone_ids(self) -> list[str]:
        return [mark.milestone_id for mark in self._marks]

    # ------------------------------------------------------------------
    # Escala lineal (años ↔ píxeles) + ventana de vista (zoom/pan)
    # ------------------------------------------------------------------

    def _year_range(self) -> tuple[int, int]:
        """Rango ENCUADRADO a los datos (lapso + hitos), con margen. Es el
        encuadre por defecto; ``_view_range`` lo usa cuando no hay zoom/pan."""
        years = [mark.year for mark in self._marks]
        years.extend(mark.end_year for mark in self._marks if mark.end_year is not None)
        if self._birth is not None:
            years.append(int(self._birth))
        if self._death is not None:
            years.append(int(self._death))
        if not years:
            return (0, _MIN_SPAN_YEARS)
        low, high = min(years), max(years)
        if high - low < _MIN_SPAN_YEARS:
            pad = (_MIN_SPAN_YEARS - (high - low)) / 2
            low, high = int(low - pad), int(high + pad)
        span = high - low
        return (int(low - span * 0.08), int(high + span * 0.08))

    def _view_range(self) -> tuple[float, float]:
        """Ventana visible: la fijada por zoom/pan, o el encuadre por defecto."""
        if self._view_low is not None and self._view_high is not None:
            return (self._view_low, self._view_high)
        return self._year_range()

    def _calendar_range(self) -> tuple[float, float] | None:
        """Extensión máxima (alejamiento/pan): eras + presente + datos + encuadre.
        ``None`` si no hay nada que situar."""
        vals: list[int] = []
        for era in self._eras:
            start = getattr(era, "start_year", None)
            if start is not None:
                vals.append(int(start))
            end = getattr(era, "end_year", None)
            if end is not None:
                vals.append(int(end))
        if self._present_year is not None:
            vals.append(int(self._present_year))
        if self._birth is not None:
            vals.append(int(self._birth))
        if self._death is not None:
            vals.append(int(self._death))
        for mark in self._marks:
            vals.append(mark.year)
            if mark.end_year is not None:
                vals.append(mark.end_year)
        fitted = self._year_range()  # el calendario SIEMPRE cubre el encuadre por defecto
        vals.extend(fitted)
        if not vals:
            return None
        lo, hi = float(min(vals)), float(max(vals))
        if hi - lo < _MIN_VIEW_SPAN:
            hi = lo + _MIN_VIEW_SPAN
        return (lo, hi)

    def set_view_range(self, low: float, high: float) -> None:
        """Fija la ventana visible, acotada al calendario y a un span mínimo."""
        low, high = float(low), float(high)
        if high < low:
            low, high = high, low
        span = max(float(_MIN_VIEW_SPAN), high - low)
        cal = self._calendar_range()
        if cal is not None:
            cal_lo, cal_hi = cal
            cal_span = max(float(_MIN_VIEW_SPAN), cal_hi - cal_lo)
            if span >= cal_span:  # alejar hasta el tope = todo el calendario
                low, high = cal_lo, cal_hi
            else:
                high = low + span
                if low < cal_lo:
                    low, high = cal_lo, cal_lo + span
                if high > cal_hi:
                    high, low = cal_hi, cal_hi - span
        else:
            high = low + span
        self._view_low, self._view_high = low, high
        self.update()

    def view_range(self) -> tuple[float, float]:
        return self._view_range()

    def fit(self) -> None:
        """Reencuadra al lapso de la entidad (quita zoom/pan)."""
        self._view_low = None
        self._view_high = None
        self.update()

    def zoom_view(self, anchor_year: float, zoom_in: bool) -> None:
        """Un paso de zoom manteniendo fijo ``anchor_year`` bajo el cursor."""
        low, high = self._view_range()
        span = high - low
        if span <= 0:
            return
        new_span = span / _ZOOM_FACTOR if zoom_in else span * _ZOOM_FACTOR
        frac = (anchor_year - low) / span
        new_low = anchor_year - frac * new_span
        self.set_view_range(new_low, new_low + new_span)

    def pan_view(self, delta_years: float) -> None:
        low, high = self._view_range()
        self.set_view_range(low + delta_years, high + delta_years)

    def x_at(self, year: int) -> float:
        low, high = self._view_range()
        width = max(1.0, self.width() - 2 * _MARGIN_X)
        if high == low:
            return _MARGIN_X
        return _MARGIN_X + (float(year) - low) / (high - low) * width

    def year_at(self, x: float) -> int:
        low, high = self._view_range()
        width = max(1.0, self.width() - 2 * _MARGIN_X)
        ratio = min(1.0, max(0.0, (x - _MARGIN_X) / width))
        return int(round(low + ratio * (high - low)))

    def milestone_at(self, x: float, tolerance: float = 8.0) -> str:
        for mark in self._marks:
            if abs(self.x_at(mark.year) - x) <= tolerance:
                return mark.milestone_id
        return ""

    def milestone_end_at(self, x: float, tolerance: float = 8.0) -> str:
        """UI2-14: hito cuyo rombo de FIN cae bajo x (solo hitos con rango)."""
        for mark in self._marks:
            if mark.end_year is None:
                continue
            if abs(self.x_at(mark.end_year) - x) <= tolerance:
                return mark.milestone_id
        return ""

    def _milestone_hit(self, x: float, tolerance: float = 8.0) -> tuple[str, str]:
        """UI2-14: (milestone_id, "start"|"end") del extremo MÁS CERCANO bajo
        x; empate a distancia → gana el inicio. ("", "") si no hay nada."""
        candidates: list[tuple[float, int, str, str]] = []
        for mark in self._marks:
            start_dist = abs(self.x_at(mark.year) - x)
            if start_dist <= tolerance:
                candidates.append((start_dist, 0, mark.milestone_id, "start"))
            if mark.end_year is not None:
                end_dist = abs(self.x_at(mark.end_year) - x)
                if end_dist <= tolerance:
                    candidates.append((end_dist, 1, mark.milestone_id, "end"))
        if not candidates:
            return "", ""
        _, _, milestone_id, edge = min(candidates)
        return milestone_id, edge

    def _ghost_end_at(self, x: float, tolerance: float = 6.0) -> str:
        """UI2-14: hito PUNTUAL cuyo rombo fantasma de fin (a +14px del
        inicio) cae bajo x — solo mientras el hover lo hace visible."""
        if self._hover_x is None:
            return ""
        for mark in self._marks:
            if mark.end_year is not None:
                continue
            x_mark = self.x_at(mark.year)
            if abs(self._hover_x - x_mark) > 22.0:
                continue  # el fantasma solo existe con el cursor cerca
            if abs((x_mark + _GHOST_END_OFFSET) - x) <= tolerance:
                return mark.milestone_id
        return ""

    def _lanes(self) -> dict[str, int]:
        """FOCO-26: carril por hito para que los que comparten espacio temporal
        NO se solapen. Greedy en orden de año: primer carril cuyo último ocupante
        no invade el intervalo en píxeles [x(inicio)−8, x(fin)+8]."""
        lanes: dict[str, int] = {}
        lane_ends: list[float] = []  # x derecho ocupado por carril
        for mark in self._marks:
            x0 = self.x_at(mark.year) - _DIAMOND - 2
            x1 = self.x_at(mark.end_year if mark.end_year is not None else mark.year)
            x1 += _DIAMOND + 2
            for lane, end in enumerate(lane_ends):
                if x0 > end:
                    lanes[mark.milestone_id] = lane
                    lane_ends[lane] = x1
                    break
            else:
                lanes[mark.milestone_id] = len(lane_ends)
                lane_ends.append(x1)
        return lanes

    def _sync_height(self) -> None:
        """Crece la banda cuando hay más de dos carriles (el eje ancla abajo)."""
        lanes = self._lanes()
        max_lane = max(lanes.values(), default=0)
        height = 64 + max(0, max_lane - 1) * 10
        height = min(height, 104)
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    # ------------------------------------------------------------------
    # Edición
    # ------------------------------------------------------------------

    def set_span_by_drag(self, edge: str, year: int) -> None:
        """Ruta única de edición del lapso (los handlers de ratón la usan).

        Actualiza optimista la banda y emite ``lifespanEdited`` con la firma de
        la cronología global; el workspace persiste vía EntityController.
        """
        if not self._entity_id:
            return
        year = int(year)
        if edge == "birth":
            if self._death is not None and year > int(self._death):
                year = int(self._death)
            self._birth = year
        elif edge == "death":
            if self._birth is not None and year < int(self._birth):
                year = int(self._birth)
            self._death = year
        else:
            return
        self.update()
        birth = int(self._birth) if self._birth is not None else 0
        self.lifespanEdited.emit(self._entity_id, birth, self._death)

    def activate_milestone(self, milestone_id: str) -> None:
        if milestone_id:
            self.milestoneActivated.emit(milestone_id)

    def set_read_only(self, value: bool) -> None:
        """BETA2-FOCO-27: alterna el modo SOLO lectura.

        En lectura (tarjeta de descripción) se oculta «+ hito» y se bloquean los
        arrastres de EDICIÓN (bordes del lapso, año/fin de hito); solo el CLIC
        sobre un rombo sigue vivo para abrir el hito. El zoom/pan/fit siguen
        disponibles (son de navegación, no de edición). En edición vuelve a ser
        plenamente interactiva."""
        self._read_only = bool(value)
        self._add_button.setVisible(not self._read_only and not self._lapso_only)
        # Cancelar cualquier arrastre en curso al cambiar de modo.
        self._drag_edge = ""
        self._drag_milestone_id = ""
        self._panning = False
        self._ro_click_id = ""
        self.update()

    def set_lapso_editable_only(self, value: bool) -> None:
        """BETA2-FOCO-29: modo DUAL — el LAPSO se arrastra (sombra), pero los
        hitos NO se crean ni se arrastran en línea; solo el CLIC sobre un rombo
        abre su panel completo. Evita ediciones de hito que parecerían guardarse
        sin persistirse (la persistencia de hito en dual va por el panel)."""
        self._lapso_only = bool(value)
        self._add_button.setVisible(not self._read_only and not self._lapso_only)
        self.update()

    def set_milestone_year_by_drag(self, milestone_id: str, year: int) -> None:
        """Ruta única de reubicación de un hito (FOCO-25, la usan los handlers).

        Actualiza optimista la marca y emite ``milestoneYearEdited``; el
        consumidor persiste por el controller (la UI nunca escribe directa).
        """
        if not milestone_id:
            return
        year = int(year)

        def _moved(mark: _MilestoneMark) -> _MilestoneMark:
            if mark.milestone_id != milestone_id:
                return mark
            # La duración persiste en el hito: el fin se desplaza con el inicio.
            end = mark.end_year + (year - mark.year) if mark.end_year is not None else None
            return _MilestoneMark(mark.milestone_id, mark.title, year, end)

        self._marks = sorted(
            (_moved(mark) for mark in self._marks),
            key=lambda mark: (mark.year, mark.title),
        )
        self.update()
        self.milestoneYearEdited.emit(milestone_id, year)

    def set_milestone_end_by_drag(self, milestone_id: str, end_year: int) -> None:
        """UI2-14: ruta única de edición del FIN de un hito (handlers y tests).

        Arrastrar el fin por debajo del inicio deshace el rango (hito puntual).
        Actualiza optimista y emite ``milestoneEndYearEdited``; el consumidor
        persiste la duración por el controller (temporality)."""
        if not milestone_id:
            return
        end_year = int(end_year)
        emitted_year = end_year

        def _resized(mark: _MilestoneMark) -> _MilestoneMark:
            nonlocal emitted_year
            if mark.milestone_id != milestone_id:
                return mark
            end = end_year if end_year > mark.year else None
            if end is None:
                emitted_year = mark.year  # fin ≤ inicio ⇒ puntual
            return _MilestoneMark(mark.milestone_id, mark.title, mark.year, end)

        self._marks = sorted(
            (_resized(mark) for mark in self._marks),
            key=lambda mark: (mark.year, mark.title),
        )
        self._sync_height()
        self.update()
        self.milestoneEndYearEdited.emit(milestone_id, emitted_year)

    def _request_create(self) -> None:
        if not self._entity_id:
            return
        if self._birth is not None and self._death is not None:
            default_year = int((int(self._birth) + int(self._death)) / 2)
        elif self._birth is not None:
            default_year = int(self._birth)
        else:
            low, high = self._year_range()
            default_year = int((low + high) / 2)
        self.milestoneCreateRequested.emit(default_year, "")

    # ------------------------------------------------------------------
    # Ratón
    # ------------------------------------------------------------------

    def _handle_x(self, edge: str) -> tuple[float | None, bool]:
        """BETA2-FOCO-29: x del asa del lapso y si es PLACEHOLDER (sin datar).

        birth: si hay inicio, su x; si no, un placeholder al 30 % para FIJARLO
        arrastrando. death: si hay fin, su x; si hay inicio pero no fin, el
        extremo abierto (derecha) como asa para fijar el fin; sin inicio aún,
        None (se fija primero el inicio para no forzar un inicio 0)."""
        left = _MARGIN_X
        right = float(self.width()) - _MARGIN_X
        if edge == "birth":
            if self._birth is not None:
                return (self.x_at(int(self._birth)), False)
            return (left + (right - left) * 0.30, True)
        if edge == "death":
            if self._death is not None:
                return (self.x_at(int(self._death)), False)
            if self._birth is not None:
                return (right, True)
            return (None, False)
        return (None, False)

    def _edge_at(self, x: float) -> str:
        for edge in ("birth", "death"):
            hx, _ph = self._handle_x(edge)
            if hx is not None and abs(hx - x) <= _HANDLE_RADIUS + 4:
                return edge
        return ""

    def _begin_pan(self, x: float) -> None:
        self._panning = True
        self._pan_last_x = x
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _apply_pan(self, x: float) -> None:
        low, high = self._view_range()
        width = max(1.0, self.width() - 2 * _MARGIN_X)
        delta = -(x - self._pan_last_x) / width * (high - low)
        self._pan_last_x = x
        self.pan_view(delta)

    def wheelEvent(self, event) -> None:  # noqa: N802
        """BETA2-CAL-08: rueda = zoom, anclado al año bajo el cursor."""
        if not self._entity_id:
            super().wheelEvent(event)
            return
        anchor = self.year_at(float(event.position().x()))
        self.zoom_view(anchor, event.angleDelta().y() > 0)
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        """BETA2-CAL-08: doble clic en vacío reencuadra; sobre un hito lo abre."""
        x = float(event.position().x())
        milestone_id = self._milestone_hit(x)[0]
        if milestone_id:
            self.activate_milestone(milestone_id)
        else:
            self.fit()
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        x = float(event.position().x())
        # BETA2-FOCO-27: en lectura, clic sobre un rombo lo abre; en vacío, PAN.
        if self._read_only:
            self._ro_click_id = self._milestone_hit(x)[0]
            if self._ro_click_id:
                event.accept()
                return
            self._begin_pan(x)
            event.accept()
            return
        # Asa del lapso (edición y dual).
        edge = self._edge_at(x)
        if edge:
            self._drag_edge = edge
            self._drag_year = self.year_at(x)
            event.accept()
            return
        # BETA2-FOCO-29: en dual, clic sobre rombo lo abre; en vacío, PAN.
        if self._lapso_only:
            self._ro_click_id = self._milestone_hit(x)[0]
            if self._ro_click_id:
                event.accept()
                return
            self._begin_pan(x)
            event.accept()
            return
        # Edición plena: arrastrar/abrir hito.
        milestone_id, milestone_edge = self._milestone_hit(x)
        ghost_id = self._ghost_end_at(x) if not milestone_id else ""
        if ghost_id:
            # UI2-14: presionar el rombo fantasma arma un drag de FIN nuevo.
            milestone_id, milestone_edge = ghost_id, "end"
        if milestone_id:
            # FOCO-25: el clic arma un arrastre; si no se mueve, al soltar abre.
            # UI2-14: Shift desde el inicio arma el FIN (fijar rango sin soltar).
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if milestone_edge == "start" and shift:
                milestone_edge = "end"
            self._drag_milestone_id = milestone_id
            self._drag_milestone_edge = milestone_edge or "start"
            self._drag_milestone_moved = False
            self._drag_start_x = x
            self._drag_year = self.year_at(x)
            event.accept()
            return
        # BETA2-CAL-08: zona vacía = PAN (antes creaba un hito por rango).
        self._begin_pan(x)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        x = float(event.position().x())
        if self._panning:
            self._apply_pan(x)
            event.accept()
            return
        if self._read_only:
            over = bool(self._milestone_hit(x)[0])
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.OpenHandCursor
            )
            super().mouseMoveEvent(event)
            return
        if self._drag_edge:
            self._drag_year = self.year_at(x)
            self.update()
            event.accept()
            return
        if self._lapso_only:
            if self._edge_at(x):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif self._milestone_hit(x)[0]:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            super().mouseMoveEvent(event)
            return
        if self._drag_milestone_id:
            if abs(x - self._drag_start_x) > 4.0:
                self._drag_milestone_moved = True
            self._drag_year = self.year_at(x)
            self.update()
            event.accept()
            return
        # UI2-14: el hover alimenta el rombo fantasma de FIN de los puntuales.
        self._hover_x = x
        hot = self._edge_at(x) or self._milestone_hit(x)[0] or self._ghost_end_at(x)
        if hot:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.OpenHandCursor)  # vacío = pan
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_x = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if self._read_only:
            # BETA2-FOCO-27: soltar sobre el mismo rombo → abrir el hito (lectura).
            milestone_id = self._ro_click_id
            self._ro_click_id = ""
            if milestone_id and self._milestone_hit(float(event.position().x()))[0] == milestone_id:
                self.activate_milestone(milestone_id)
                event.accept()
                return
            super().mouseReleaseEvent(event)
            return
        if self._drag_edge and self._drag_year is not None:
            edge, year = self._drag_edge, self._drag_year
            self._drag_edge = ""
            self._drag_year = None
            self.set_span_by_drag(edge, year)
            event.accept()
            return
        if self._lapso_only:
            # BETA2-FOCO-29: soltar sobre el mismo rombo → abrir el hito.
            milestone_id = self._ro_click_id
            self._ro_click_id = ""
            if milestone_id and self._milestone_hit(float(event.position().x()))[0] == milestone_id:
                self.activate_milestone(milestone_id)
                event.accept()
                return
            super().mouseReleaseEvent(event)
            return
        if self._drag_milestone_id:
            milestone_id = self._drag_milestone_id
            moved, year = self._drag_milestone_moved, self._drag_year
            milestone_edge = self._drag_milestone_edge
            self._drag_milestone_id = ""
            self._drag_milestone_edge = "start"
            self._drag_milestone_moved = False
            self._drag_year = None
            if moved and year is not None:
                if milestone_edge == "end":
                    self.set_milestone_end_by_drag(milestone_id, year)  # UI2-14
                else:
                    self.set_milestone_year_by_drag(milestone_id, year)
            else:
                self.activate_milestone(milestone_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._add_button.move(self.width() - self._add_button.width() - 8, 4)
        # ⌂ en la esquina inferior izquierda (discreto).
        self._fit_button.move(6, int(self.height()) - self._fit_button.height() - 4)
        self._sync_height()  # los carriles dependen del ancho (solape en píxeles)

    # ------------------------------------------------------------------
    # Pintura (a mano; sin QGraphicsEffect)
    # ------------------------------------------------------------------

    def _paint_eras(self, painter: QPainter, axis_y: float) -> None:
        """BETA2-CAL-08: eras como fondo tintado sutil + nombre + divisoria, y la
        línea de presente. Solo con escala datable (lapso o hitos)."""
        if not self._eras:
            return
        if self._birth is None and self._death is None and not self._marks:
            return
        low, high = self._view_range()
        band_top = 2.0
        band_bottom = axis_y + 6.0
        eras = sorted(self._eras, key=lambda e: int(getattr(e, "start_year", 0) or 0))
        n = len(CHRONO_ERA_TINTS)
        name_font = QFont()
        name_font.setPointSizeF(7.5)
        metrics = QFontMetrics(name_font)
        open_end = max(high, float(self._present_year) if self._present_year is not None else high)
        for idx, era in enumerate(eras):
            start = int(getattr(era, "start_year", 0) or 0)
            end = getattr(era, "end_year", None)
            order = int(getattr(era, "order", idx) or idx)
            end_val = float(end) if end is not None else open_end
            vis_start = max(float(start), low)
            vis_end = min(end_val, high)
            if vis_end <= vis_start:
                continue  # la era no cae en la ventana
            x0 = self.x_at(vis_start)
            x1 = self.x_at(vis_end)
            tint = QColor(CHRONO_ERA_TINTS[order % n])
            rect = QRectF(x0, band_top, max(1.0, x1 - x0), band_bottom - band_top)
            if end is None:
                grad = QLinearGradient(x0, 0, x1, 0)
                c0 = QColor(tint)
                c0.setAlpha(46)
                c1 = QColor(tint)
                c1.setAlpha(10)
                grad.setColorAt(0.0, c0)
                grad.setColorAt(1.0, c1)
                painter.fillRect(rect, QBrush(grad))
            else:
                fill = QColor(tint)
                fill.setAlpha(42)
                painter.fillRect(rect, fill)
            # Divisoria en la frontera de inicio (si es visible dentro del margen).
            if float(start) >= low:
                painter.setPen(QPen(QColor(LINE), 1.0))
                bx = self.x_at(float(start))
                painter.drawLine(QPointF(bx, band_top), QPointF(bx, band_bottom))
            # Nombre de la era, elidido dentro de su tramo visible.
            name = str(getattr(era, "name", "") or "").strip()
            if name:
                painter.setFont(name_font)
                painter.setPen(QPen(QColor(INK_MUTED)))
                avail = max(8.0, (x1 - x0) - 8.0)
                elided = metrics.elidedText(name, Qt.TextElideMode.ElideRight, int(avail))
                painter.drawText(
                    QRectF(x0 + 4, band_top, x1 - x0 - 6, 12),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    elided,
                )
        # Línea de presente (contexto), discreta.
        if self._present_year is not None and low <= self._present_year <= high:
            xp = self.x_at(int(self._present_year))
            pen = QPen(QColor(GOLD_DEEP))
            pen.setWidthF(1.0)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(xp, band_top), QPointF(xp, band_bottom))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = self.width()
        axis_y = self._axis_y

        if not self._entity_id:
            axis_pen = QPen(QColor(LINE_STRONG))
            axis_pen.setWidthF(1.2)
            painter.setPen(axis_pen)
            painter.drawLine(QPointF(_MARGIN_X, axis_y), QPointF(width - _MARGIN_X, axis_y))
            painter.end()
            return

        # BETA2-FOCO-29: en LECTURA sin datar no hay affordance de edición — solo
        # un aviso tenue (sin ejes ni placeholder de arrastre).
        if self._read_only and self._birth is None and self._death is None and not self._marks:
            painter.setPen(QPen(QColor(INK_MUTED)))
            painter.drawText(QRectF(0, 8, width, 20), Qt.AlignmentFlag.AlignHCenter, "Sin datar")
            painter.end()
            return

        # BETA2-CAL-08: eras de fondo + presente (detrás de todo).
        self._paint_eras(painter, axis_y)

        # Eje.
        axis_pen = QPen(QColor(LINE_STRONG))
        axis_pen.setWidthF(1.2)
        painter.setPen(axis_pen)
        painter.drawLine(QPointF(_MARGIN_X, axis_y), QPointF(width - _MARGIN_X, axis_y))

        font = QFont()
        font.setPointSizeF(8.0)
        painter.setFont(font)

        low, high = self._view_range()
        painter.setPen(QPen(QColor(INK_MUTED)))
        painter.drawText(
            QRectF(4, axis_y - 8, _MARGIN_X - 8, 16),
            Qt.AlignmentFlag.AlignRight,
            str(int(round(low))),
        )
        painter.drawText(
            QRectF(width - _MARGIN_X + 4, axis_y - 8, _MARGIN_X - 8, 16),
            Qt.AlignmentFlag.AlignLeft,
            str(int(round(high))),
        )

        # Lapso de existencia como SOMBRA integrada (BETA2-FOCO-29) — banda
        # translúcida por detrás de los rombos, distinta de las barras de hito;
        # asas de borde arrastrables. Sin datar, un placeholder tenue invita a
        # FIJAR el inicio arrastrando su borde.
        band_top = 6.0
        band_bottom = axis_y + 6.0
        bx, b_ph = self._handle_x("birth")
        dx, d_ph = self._handle_x("death")
        if bx is not None:
            if dx is not None:
                right_x = dx
            elif self._birth is None:
                right_x = _MARGIN_X + (width - 2 * _MARGIN_X) * 0.70  # placeholder acotado
            else:
                right_x = width - _MARGIN_X  # vivo hasta el presente
            shadow = QColor(GOLD_DEEP)
            shadow.setAlphaF(0.07 if self._birth is None else 0.14)
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.setBrush(shadow)
            painter.drawRoundedRect(
                QRectF(bx, band_top, max(4.0, right_x - bx), band_bottom - band_top), 8, 8
            )
            for edge, hx, is_ph in (("birth", bx, b_ph), ("death", dx, d_ph)):
                if hx is None or (is_ph and self._read_only):
                    continue
                edge_pen = QPen(QColor(GOLD_DEEP))
                edge_pen.setWidthF(1.4)
                if is_ph:
                    edge_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(edge_pen)
                painter.drawLine(QPointF(hx, band_top), QPointF(hx, band_bottom))
                painter.setPen(QPen(Qt.PenStyle.NoPen))
                painter.setBrush(QColor(GOLD_SOFT if is_ph else GOLD))
                painter.drawRoundedRect(QRectF(hx - 3, axis_y - 8, 6, 16), 3, 3)
            painter.setPen(QPen(QColor(INK_SOFT)))
            if self._birth is not None:
                painter.drawText(
                    QRectF(bx - 30, band_bottom + 1, 60, 14),
                    Qt.AlignmentFlag.AlignHCenter,
                    str(self._birth),
                )
            if self._death is not None and dx is not None:
                painter.drawText(
                    QRectF(dx - 30, band_bottom + 1, 60, 14),
                    Qt.AlignmentFlag.AlignHCenter,
                    str(self._death),
                )
            if self._birth is None and not self._read_only:
                painter.setPen(QPen(QColor(INK_MUTED)))
                painter.drawText(
                    QRectF(0, band_top - 4, width, 12),
                    Qt.AlignmentFlag.AlignHCenter,
                    "Arrastra el borde para fijar el lapso",
                )

        # Vista previa del arrastre (lapso o hito).
        if (self._drag_edge or self._drag_milestone_moved) and self._drag_year is not None:
            x_preview = self.x_at(self._drag_year)
            preview_pen = QPen(QColor(GOLD))
            preview_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(preview_pen)
            painter.drawLine(QPointF(x_preview, 10), QPointF(x_preview, axis_y + 10))

        # Hitos: rombo en el inicio; con fin, además una barra inicio→fin.
        # FOCO-26: cada hito ocupa su CARRIL — los que comparten espacio
        # temporal se apilan hacia arriba en vez de solaparse.
        lanes = self._lanes()
        for mark in self._marks:
            x_mark = self.x_at(mark.year)
            lift = lanes.get(mark.milestone_id, 0) * 10.0
            if mark.end_year is not None:
                x_end = self.x_at(mark.end_year)
                span_fill = QColor(GOLD_SOFT)
                span_fill.setAlphaF(0.45)
                painter.setPen(QPen(QColor(GOLD_DEEP)))
                painter.setBrush(span_fill)
                painter.drawRoundedRect(
                    QRectF(x_mark, axis_y - _DIAMOND - 11 - lift, max(4.0, x_end - x_mark), 6.0),
                    3.0,
                    3.0,
                )
            diamond = QPolygonF(
                [
                    QPointF(x_mark, axis_y - _DIAMOND - 8 - lift),
                    QPointF(x_mark + _DIAMOND, axis_y - 8 - lift),
                    QPointF(x_mark, axis_y + _DIAMOND - 8 - lift),
                    QPointF(x_mark - _DIAMOND, axis_y - 8 - lift),
                ]
            )
            painter.setPen(QPen(QColor(GOLD_DEEP)))
            painter.setBrush(QColor(LINE_SOFT))
            painter.drawPolygon(diamond)
            if mark.end_year is not None:
                # UI2-14: rombo HUECO en el FIN — hueco vs relleno distingue
                # finalización de inicio; también es el handle de arrastre.
                x_end = self.x_at(mark.end_year)
                end_diamond = QPolygonF(
                    [
                        QPointF(x_end, axis_y - _DIAMOND - 8 - lift),
                        QPointF(x_end + _DIAMOND, axis_y - 8 - lift),
                        QPointF(x_end, axis_y + _DIAMOND - 8 - lift),
                        QPointF(x_end - _DIAMOND, axis_y - 8 - lift),
                    ]
                )
                painter.setPen(QPen(QColor(GOLD_DEEP)))
                painter.setBrush(QColor(SURFACE_HI))
                painter.drawPolygon(end_diamond)
            elif self._hover_x is not None and abs(self._hover_x - x_mark) <= 22.0:
                # UI2-14: hito puntual con el cursor cerca — rombo fantasma que
                # invita a fijar un fin (arrastrable; Shift+drag también sirve).
                x_ghost = x_mark + _GHOST_END_OFFSET
                ghost = QPolygonF(
                    [
                        QPointF(x_ghost, axis_y - _DIAMOND - 8 - lift),
                        QPointF(x_ghost + _DIAMOND, axis_y - 8 - lift),
                        QPointF(x_ghost, axis_y + _DIAMOND - 8 - lift),
                        QPointF(x_ghost - _DIAMOND, axis_y - 8 - lift),
                    ]
                )
                ghost_pen = QColor(GOLD_DEEP)
                ghost_pen.setAlphaF(0.5)
                painter.setPen(QPen(ghost_pen))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPolygon(ghost)
        painter.end()
