"""Manual project chronology/calendar editor (H06)."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.calendar_date_picker import CalendarDatePicker
from packages.domain.result import Error


def _metadata(chronology: Any) -> dict[str, Any]:
    value = getattr(chronology, "metadata", {}) or {}
    return dict(value) if isinstance(value, dict) else {}


def _lines(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def _spin_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _length_lines(names: Any, lengths: Any, fallback: int) -> str:
    length_map = dict(lengths or {}) if isinstance(lengths, dict) else {}
    rows = []
    for name in _lines(names).splitlines():
        clean = name.strip()
        if not clean:
            continue
        rows.append(f"{clean}: {length_map.get(clean, fallback)}")
    return "\n".join(rows)


def _names_from_length_text(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        for separator in (":", "=", ","):
            if separator in clean:
                clean = clean.split(separator, 1)[0].strip()
                break
        if clean:
            names.append(clean)
    return names


class ChronologyConfigPanel(QGroupBox):
    """Three-mode manual chronology editor; no AI provider required."""

    def __init__(
        self,
        controller: Any,
        *,
        on_saved: Callable[[], None] | None = None,
        compact: bool = False,
        parent=None,
    ):
        super().__init__("Configuracion de cronologia", parent)
        self.controller = controller
        self.on_saved = on_saved
        self.compact = bool(compact)
        self._mode_rows: dict[str, list[QWidget]] = {"vague_periods": [], "full_calendar": []}
        self.setObjectName("chronologyConfigPanel")
        self.setStyleSheet(
            "QGroupBox#chronologyConfigPanel { color: #6F6A42; font-weight: 600; "
            "border: 1px solid #D8D6C8; border-radius: 10px; margin-top: 8px; "
            "padding-top: 14px; background: transparent; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)
        self.mode_combo = QComboBox()
        for raw, label in [
            ("none", "No anadir calendario"),
            ("vague_periods", "Calendario vago"),
            ("full_calendar", "Calendario completo"),
        ]:
            self.mode_combo.addItem(label, raw)
        self.mode_combo.currentIndexChanged.connect(self._sync_mode_visibility)
        self._add_row(form, "Opcion", self.mode_combo)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre del calendario")
        self._add_row(form, "Nombre", self.name_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(58 if compact else 84)
        self.description_edit.setPlaceholderText("Descripcion breve de como se mide el tiempo")
        self._add_row(form, "Descripcion", self.description_edit)

        self.periods_edit = QTextEdit()
        self.periods_edit.setObjectName("vagueCalendarPeriodsEdit")
        self.periods_edit.setMaximumHeight(74 if compact else 100)
        self.periods_edit.setPlaceholderText("Antiguedad\nHistoria reciente\nActualidad")
        self._add_row(form, "Periodos vagos", self.periods_edit, mode="vague_periods")

        self.eras_edit = QTextEdit()
        self.eras_edit.setObjectName("fullCalendarErasEdit")
        self.eras_edit.setMaximumHeight(74 if compact else 100)
        self.eras_edit.setPlaceholderText("Era del Hierro: 800\nEra Imperial: 1200\nEra de la Ruptura: 40")
        self.eras_edit.textChanged.connect(self._sync_current_picker_calendar)
        self._add_row(form, "Eras pasadas", self.eras_edit, mode="full_calendar")

        self.months_edit = QTextEdit()
        self.months_edit.setObjectName("fullCalendarMonthsEdit")
        self.months_edit.setMaximumHeight(86 if compact else 120)
        self.months_edit.setPlaceholderText("Enero: 31\nFebrero: 28\nMarzo: 31...")
        self.months_edit.textChanged.connect(self._sync_current_picker_calendar)
        self._add_row(form, "Meses", self.months_edit, mode="full_calendar")

        self.weekdays_edit = QTextEdit()
        self.weekdays_edit.setObjectName("fullCalendarWeekdaysEdit")
        self.weekdays_edit.setMaximumHeight(68 if compact else 90)
        self.weekdays_edit.setPlaceholderText("Lunes\nMartes\nMiercoles...")
        self._add_row(form, "Dias semana", self.weekdays_edit, mode="full_calendar")

        self.days_per_month_spin = QSpinBox()
        self.days_per_month_spin.setRange(1, 999)
        self.days_per_month_spin.setValue(30)
        self._add_row(form, "Dias por mes", self.days_per_month_spin, mode="full_calendar")

        self.current_year_spin = QSpinBox()
        self.current_year_spin.setRange(-999999, 999999)
        self.current_year_spin.setValue(1)
        self._add_row(form, "Ano actual", self.current_year_spin, mode="full_calendar")

        self.current_date_picker = CalendarDatePicker(compact=True)
        self.current_date_picker.setObjectName("currentCalendarDatePicker")
        self._add_row(form, "Fecha actual", self.current_date_picker, mode="full_calendar")

        root.addLayout(form)

        self.help_label = QLabel("")
        self.help_label.setObjectName("mutedLabel")
        self.help_label.setWordWrap(True)
        root.addWidget(self.help_label)

        row = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("mutedLabel")
        self.status.setWordWrap(True)
        row.addWidget(self.status, 1)
        save = QPushButton("Guardar cronologia")
        save.setObjectName("saveChronologyConfigButton")
        save.clicked.connect(self.save)
        row.addWidget(save)
        root.addLayout(row)

        self.refresh()

    def _add_row(self, form: QFormLayout, label_text: str, widget: QWidget, *, mode: str = "") -> None:
        label = QLabel(label_text)
        form.addRow(label, widget)
        if mode:
            self._mode_rows.setdefault(mode, []).extend([label, widget])

    def _sync_mode_visibility(self) -> None:
        mode = str(self.mode_combo.currentData() or "none")
        for row_mode, widgets in self._mode_rows.items():
            visible = row_mode == mode
            for widget in widgets:
                widget.setVisible(visible)
        if mode == "none":
            self.help_label.setText("El proyecto no usara calendario. Los hitos pueden ordenarse manualmente.")
        elif mode == "vague_periods":
            self.help_label.setText("Usa periodos amplios como Antiguedad, Historia reciente y Actualidad.")
        else:
            self.help_label.setText("Define eras y meses como 'Nombre: duracion'. Ej: Febrero: 28, Era Imperial: 1200.")
            self._sync_current_picker_calendar()

    def _form_calendar_metadata(self) -> dict[str, Any]:
        eras = _names_from_length_text(self.eras_edit.toPlainText())
        months = _names_from_length_text(self.months_edit.toPlainText())
        return {
            "mode": "full_calendar",
            "eras": eras,
            "past_eras": eras,
            "months": months,
            "weekdays": _names_from_length_text(self.weekdays_edit.toPlainText()),
            "era_lengths": self.eras_edit.toPlainText(),
            "month_lengths": self.months_edit.toPlainText(),
            "days_per_month": self.days_per_month_spin.value(),
            "current_year": self.current_year_spin.value(),
        }

    def _sync_current_picker_calendar(self) -> None:
        if not hasattr(self, "current_date_picker"):
            return
        current = self.current_date_picker.date()
        self.current_date_picker.set_calendar(self._form_calendar_metadata())
        self.current_date_picker.set_date(current)

    def refresh(self) -> None:
        if self.controller is None or not hasattr(self.controller, "get"):
            self.status.setText("Cronologia no disponible")
            return
        result = self.controller.get()
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        chronology = result.value
        meta = _metadata(chronology)
        mode = str(meta.get("mode") or getattr(chronology, "calendar_system", "") or "none")
        legacy = {"relative": "vague_periods", "narrative": "vague_periods", "custom_calendar": "full_calendar"}
        mode = legacy.get(mode, mode)
        idx = self.mode_combo.findData(mode)
        self.mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.name_edit.setText(str(getattr(chronology, "calendar_name", "") or ""))
        self.description_edit.setPlainText(str(getattr(chronology, "description", "") or ""))
        self.periods_edit.setPlainText(_lines(meta.get("periods") or ["Antiguedad", "Historia reciente", "Actualidad"]))
        self.eras_edit.setPlainText(_length_lines(meta.get("past_eras") or meta.get("eras") or [], meta.get("era_lengths"), 100))
        self.months_edit.setPlainText(_length_lines(meta.get("months") or [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        ], meta.get("month_lengths"), _spin_value(meta.get("days_per_month"), 30)))
        self.weekdays_edit.setPlainText(_lines(meta.get("weekdays") or [
            "Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo",
        ]))
        self.days_per_month_spin.setValue(max(1, _spin_value(meta.get("days_per_month"), 30)))
        self.current_year_spin.setValue(_spin_value(meta.get("current_year"), 1))
        self._sync_current_picker_calendar()
        self.current_date_picker.set_date(meta.get("current_date") or {})
        self._sync_mode_visibility()

    def save(self) -> None:
        if self.controller is None or not hasattr(self.controller, "update"):
            self.status.setText("Cronologia no disponible")
            return
        mode = str(self.mode_combo.currentData() or "none")
        data = {
            "calendar_name": self.name_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "calendar_system": mode,
            "mode": mode,
            "periods": self.periods_edit.toPlainText(),
            "eras": _names_from_length_text(self.eras_edit.toPlainText()),
            "past_eras": _names_from_length_text(self.eras_edit.toPlainText()),
            "era_lengths": self.eras_edit.toPlainText(),
            "months": _names_from_length_text(self.months_edit.toPlainText()),
            "month_lengths": self.months_edit.toPlainText(),
            "weekdays": self.weekdays_edit.toPlainText(),
            "days_per_month": self.days_per_month_spin.value(),
            "months_per_year": len(_names_from_length_text(self.months_edit.toPlainText())),
            "current_year": self.current_year_spin.value(),
            "current_date": self.current_date_picker.date(),
        }
        result = self.controller.update(data)
        if isinstance(result, Error):
            self.status.setText(result.error)
            return
        self.status.setText("Cronologia guardada")
        if self.on_saved is not None:
            self.on_saved()
