"""Cronología LOCAL de la entidad en foco (BETA2-FOCO-10).

Banda compacta bajo el formulario (mismo ancho que el editor): lapso de
existencia con extremos ARRASTRABLES y los hitos de la entidad como rombos
clicables, con creación desde la propia banda. Emite las MISMAS firmas de señal
que la cronología global (``lifespanEdited(str, int, object)`` y
``milestoneCreateRequested(int, str)``) para reutilizar los slots existentes
del workspace — la UI nunca escribe persistencia directamente.

No se incrusta ``ChronoCanvasView`` (3.2k líneas, project-wide): esta banda es
pintura propia con una escala lineal simple. La cronología global sigue siendo
el modo `Cronología`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QPushButton, QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    INK_MUTED,
    INK_SOFT,
    LINE_SOFT,
    LINE_STRONG,
)

_MARGIN_X = 46.0
_AXIS_Y = 40.0
_HANDLE_RADIUS = 6.0
_DIAMOND = 6.0
_MIN_SPAN_YEARS = 10


@dataclass(frozen=True)
class _MilestoneMark:
    milestone_id: str
    title: str
    year: int


class FocoLifelineBand(QWidget):
    """Banda de vida + hitos de UNA entidad. Ajustable por arrastre."""

    lifespanEdited = Signal(str, int, object)  # noqa: N815 — misma firma que la cronología global
    milestoneCreateRequested = Signal(int, str)  # noqa: N815 — mismo slot del workspace
    milestoneActivated = Signal(str)  # noqa: N815 — abre el panel adyacente del hito

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
        self._drag_edge = ""  # "birth" | "death" | ""
        self._drag_year: int | None = None

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

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def set_entity(self, entity: Any, milestones: list[Any] | None = None) -> None:
        """Carga el lapso de la entidad y sus hitos (objetos CausalMilestone)."""
        self._entity_id = str(getattr(entity, "id", "") or "")
        self._entity_name = str(getattr(entity, "name", "") or "")
        self._birth = getattr(entity, "birth_year", None)
        self._death = getattr(entity, "death_year", None)
        marks: list[_MilestoneMark] = []
        for milestone in milestones or []:
            year = getattr(milestone, "year", None)
            if year is None:
                continue
            marks.append(
                _MilestoneMark(
                    str(getattr(milestone, "id", "")),
                    str(getattr(milestone, "title", "")),
                    int(year),
                )
            )
        marks.sort(key=lambda mark: (mark.year, mark.title))
        self._marks = marks
        self._drag_edge = ""
        self._drag_year = None
        self.update()

    def entity_id(self) -> str:
        return self._entity_id

    def span(self) -> tuple[int | None, int | None]:
        return (self._birth, self._death)

    def milestone_ids(self) -> list[str]:
        return [mark.milestone_id for mark in self._marks]

    # ------------------------------------------------------------------
    # Escala lineal (años ↔ píxeles)
    # ------------------------------------------------------------------

    def _year_range(self) -> tuple[int, int]:
        years = [mark.year for mark in self._marks]
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

    def x_at(self, year: int) -> float:
        low, high = self._year_range()
        width = max(1.0, self.width() - 2 * _MARGIN_X)
        if high == low:
            return _MARGIN_X
        return _MARGIN_X + (float(year) - low) / (high - low) * width

    def year_at(self, x: float) -> int:
        low, high = self._year_range()
        width = max(1.0, self.width() - 2 * _MARGIN_X)
        ratio = min(1.0, max(0.0, (x - _MARGIN_X) / width))
        return int(round(low + ratio * (high - low)))

    def milestone_at(self, x: float, tolerance: float = 8.0) -> str:
        for mark in self._marks:
            if abs(self.x_at(mark.year) - x) <= tolerance:
                return mark.milestone_id
        return ""

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

    def _edge_at(self, x: float) -> str:
        if self._birth is not None and abs(self.x_at(int(self._birth)) - x) <= _HANDLE_RADIUS + 3:
            return "birth"
        death_year = self._death if self._death is not None else None
        if death_year is not None and abs(self.x_at(int(death_year)) - x) <= _HANDLE_RADIUS + 3:
            return "death"
        return ""

    def mousePressEvent(self, event) -> None:  # noqa: N802
        x = float(event.position().x())
        edge = self._edge_at(x)
        if edge:
            self._drag_edge = edge
            self._drag_year = self.year_at(x)
            event.accept()
            return
        milestone_id = self.milestone_at(x)
        if milestone_id:
            self.activate_milestone(milestone_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_edge:
            self._drag_year = self.year_at(float(event.position().x()))
            self.update()
            event.accept()
            return
        edge = self._edge_at(float(event.position().x()))
        self.setCursor(Qt.CursorShape.SizeHorCursor if edge else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_edge and self._drag_year is not None:
            edge, year = self._drag_edge, self._drag_year
            self._drag_edge = ""
            self._drag_year = None
            self.set_span_by_drag(edge, year)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._add_button.move(self.width() - self._add_button.width() - 8, 4)

    # ------------------------------------------------------------------
    # Pintura (a mano; sin QGraphicsEffect)
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = self.width()
        axis_pen = QPen(QColor(LINE_STRONG))
        axis_pen.setWidthF(1.2)
        painter.setPen(axis_pen)
        painter.drawLine(QPointF(_MARGIN_X, _AXIS_Y), QPointF(width - _MARGIN_X, _AXIS_Y))

        font = QFont()
        font.setPointSizeF(8.0)
        painter.setFont(font)

        if not self._entity_id or (self._birth is None and self._death is None and not self._marks):
            painter.setPen(QPen(QColor(INK_MUTED)))
            painter.drawText(
                QRectF(0, 8, width, 20),
                Qt.AlignmentFlag.AlignHCenter,
                "Sin datación — arrastra tras fijar años, o crea un hito",
            )
            painter.end()
            return

        low, high = self._year_range()
        painter.setPen(QPen(QColor(INK_MUTED)))
        painter.drawText(
            QRectF(4, _AXIS_Y - 8, _MARGIN_X - 8, 16), Qt.AlignmentFlag.AlignRight, str(low)
        )
        painter.drawText(
            QRectF(width - _MARGIN_X + 4, _AXIS_Y - 8, _MARGIN_X - 8, 16),
            Qt.AlignmentFlag.AlignLeft,
            str(high),
        )

        # Lapso de existencia (abierto por la derecha si no hay muerte).
        if self._birth is not None:
            x_birth = self.x_at(int(self._birth))
            x_death = self.x_at(int(self._death)) if self._death is not None else width - _MARGIN_X
            bar = QRectF(x_birth, _AXIS_Y - 5, max(4.0, x_death - x_birth), 10)
            painter.setPen(QPen(QColor(GOLD_DEEP)))
            painter.setBrush(QColor(GOLD_SOFT))
            painter.drawRoundedRect(bar, 5, 5)
            for edge, x_pos in (("birth", x_birth), ("death", x_death)):
                if edge == "death" and self._death is None:
                    continue
                painter.setBrush(QColor(GOLD))
                painter.drawEllipse(QPointF(x_pos, _AXIS_Y), _HANDLE_RADIUS, _HANDLE_RADIUS)
            painter.setPen(QPen(QColor(INK_SOFT)))
            painter.drawText(
                QRectF(x_birth - 30, _AXIS_Y + 8, 60, 14),
                Qt.AlignmentFlag.AlignHCenter,
                str(self._birth),
            )
            if self._death is not None:
                painter.drawText(
                    QRectF(x_death - 30, _AXIS_Y + 8, 60, 14),
                    Qt.AlignmentFlag.AlignHCenter,
                    str(self._death),
                )

        # Vista previa del arrastre.
        if self._drag_edge and self._drag_year is not None:
            x_preview = self.x_at(self._drag_year)
            preview_pen = QPen(QColor(GOLD))
            preview_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(preview_pen)
            painter.drawLine(QPointF(x_preview, 10), QPointF(x_preview, _AXIS_Y + 10))

        # Hitos como rombos.
        for mark in self._marks:
            x_mark = self.x_at(mark.year)
            diamond = QPolygonF(
                [
                    QPointF(x_mark, _AXIS_Y - _DIAMOND - 8),
                    QPointF(x_mark + _DIAMOND, _AXIS_Y - 8),
                    QPointF(x_mark, _AXIS_Y + _DIAMOND - 8),
                    QPointF(x_mark - _DIAMOND, _AXIS_Y - 8),
                ]
            )
            painter.setPen(QPen(QColor(GOLD_DEEP)))
            painter.setBrush(QColor(LINE_SOFT))
            painter.drawPolygon(diamond)
        painter.end()
