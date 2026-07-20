"""BETA2-CAL-06 — Timeline visual de eras encadenadas (pintura propia).

Una franja horizontal donde las eras se dibujan como segmentos tintados
proporcionales a su duración, encadenados (la primera empieza en el origen, la
última queda ABIERTA ``…∞``). Se editan por arrastre:

- **Asas de frontera**: cada límite entre dos eras es un asa. Arrastrarla
  redimensiona la era de su IZQUIERDA y desplaza las siguientes (el total del
  calendario crece/mengua) — "agarrar el final de la era".
- **Asa de extensión**: el borde abierto de la última era fija su duración
  nominal (para el ancho visual y el encaje del presente).
- **Línea de presente**: una línea vertical arrastrable marca el momento
  presente (fija era + año dentro de la era).

No incrusta ``ChronoCanvasView`` (project-wide): es pintura propia con una
escala lineal por tramos, siguiendo a ``FocoLifelineBand``. La UI nunca escribe
persistencia directa: este widget solo mantiene estado en memoria y emite
``changed``; ``CalendarEditor`` traduce a payload de ``CalendarService``.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
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
from PySide6.QtWidgets import QWidget

from hosts.DesktopHostPySide.widgets.design_system import (
    CHRONO_ERA_TINTS,
    GOLD,
    GOLD_DEEP,
    GOLD_SOFT,
    GOLD_TINT,
    INK_MUTED,
    INK_SOFT,
    INK_STRONG,
    LINE_STRONG,
    SURFACE,
    SURFACE_HI,
)

DEFAULT_ERA_DURATION = 100

_MARGIN_X = 20.0
_TOP = 50.0  # franja del presente: bandera + chip de fecha exacta
_BAND_H = 54.0  # banda de eras (alta, para que respire)
_BOTTOM = 28.0  # eje de años (ticks de frontera) BAJO la banda
_HANDLE_R = 7.0
_MIN_SEG_PX = 34.0  # ancho mínimo por era (para poder agarrarla aunque sea corta)
_HIT_TOL = 4.0  # umbral de arrastre (px)


class EraTimelineBand(QWidget):
    """Timeline horizontal de eras encadenadas, ajustable por arrastre."""

    changed = Signal()  # cualquier edición (fronteras, presente, alta/baja/orden)
    eraSelected = Signal(int)  # noqa: N815 — convención Qt

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(int(_TOP + _BAND_H + _BOTTOM))
        self.setMinimumWidth(320)
        self.setMouseTracking(True)
        self._loading = False
        self._eras: list[dict[str, Any]] = [{"name": "Presente", "duration": DEFAULT_ERA_DURATION}]
        self._present_index = 0
        self._present_year_within = 1
        self._selected = 0
        # Rótulo de fecha exacta que muestra el chip del presente; lo fija
        # CalendarEditor (p.ej. "año 15 · Ene 3"). Si es None, se usa "año N".
        self._present_caption: str | None = None

        # Estado de arrastre.
        self._drag_kind = ""  # "" | "boundary" | "open" | "present" | "select"
        self._drag_boundary = -1
        self._press_x = 0.0
        self._drag_moved = False
        self._drag_year: int | None = None

    # ------------------------------------------------------------------
    # API de datos
    # ------------------------------------------------------------------

    def set_eras(
        self, eras: list[dict[str, Any]] | None, present_index: int, present_year_within: int
    ) -> None:
        """Carga la lista de eras y el presente (sin emitir ``changed``)."""
        self._loading = True
        cleaned: list[dict[str, Any]] = []
        for era in eras or []:
            name = str(era.get("name", "") or "")
            duration = max(1, int(era.get("duration", DEFAULT_ERA_DURATION) or 1))
            cleaned.append({"name": name, "duration": duration})
        if not cleaned:
            cleaned = [{"name": "Presente", "duration": DEFAULT_ERA_DURATION}]
        self._eras = cleaned
        self._present_index = min(max(0, int(present_index)), len(self._eras) - 1)
        self._present_year_within = self._clamp_year_within(
            self._present_index, int(present_year_within)
        )
        self._selected = self._present_index
        self._loading = False
        self.updateGeometry()
        self.update()

    def eras(self) -> list[dict[str, Any]]:
        return [dict(era) for era in self._eras]

    def present(self) -> tuple[int, int]:
        return (self._present_index, self._present_year_within)

    def selected_index(self) -> int:
        return self._selected

    def era_count(self) -> int:
        return len(self._eras)

    def set_present_caption(self, caption: str | None) -> None:
        """Rótulo de fecha exacta del chip del presente (p.ej. 'año 15 · Ene 3')."""
        caption = caption or None
        if caption != self._present_caption:
            self._present_caption = caption
            self.update()

    # ------------------------------------------------------------------
    # Rutas de edición únicas (handlers de ratón, inspector y tests)
    # ------------------------------------------------------------------

    def set_boundary_by_drag(self, boundary: int, year: int) -> None:
        """Frontera entre la era ``boundary`` y la ``boundary+1``.

        Redimensiona-y-desplaza: la nueva duración de la era ``boundary`` es
        ``year − inicio(boundary)`` (≥1); las eras siguientes conservan su
        duración y se desplazan solas por el encadenado.
        """
        if boundary < 0 or boundary >= len(self._eras) - 1:
            return
        start = self._era_start(boundary)
        new_duration = max(1, min(999999, int(year) - start))
        if new_duration == self._eras[boundary]["duration"]:
            return
        self._eras[boundary]["duration"] = new_duration
        self._present_year_within = self._clamp_year_within(
            self._present_index, self._present_year_within
        )
        self._emit_changed()

    def set_open_extent_by_drag(self, year: int) -> None:
        """Fija la duración nominal de la ÚLTIMA era (la abierta)."""
        last = len(self._eras) - 1
        if last < 0:
            return
        start = self._era_start(last)
        new_duration = max(1, min(999999, int(year) - start))
        if new_duration == self._eras[last]["duration"]:
            return
        self._eras[last]["duration"] = new_duration
        self._emit_changed()

    def set_present_by_drag(self, year: int) -> None:
        """Marca el presente en el año absoluto ``year`` (fija era + año dentro)."""
        year = max(0, int(year))
        idx = self._era_containing_year(year)
        within = year - self._era_start(idx) + 1
        self._present_index = idx
        self._present_year_within = self._clamp_year_within(idx, within)
        self._emit_changed()

    def set_present_index(self, index: int) -> None:
        index = min(max(0, int(index)), len(self._eras) - 1)
        if index == self._present_index:
            return
        self._present_index = index
        self._present_year_within = self._clamp_year_within(index, self._present_year_within)
        self._emit_changed()

    def set_present_year_within(self, year_within: int) -> None:
        value = self._clamp_year_within(self._present_index, int(year_within))
        if value == self._present_year_within:
            return
        self._present_year_within = value
        self._emit_changed()

    def rename_era(self, index: int, name: str) -> None:
        if 0 <= index < len(self._eras):
            self._eras[index]["name"] = str(name)
            self._emit_changed()

    def set_era_duration(self, index: int, duration: int) -> None:
        if not (0 <= index < len(self._eras)):
            return
        value = max(1, min(999999, int(duration)))
        if value == self._eras[index]["duration"]:
            return
        self._eras[index]["duration"] = value
        self._present_year_within = self._clamp_year_within(
            self._present_index, self._present_year_within
        )
        self._emit_changed()

    def add_era(self, name: str = "Nueva era", duration: int = DEFAULT_ERA_DURATION) -> int:
        """Añade una era al final (pasa a ser la abierta) y la selecciona."""
        self._eras.append({"name": str(name), "duration": max(1, int(duration))})
        self._selected = len(self._eras) - 1
        self._emit_changed()
        self.eraSelected.emit(self._selected)
        return self._selected

    def remove_era(self, index: int) -> None:
        if len(self._eras) <= 1 or not (0 <= index < len(self._eras)):
            return  # contrato: siempre ≥1 era
        del self._eras[index]
        n = len(self._eras)
        if self._present_index == index:
            self._present_index = min(index, n - 1)
        elif self._present_index > index:
            self._present_index -= 1
        self._present_year_within = self._clamp_year_within(
            self._present_index, self._present_year_within
        )
        self._selected = min(self._selected, n - 1)
        self._emit_changed()
        self.eraSelected.emit(self._selected)

    def move_era(self, index: int, delta: int) -> None:
        target = index + delta
        if not (0 <= index < len(self._eras)) or not (0 <= target < len(self._eras)):
            return
        self._eras[index], self._eras[target] = self._eras[target], self._eras[index]
        for attr in ("_present_index", "_selected"):
            value = getattr(self, attr)
            if value == index:
                setattr(self, attr, target)
            elif value == target:
                setattr(self, attr, index)
        self._emit_changed()
        self.eraSelected.emit(self._selected)

    def select_era(self, index: int) -> None:
        if 0 <= index < len(self._eras) and index != self._selected:
            self._selected = index
            self.update()
            self.eraSelected.emit(index)

    # ------------------------------------------------------------------
    # Geometría / escala (año ↔ píxel, por tramos)
    # ------------------------------------------------------------------

    def _era_start(self, index: int) -> int:
        return sum(int(e["duration"]) for e in self._eras[:index])

    def _era_containing_year(self, year: int) -> int:
        """Índice de la era cuyo ``[inicio, inicio+duración)`` contiene ``year``;
        la última (abierta) absorbe cualquier ``year`` que exceda el total."""
        for i, era in enumerate(self._eras):
            if year < self._era_start(i) + int(era["duration"]):
                return i
        return len(self._eras) - 1

    def _clamp_year_within(self, index: int, year_within: int) -> int:
        year_within = max(1, int(year_within))
        is_open = index == len(self._eras) - 1
        if is_open:
            return year_within
        return min(year_within, int(self._eras[index]["duration"]))

    def _seg_widths(self) -> list[float]:
        n = len(self._eras)
        avail = max(1.0, float(self.width()) - 2 * _MARGIN_X)
        durations = [max(1, int(e["duration"])) for e in self._eras]
        total = float(sum(durations))
        if n * _MIN_SEG_PX >= avail:
            return [avail / n] * n
        extra = avail - n * _MIN_SEG_PX
        return [_MIN_SEG_PX + extra * (d / total) for d in durations]

    def _segments(self) -> list[dict[str, Any]]:
        widths = self._seg_widths()
        x = _MARGIN_X
        start = 0
        out: list[dict[str, Any]] = []
        for i, era in enumerate(self._eras):
            duration = max(1, int(era["duration"]))
            out.append({"i": i, "x0": x, "x1": x + widths[i], "start": start, "duration": duration})
            x += widths[i]
            start += duration
        return out

    def x_at(self, year: int) -> float:
        segs = self._segments()
        if year <= 0:
            return segs[0]["x0"]
        for seg in segs:
            if seg["start"] <= year <= seg["start"] + seg["duration"]:
                frac = (year - seg["start"]) / seg["duration"]
                return seg["x0"] + frac * (seg["x1"] - seg["x0"])
        return segs[-1]["x1"]

    def year_at(self, x: float) -> int:
        segs = self._segments()
        if x <= segs[0]["x0"]:
            return 0
        for seg in segs:
            if seg["x0"] <= x <= seg["x1"]:
                width = max(1e-6, seg["x1"] - seg["x0"])
                frac = (x - seg["x0"]) / width
                return int(round(seg["start"] + frac * seg["duration"]))
        last = segs[-1]
        return last["start"] + last["duration"]

    def _present_abs(self) -> int:
        return self._era_start(self._present_index) + (self._present_year_within - 1)

    # ------------------------------------------------------------------
    # Ratón
    # ------------------------------------------------------------------

    def _boundary_at(self, x: float) -> int:
        segs = self._segments()
        for i in range(len(segs) - 1):  # fronteras internas 0..n-2
            if abs(segs[i]["x1"] - x) <= _HANDLE_R + 3:
                return i
        return -1

    def _open_handle_at(self, x: float) -> bool:
        segs = self._segments()
        return abs(segs[-1]["x1"] - x) <= _HANDLE_R + 3

    def _segment_at(self, x: float) -> int:
        for seg in self._segments():
            if seg["x0"] <= x <= seg["x1"]:
                return seg["i"]
        return -1

    def mousePressEvent(self, event) -> None:  # noqa: N802
        x = float(event.position().x())
        y = float(event.position().y())
        self._press_x = x
        self._drag_moved = False
        self._drag_year = None
        present_x = self.x_at(self._present_abs())
        if abs(present_x - x) <= _HANDLE_R + 4 and y <= _TOP + _BAND_H:
            self._drag_kind = "present"
        elif self._open_handle_at(x):
            self._drag_kind = "open"
        elif (boundary := self._boundary_at(x)) >= 0:
            self._drag_kind = "boundary"
            self._drag_boundary = boundary
        else:
            self._drag_kind = "select"
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        x = float(event.position().x())
        if self._drag_kind and self._drag_kind != "select":
            if not self._drag_moved and abs(x - self._press_x) <= _HIT_TOL:
                event.accept()
                return
            self._drag_moved = True
            self._drag_year = self.year_at(x)
            self.update()
            event.accept()
            return
        if self._drag_kind == "select":
            event.accept()
            return
        # Hover: feedback de cursor.
        present_x = self.x_at(self._present_abs())
        over_handle = (
            abs(present_x - x) <= _HANDLE_R + 4
            or self._open_handle_at(x)
            or self._boundary_at(x) >= 0
        )
        self.setCursor(
            Qt.CursorShape.SizeHorCursor if over_handle else Qt.CursorShape.PointingHandCursor
        )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        kind = self._drag_kind
        year = self._drag_year
        moved = self._drag_moved
        boundary = self._drag_boundary
        self._drag_kind = ""
        self._drag_boundary = -1
        self._drag_moved = False
        self._drag_year = None
        x = float(event.position().x())
        if kind and kind != "select" and moved and year is not None:
            if kind == "present":
                self.set_present_by_drag(year)
            elif kind == "open":
                self.set_open_extent_by_drag(year)
            elif kind == "boundary":
                self.set_boundary_by_drag(boundary, year)
            self.update()
            event.accept()
            return
        # Clic sin arrastre → seleccionar la era bajo el cursor.
        idx = self._segment_at(x)
        if idx >= 0:
            self.select_era(idx)
        event.accept()

    # ------------------------------------------------------------------
    # Emisión
    # ------------------------------------------------------------------

    def _emit_changed(self) -> None:
        self.update()
        if self._loading:
            return
        self.changed.emit()

    # ------------------------------------------------------------------
    # Tamaño
    # ------------------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(560, int(_TOP + _BAND_H + _BOTTOM))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(320, int(_TOP + _BAND_H + _BOTTOM))

    # ------------------------------------------------------------------
    # Pintura (a mano; sin QGraphicsEffect)
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        segs = self._segments()
        band_top = _TOP
        band_bot = _TOP + _BAND_H
        last = len(segs) - 1

        # Fondo de la franja.
        painter.setPen(QPen(QColor(LINE_STRONG), 1.0))
        painter.setBrush(QColor(SURFACE))
        painter.drawRoundedRect(
            QRectF(_MARGIN_X, band_top, segs[-1]["x1"] - _MARGIN_X, _BAND_H), 8, 8
        )

        name_font = QFont()
        name_font.setPointSizeF(9.5)
        name_font.setWeight(QFont.Weight.DemiBold)
        small_font = QFont()
        small_font.setPointSizeF(8.0)

        for seg in segs:
            i = seg["i"]
            x0, x1 = seg["x0"], seg["x1"]
            tint = QColor(CHRONO_ERA_TINTS[i % len(CHRONO_ERA_TINTS)])
            rect = QRectF(x0, band_top, x1 - x0, _BAND_H)
            if i == last and len(segs) >= 1:
                # Última era ABIERTA: degradado a transparente por la derecha.
                grad = QLinearGradient(x0, 0, x1, 0)
                open_from = QColor(tint)
                open_from.setAlpha(150)
                open_to = QColor(tint)
                open_to.setAlpha(24)
                grad.setColorAt(0.0, open_from)
                grad.setColorAt(1.0, open_to)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(grad))
            else:
                fill = QColor(tint)
                fill.setAlpha(150)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fill)
            painter.drawRect(rect)

            # Nombre de la era (elidido) + años.
            painter.setFont(name_font)
            painter.setPen(QPen(QColor(INK_STRONG)))
            metrics = QFontMetrics(name_font)
            name = str(self._eras[i]["name"]).strip() or "Sin nombre"
            avail = max(10.0, (x1 - x0) - 10.0)
            elided = metrics.elidedText(name, Qt.TextElideMode.ElideRight, int(avail))
            painter.drawText(
                QRectF(x0 + 5, band_top + 6, x1 - x0 - 10, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                elided,
            )
            painter.setFont(small_font)
            painter.setPen(QPen(QColor(INK_SOFT)))
            duration = int(self._eras[i]["duration"])
            years_text = f"{duration} años" + (" · ∞" if i == last else "")
            painter.drawText(
                QRectF(x0 + 5, band_bot - 20, x1 - x0 - 10, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                years_text,
            )

            # Eje de años: tick del año absoluto de inicio BAJO la frontera izq.
            painter.setFont(small_font)
            painter.setPen(QPen(QColor(INK_MUTED)))
            painter.drawText(
                QRectF(x0 - 24, band_bot + 5, 48, 14),
                Qt.AlignmentFlag.AlignHCenter,
                str(seg["start"]),
            )

        # Borde de la era seleccionada.
        if 0 <= self._selected < len(segs):
            seg = segs[self._selected]
            painter.setPen(QPen(QColor(GOLD_DEEP), 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                QRectF(seg["x0"] + 1, band_top + 1, seg["x1"] - seg["x0"] - 2, _BAND_H - 2), 6, 6
            )

        # Asas de frontera (internas) + asa de extensión (abierta).
        for i in range(len(segs) - 1):
            self._paint_handle(painter, segs[i]["x1"], band_top + _BAND_H / 2, filled=True)
        self._paint_handle(painter, segs[-1]["x1"], band_top + _BAND_H / 2, filled=False)
        # "∞" junto al borde abierto.
        painter.setFont(name_font)
        painter.setPen(QPen(QColor(GOLD_DEEP)))
        painter.drawText(
            QRectF(segs[-1]["x1"] + 2, band_top + _BAND_H / 2 - 10, 16, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "∞",
        )

        # Línea de presente (o preview de arrastre del presente).
        self._paint_present(painter, band_top, band_bot)

        # Preview punteado del año arrastrado.
        if (
            self._drag_moved
            and self._drag_year is not None
            and self._drag_kind
            in {
                "boundary",
                "open",
            }
        ):
            x_prev = self.x_at(self._drag_year)
            pen = QPen(QColor(GOLD))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(x_prev, band_top - 4), QPointF(x_prev, band_bot + 2))
            painter.setPen(QPen(QColor(GOLD_DEEP)))
            painter.setFont(small_font)
            painter.drawText(
                QRectF(x_prev - 30, band_top - 20, 60, 14),
                Qt.AlignmentFlag.AlignHCenter,
                str(self._drag_year),
            )
        painter.end()

    def _paint_handle(self, painter: QPainter, x: float, y: float, *, filled: bool) -> None:
        painter.setPen(QPen(QColor(GOLD_DEEP), 1.5))
        painter.setBrush(QColor(GOLD) if filled else QColor(SURFACE_HI))
        painter.drawEllipse(QPointF(x, y), _HANDLE_R, _HANDLE_R)

    def _paint_present(self, painter: QPainter, band_top: float, band_bot: float) -> None:
        if self._drag_moved and self._drag_kind == "present" and self._drag_year is not None:
            # Durante el arrastre el rótulo externo está obsoleto: mostrar el año vivo.
            x = self.x_at(self._drag_year)
            idx = self._era_containing_year(max(0, self._drag_year))
            within = max(1, self._drag_year - self._era_start(idx) + 1)
            caption = f"año {within}"
        else:
            x = self.x_at(self._present_abs())
            caption = self._present_caption or f"año {self._present_year_within}"

        # Línea + banderín del presente (ancla arriba de la banda).
        painter.setPen(QPen(QColor(GOLD_DEEP), 2.2))
        painter.drawLine(QPointF(x, band_top - 4), QPointF(x, band_bot + 3))
        flag = QPolygonF(
            [
                QPointF(x, band_top - 4),
                QPointF(x + 9, band_top - 10),
                QPointF(x + 9, band_top + 2),
            ]
        )
        painter.setBrush(QColor(GOLD))
        painter.setPen(QPen(QColor(GOLD_DEEP), 1.0))
        painter.drawPolygon(flag)

        # Chip compacto de fecha exacta, siguiendo al marcador (sin solapar el eje).
        font = QFont()
        font.setPointSizeF(8.5)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        text_w = metrics.horizontalAdvance(caption) + 16
        cx = min(max(_MARGIN_X, x - text_w / 2), self.width() - _MARGIN_X - text_w)
        chip = QRectF(cx, 6, text_w, 20)
        painter.setBrush(QColor(GOLD_TINT))
        painter.setPen(QPen(QColor(GOLD_SOFT), 1.0))
        painter.drawRoundedRect(chip, 9, 9)
        painter.setPen(QPen(QColor(GOLD_DEEP)))
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, caption)


__all__ = ["EraTimelineBand", "DEFAULT_ERA_DURATION"]
