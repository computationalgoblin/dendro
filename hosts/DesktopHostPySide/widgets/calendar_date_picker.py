"""Reusable exact-date picker for project full calendars (H07)."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


DEFAULT_MONTHS = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]
DEFAULT_WEEKDAYS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def _named_lengths(value: Any, names: list[str], fallback: int) -> dict[str, int]:
    result: dict[str, int] = {}
    if isinstance(value, dict):
        for name in names:
            result[name] = max(1, _int_value(value.get(name), fallback))
        return result
    if isinstance(value, str):
        for line in _str_list(value):
            name = line
            length = fallback
            for separator in (":", "=", ","):
                if separator in line:
                    left, right = line.split(separator, 1)
                    name = left.strip()
                    length = _int_value(right.strip(), fallback)
                    break
            if name:
                result[name] = max(1, length)
    for name in names:
        result.setdefault(name, fallback)
    return result


class CalendarDatePicker(QWidget):
    """Era/year/month/day picker backed by ProjectChronology metadata."""

    def __init__(
        self,
        *,
        on_changed: Callable[[dict[str, Any]], None] | None = None,
        compact: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.on_changed = on_changed
        self.compact = bool(compact)
        self._metadata: dict[str, Any] = {}
        self._month_lengths: dict[str, int] = {}
        self._era_lengths: dict[str, int] = {}
        self._weekdays: list[str] = list(DEFAULT_WEEKDAYS)
        self._buttons: list[QPushButton] = []
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        top = QHBoxLayout()
        self.era_combo = QComboBox()
        self.era_combo.currentIndexChanged.connect(self._on_era_changed)
        top.addWidget(self.era_combo, 2)
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1, 999999)
        self.year_spin.valueChanged.connect(self._emit_changed)
        top.addWidget(QLabel("Ano"))
        top.addWidget(self.year_spin, 1)
        self.month_combo = QComboBox()
        self.month_combo.currentIndexChanged.connect(self._rebuild_days)
        top.addWidget(self.month_combo, 2)
        root.addLayout(top)

        self.grid = QGridLayout()
        self.grid.setSpacing(3 if compact else 5)
        root.addLayout(self.grid)

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("mutedLabel")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.set_calendar({})

    def set_calendar(self, metadata: dict[str, Any] | None) -> None:
        self._metadata = dict(metadata or {})
        mode = str(self._metadata.get("mode") or "")
        self.setEnabled(mode == "full_calendar")
        eras = _str_list(self._metadata.get("eras") or self._metadata.get("past_eras")) or ["Actualidad"]
        months = _str_list(self._metadata.get("months")) or list(DEFAULT_MONTHS)
        weekdays = _str_list(self._metadata.get("weekdays")) or list(DEFAULT_WEEKDAYS)
        self._weekdays = weekdays
        self._month_lengths = _named_lengths(
            self._metadata.get("month_lengths"),
            [str(month) for month in months],
            _int_value(self._metadata.get("days_per_month"), 30),
        )
        self._era_lengths = _named_lengths(
            self._metadata.get("era_lengths"),
            [str(era) for era in eras],
            100,
        )
        self._syncing = True
        self.era_combo.blockSignals(True)
        self.month_combo.blockSignals(True)
        self.era_combo.clear()
        for era in eras:
            self.era_combo.addItem(str(era), str(era))
        self.month_combo.clear()
        for month in months:
            self.month_combo.addItem(str(month), str(month))
        self.era_combo.blockSignals(False)
        self.month_combo.blockSignals(False)
        self._syncing = False
        self._on_era_changed()
        self._rebuild_days()

    def set_date(self, value: dict[str, Any] | None) -> None:
        data = dict(value or {})
        self._syncing = True
        era = str(data.get("era", "") or "")
        month = str(data.get("month", "") or "")
        era_idx = self.era_combo.findData(era)
        if era_idx >= 0:
            self.era_combo.setCurrentIndex(era_idx)
        self._on_era_changed()
        self.year_spin.setValue(max(1, _int_value(data.get("year"), 1)))
        month_idx = self.month_combo.findData(month)
        if month_idx >= 0:
            self.month_combo.setCurrentIndex(month_idx)
        self._syncing = False
        self._rebuild_days(day=max(1, _int_value(data.get("day"), 1)))

    def date(self) -> dict[str, Any]:
        return {
            "era": str(self.era_combo.currentData() or self.era_combo.currentText() or ""),
            "year": int(self.year_spin.value()),
            "month": str(self.month_combo.currentData() or self.month_combo.currentText() or ""),
            "day": int(getattr(self, "_selected_day", 1)),
        }

    def date_label(self) -> str:
        data = self.date()
        if not data["era"] or not data["month"]:
            return ""
        return f"{data['era']}, ano {data['year']}, {data['month']} {data['day']}"

    def _on_era_changed(self) -> None:
        era = str(self.era_combo.currentData() or self.era_combo.currentText() or "")
        max_year = self._era_lengths.get(era, 100)
        current = min(max(1, self.year_spin.value()), max_year)
        self.year_spin.setRange(1, max_year)
        self.year_spin.setValue(current)
        self._emit_changed()

    def _clear_grid(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._buttons.clear()

    def _rebuild_days(self, day: int | None = None) -> None:
        month = str(self.month_combo.currentData() or self.month_combo.currentText() or "")
        max_day = self._month_lengths.get(month, 30)
        selected = min(max(1, int(day if day is not None else getattr(self, "_selected_day", 1))), max_day)
        self._selected_day = selected
        self._clear_grid()
        for column, weekday in enumerate(self._weekdays[:7]):
            label = QLabel(str(weekday)[:3])
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setObjectName("mutedLabel")
            self.grid.addWidget(label, 0, column)
        for index in range(max_day):
            day_number = index + 1
            button = QPushButton(str(day_number))
            button.setObjectName("calendarDayButton")
            button.setCheckable(True)
            button.setChecked(day_number == selected)
            button.setFixedSize(30 if self.compact else 34, 26 if self.compact else 30)
            button.clicked.connect(lambda _=False, value=day_number: self._select_day(value))
            self._buttons.append(button)
            self.grid.addWidget(button, 1 + index // 7, index % 7)
        self._update_summary()
        self._emit_changed()

    def _select_day(self, value: int) -> None:
        self._selected_day = int(value)
        for button in self._buttons:
            button.setChecked(button.text() == str(value))
        self._update_summary()
        self._emit_changed()

    def _update_summary(self) -> None:
        self.summary_label.setText(self.date_label())

    def _emit_changed(self) -> None:
        self._update_summary()
        if self._syncing or self.on_changed is None:
            return
        self.on_changed(self.date())
