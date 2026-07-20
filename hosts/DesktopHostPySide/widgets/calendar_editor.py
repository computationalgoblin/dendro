"""BETA2-CAL-04/06/07 — Editor de calendario unificado por eras encadenadas.

Un único widget visual/interactivo (usado por el wizard y por la configuración de
proyecto). La **timeline es el centro**; todo lo demás es mínimo:

(a) **Presente** en una fila compacta ENCIMA de la timeline: «Era» · año (escribible,
    con ‹ ›) y, si hay meses, mes + día + día de la semana real. También se coloca
    arrastrando la línea de la timeline.
(b) **Timeline de eras** (``EraTimelineBand``): segmentos tintados encadenados (última
    abierta ``…∞``), asas de frontera (redimensiona-y-desplaza), chip de fecha exacta.
(c) **Inspector** mínimo de la era seleccionada: nombre + años (escribible) + reordenar
    + eliminar; añadir era = un botón ``+``.
(d) Extensiones plegables **Meses** / **Semana** (rejilla mínima, longitudes escribibles).

Degrada a "solo eras" cuando no hay meses/semana. Los números usan ``MiniStepper``
(escribible, botones pequeños). El valor se entrega como payload para
``CalendarService.configure`` (la UI nunca escribe persistencia directamente).
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    GOLD,
    GOLD_DEEP,
    GOLD_TINT,
    DisclosureSection,
    ElidedLabel,
    meta_chip_style,
)
from hosts.DesktopHostPySide.widgets.era_timeline import DEFAULT_ERA_DURATION, EraTimelineBand
from hosts.DesktopHostPySide.widgets.mini_stepper import MiniStepper
from packages.domain.calendar_math import CalendarConfig

DEFAULT_MONTH_LENGTH = 30

_ADD_BTN_QSS = (
    f"QToolButton {{ background: transparent; border: 1px solid {GOLD}; border-radius: 13px; "
    f"color: {GOLD_DEEP}; font-size: 16px; font-weight: 700; padding: 0; }} "
    f"QToolButton:hover {{ background: {GOLD_TINT}; }}"
)


class CalendarEditor(QWidget):
    """Editor visual del calendario. `value()` → payload de `CalendarService.configure`."""

    changed = Signal()

    def __init__(
        self,
        *,
        on_changed: Callable[[], None] | None = None,
        show_identity: bool = True,
        compact: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._on_changed = on_changed
        self._compact = bool(compact)
        self._loading = False
        self._syncing = False
        self._month_rows: list[dict[str, Any]] = []
        self._weekday_rows: list[dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        # Identidad: solo el nombre (la descripción se conserva en un holder oculto
        # para no perder datos ya guardados, sin robar protagonismo a la timeline).
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre del calendario (opcional)")
        self.name_edit.textChanged.connect(self._emit_changed)
        self.desc_edit = QLineEdit()  # holder oculto: solo mantiene el valor del contrato
        self.desc_edit.setVisible(False)
        if show_identity:
            root.addWidget(self.name_edit)

        # (a) Presente — fila compacta ENCIMA de la timeline.
        root.addLayout(self._build_present_row())

        # (b) Timeline de eras (elemento dominante).
        self.timeline = EraTimelineBand()
        self.timeline.changed.connect(self._on_timeline_changed)
        self.timeline.eraSelected.connect(self._on_era_selected)
        root.addWidget(self.timeline)

        # (c) Inspector mínimo de la era seleccionada + añadir "+".
        root.addLayout(self._build_inspector())

        # (d) Meses y Semana (plegables, mínimas).
        root.addWidget(self._build_months_section())
        root.addWidget(self._build_week_section())

        # Estado inicial.
        self._refresh_present_row()
        self._refresh_inspector()
        self._sync_present_date_visibility()

    # ── helpers de estilo ────────────────────────────────────────────────

    def _muted(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("mutedLabel")
        return label

    def _overline(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("overline")
        return label

    # ── (a) fila de presente ─────────────────────────────────────────────

    def _build_present_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addStretch(1)
        row.addWidget(self._overline("Presente"))
        self.present_era_label = ElidedLabel("")
        self.present_era_label.setMaximumWidth(220)
        self.present_era_label.setStyleSheet(f"color: {GOLD_DEEP}; font-weight: 600;")
        row.addWidget(self.present_era_label)
        row.addWidget(self._muted("año"))
        self.present_year_spin = MiniStepper(minimum=1, maximum=999999, glyphs=("‹", "›"))
        self.present_year_spin.valueChanged.connect(self._on_present_year_changed)
        row.addWidget(self.present_year_spin)

        self.present_month_combo = QComboBox()
        self.present_month_combo.setStyleSheet(meta_chip_style())
        self.present_month_combo.currentIndexChanged.connect(self._on_present_date_changed)
        row.addWidget(self.present_month_combo)
        self.present_day_spin = MiniStepper(minimum=1, maximum=999, edit_width=40)
        self.present_day_spin.valueChanged.connect(self._on_present_date_changed)
        row.addWidget(self.present_day_spin)

        self.weekday_preview = QLabel("")
        self.weekday_preview.setObjectName("mutedLabel")
        row.addWidget(self.weekday_preview)
        row.addStretch(1)
        return row

    # ── (c) inspector de la era seleccionada ─────────────────────────────

    def _build_inspector(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        add_era = QToolButton()
        add_era.setObjectName("addEraButton")
        add_era.setText("+")
        add_era.setToolTip("Añadir una era")
        add_era.setCursor(Qt.CursorShape.PointingHandCursor)
        add_era.setFixedSize(26, 26)
        add_era.setStyleSheet(_ADD_BTN_QSS)
        add_era.clicked.connect(self._on_add_era)
        row.addWidget(add_era)

        row.addWidget(self._muted("Era"))
        self.era_name_edit = QLineEdit()
        self.era_name_edit.setPlaceholderText("Nombre de la era")
        self.era_name_edit.textChanged.connect(self._on_inspector_name)
        row.addWidget(self.era_name_edit, 1)

        self.era_duration_spin = MiniStepper(minimum=1, maximum=999999, edit_width=58)
        self.era_duration_spin.valueChanged.connect(self._on_inspector_duration)
        row.addWidget(self.era_duration_spin)
        row.addWidget(self._muted("años"))

        self.era_left_btn = QToolButton()
        self.era_left_btn.setArrowType(Qt.ArrowType.LeftArrow)
        self.era_left_btn.setToolTip("Mover la era hacia la izquierda")
        self.era_left_btn.clicked.connect(lambda: self._move_selected(-1))
        row.addWidget(self.era_left_btn)
        self.era_right_btn = QToolButton()
        self.era_right_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.era_right_btn.setToolTip("Mover la era hacia la derecha")
        self.era_right_btn.clicked.connect(lambda: self._move_selected(+1))
        row.addWidget(self.era_right_btn)
        self.era_remove_btn = QToolButton()
        self.era_remove_btn.setText("✕")
        self.era_remove_btn.setToolTip("Eliminar la era seleccionada")
        self.era_remove_btn.clicked.connect(self._remove_selected)
        row.addWidget(self.era_remove_btn)
        return row

    def _on_add_era(self) -> None:
        self.timeline.add_era()
        self.era_name_edit.setFocus()
        self.era_name_edit.selectAll()

    def _move_selected(self, delta: int) -> None:
        self.timeline.move_era(self.timeline.selected_index(), delta)

    def _remove_selected(self) -> None:
        self.timeline.remove_era(self.timeline.selected_index())

    def _on_inspector_name(self, text: str) -> None:
        if self._syncing or self._loading:
            return
        self.timeline.rename_era(self.timeline.selected_index(), text)

    def _on_inspector_duration(self) -> None:
        if self._syncing or self._loading:
            return
        self.timeline.set_era_duration(
            self.timeline.selected_index(), self.era_duration_spin.value()
        )

    def _on_era_selected(self, _index: int) -> None:
        self._refresh_inspector()

    def _refresh_inspector(self) -> None:
        eras = self.timeline.eras()
        sel = self.timeline.selected_index()
        self._syncing = True
        name = str(eras[sel]["name"])
        if self.era_name_edit.text() != name:  # no reposicionar el cursor al teclear
            self.era_name_edit.setText(name)
        self.era_duration_spin.blockSignals(True)
        self.era_duration_spin.setValue(int(eras[sel]["duration"]))
        self.era_duration_spin.blockSignals(False)
        self.era_left_btn.setEnabled(sel > 0)
        self.era_right_btn.setEnabled(sel < len(eras) - 1)
        self.era_remove_btn.setEnabled(len(eras) > 1)
        self._syncing = False

    # ── (a/b) presente ───────────────────────────────────────────────────

    def _on_timeline_changed(self) -> None:
        if self._loading:
            return
        self._refresh_present_row()
        self._refresh_inspector()
        self._emit_changed()

    def _present_index(self) -> int:
        return self.timeline.present()[0]

    def _refresh_present_row(self) -> None:
        eras = self.timeline.eras()
        index, year_within = self.timeline.present()
        name = str(eras[index]["name"]).strip() if eras else ""
        self.present_era_label.setText(f"«{name or '—'}»")
        is_last = index == len(eras) - 1
        maximum = 999999 if is_last else max(1, int(eras[index]["duration"]))
        self.present_year_spin.blockSignals(True)
        self.present_year_spin.setRange(1, maximum)
        self.present_year_spin.setValue(min(max(1, year_within), maximum))
        self.present_year_spin.blockSignals(False)
        self._refresh_present_derived()

    def _on_present_year_changed(self) -> None:
        if self._syncing or self._loading:
            return
        self.timeline.set_present_year_within(self.present_year_spin.value())

    def _on_present_date_changed(self) -> None:
        self._refresh_present_derived()
        self._emit_changed()

    def _sync_present_date_visibility(self) -> None:
        has_months = bool([r for r in self._month_rows if r["name"].text().strip()])
        has_week = bool([r for r in self._weekday_rows if r["name"].text().strip()])
        self.present_month_combo.setVisible(has_months)
        self.present_day_spin.setVisible(has_months)
        self.weekday_preview.setVisible(has_months and has_week)
        self._refresh_present_derived()

    def _refresh_present_derived(self) -> None:
        """Actualiza la vista previa del día de la semana y el chip de la timeline."""
        cfg = self._calendar_config()
        eras = self.timeline.eras()
        index, year_within = self.timeline.present()
        month = str(self.present_month_combo.currentData() or "")
        day = self.present_day_spin.value()
        # Vista previa del día de la semana real.
        if cfg.supports_exact_dates() and eras:
            era_start = sum(max(1, int(e["duration"])) for e in eras[:index])
            weekday = cfg.weekday_name(era_start, year_within, month, day)
            self.weekday_preview.setText(f"· {weekday}" if weekday else "")
        else:
            self.weekday_preview.setText("")
        # Chip de fecha exacta sobre la timeline.
        if cfg.has_months() and month:
            caption = f"año {year_within} · {month[:3]} {day}"
        else:
            caption = f"año {year_within}"
        self.timeline.set_present_caption(caption)

    # ── (d) meses ────────────────────────────────────────────────────────

    def _build_months_section(self) -> DisclosureSection:
        self.months_section = DisclosureSection("Meses (opcional)")
        self._months_grid = QGridLayout()
        self._months_grid.setContentsMargins(0, 0, 0, 0)
        self._months_grid.setHorizontalSpacing(6)
        self._months_grid.setVerticalSpacing(4)
        grid_holder = QWidget()
        grid_holder.setLayout(self._months_grid)
        self.months_section.add_widget(grid_holder)
        add_month = QPushButton("+ Añadir mes")
        add_month.clicked.connect(lambda: self._add_month_row(focus=True))
        self.months_section.add_widget(add_month)
        return self.months_section

    def _add_month_row(
        self, name: str = "", length: int | None = None, *, focus: bool = False
    ) -> None:
        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText("Nombre del mes")
        name_edit.textChanged.connect(self._on_months_changed)
        length_spin = MiniStepper(
            minimum=1, maximum=999, value=int(length) if length else DEFAULT_MONTH_LENGTH
        )
        length_spin.valueChanged.connect(self._on_present_date_changed)
        dias = self._muted("días")
        remove = QToolButton()
        remove.setText("✕")
        entry = {"name": name_edit, "length": length_spin, "dias": dias, "remove": remove}
        remove.clicked.connect(lambda: self._remove_month_row(entry))
        self._month_rows.append(entry)
        self._rebuild_months_grid()
        if focus:
            name_edit.setFocus()
        self._on_months_changed()

    def _rebuild_months_grid(self) -> None:
        while self._months_grid.count():
            self._months_grid.takeAt(0)
        for r, entry in enumerate(self._month_rows):
            self._months_grid.addWidget(entry["name"], r, 0)
            self._months_grid.addWidget(entry["length"], r, 1)
            self._months_grid.addWidget(entry["dias"], r, 2)
            self._months_grid.addWidget(entry["remove"], r, 3)
        self._months_grid.setColumnStretch(0, 1)

    def _remove_month_row(self, entry: dict[str, Any]) -> None:
        if entry not in self._month_rows:
            return
        self._month_rows.remove(entry)
        for key in ("name", "length", "dias", "remove"):
            entry[key].setParent(None)
            entry[key].deleteLater()
        self._rebuild_months_grid()
        self._on_months_changed()

    def _clear_month_rows(self) -> None:
        for entry in self._month_rows:
            for key in ("name", "length", "dias", "remove"):
                entry[key].setParent(None)
                entry[key].deleteLater()
        self._month_rows = []
        self._rebuild_months_grid()

    def _on_months_changed(self) -> None:
        self._refresh_present_month_combo()
        self._sync_present_date_visibility()
        self._emit_changed()

    def _refresh_present_month_combo(self) -> None:
        current = str(self.present_month_combo.currentData() or "")
        names = [r["name"].text().strip() for r in self._month_rows if r["name"].text().strip()]
        self.present_month_combo.blockSignals(True)
        self.present_month_combo.clear()
        for month in names:
            self.present_month_combo.addItem(month, month)
        if current:
            idx = self.present_month_combo.findData(current)
            if idx >= 0:
                self.present_month_combo.setCurrentIndex(idx)
        self.present_month_combo.blockSignals(False)

    # ── (d) semana ───────────────────────────────────────────────────────

    def _build_week_section(self) -> DisclosureSection:
        self.week_section = DisclosureSection("Días de la semana (opcional)")
        self._weekdays_grid = QGridLayout()
        self._weekdays_grid.setContentsMargins(0, 0, 0, 0)
        self._weekdays_grid.setHorizontalSpacing(6)
        self._weekdays_grid.setVerticalSpacing(4)
        grid_holder = QWidget()
        grid_holder.setLayout(self._weekdays_grid)
        self.week_section.add_widget(grid_holder)
        add_weekday = QPushButton("+ Añadir día")
        add_weekday.clicked.connect(lambda: self._add_weekday_row(focus=True))
        self.week_section.add_widget(add_weekday)
        anchor_row = QHBoxLayout()
        anchor_row.addWidget(self._muted("El primer día del calendario cae en:"))
        self.anchor_combo = QComboBox()
        self.anchor_combo.currentIndexChanged.connect(self._on_present_date_changed)
        anchor_row.addWidget(self.anchor_combo, 1)
        anchor_holder = QWidget()
        anchor_holder.setLayout(anchor_row)
        self.week_section.add_widget(anchor_holder)
        return self.week_section

    def _add_weekday_row(self, name: str = "", *, focus: bool = False) -> None:
        name_edit = QLineEdit(name)
        name_edit.setPlaceholderText("Nombre del día")
        name_edit.textChanged.connect(self._on_weekdays_changed)
        remove = QToolButton()
        remove.setText("✕")
        entry = {"name": name_edit, "remove": remove}
        remove.clicked.connect(lambda: self._remove_weekday_row(entry))
        self._weekday_rows.append(entry)
        self._rebuild_weekdays_grid()
        if focus:
            name_edit.setFocus()
        self._on_weekdays_changed()

    def _rebuild_weekdays_grid(self) -> None:
        while self._weekdays_grid.count():
            self._weekdays_grid.takeAt(0)
        for r, entry in enumerate(self._weekday_rows):
            self._weekdays_grid.addWidget(entry["name"], r, 0)
            self._weekdays_grid.addWidget(entry["remove"], r, 1)
        self._weekdays_grid.setColumnStretch(0, 1)

    def _remove_weekday_row(self, entry: dict[str, Any]) -> None:
        if entry not in self._weekday_rows:
            return
        self._weekday_rows.remove(entry)
        for key in ("name", "remove"):
            entry[key].setParent(None)
            entry[key].deleteLater()
        self._rebuild_weekdays_grid()
        self._on_weekdays_changed()

    def _clear_weekday_rows(self) -> None:
        for entry in self._weekday_rows:
            for key in ("name", "remove"):
                entry[key].setParent(None)
                entry[key].deleteLater()
        self._weekday_rows = []
        self._rebuild_weekdays_grid()

    def _on_weekdays_changed(self) -> None:
        self._refresh_anchor_combo()
        self._sync_present_date_visibility()
        self._emit_changed()

    def _refresh_anchor_combo(self) -> None:
        current = self.anchor_combo.currentIndex()
        names = [r["name"].text().strip() for r in self._weekday_rows if r["name"].text().strip()]
        self.anchor_combo.blockSignals(True)
        self.anchor_combo.clear()
        for weekday in names:
            self.anchor_combo.addItem(weekday)
        if 0 <= current < len(names):
            self.anchor_combo.setCurrentIndex(current)
        self.anchor_combo.blockSignals(False)

    # ── util ─────────────────────────────────────────────────────────────

    def _calendar_config(self) -> CalendarConfig:
        months = [
            (r["name"].text().strip(), int(r["length"].value()))
            for r in self._month_rows
            if r["name"].text().strip()
        ]
        weekdays = [
            r["name"].text().strip() for r in self._weekday_rows if r["name"].text().strip()
        ]
        anchor = self.anchor_combo.currentIndex() if self.anchor_combo.count() else 0
        return CalendarConfig(months=months, weekdays=weekdays, week_anchor=max(0, anchor))

    # ── emisión ──────────────────────────────────────────────────────────

    def _emit_changed(self) -> None:
        if self._loading:
            return
        self.changed.emit()
        if self._on_changed is not None:
            self._on_changed()

    # ── API pública ──────────────────────────────────────────────────────

    def value(self) -> dict[str, Any]:
        eras = [
            {"name": str(e["name"]).strip(), "duration": int(e["duration"])}
            for e in self.timeline.eras()
        ]
        index, year_within = self.timeline.present()
        months = [
            {"name": r["name"].text().strip(), "length": int(r["length"].value())}
            for r in self._month_rows
            if r["name"].text().strip()
        ]
        weekdays = [
            r["name"].text().strip() for r in self._weekday_rows if r["name"].text().strip()
        ]
        anchor = self.anchor_combo.currentIndex() if self.anchor_combo.count() else 0
        return {
            "calendar_name": self.name_edit.text().strip(),
            "description": self.desc_edit.text().strip(),
            "eras": eras,
            "present": {
                "era_index": index,
                "year_within": int(year_within),
                "month": str(self.present_month_combo.currentData() or ""),
                "day": int(self.present_day_spin.value()),
            },
            "months": months,
            "weekdays": weekdays,
            "week_anchor": max(0, anchor),
        }

    def set_value(self, view: dict[str, Any] | None) -> None:
        view = view or {}
        self._loading = True
        self.name_edit.setText(str(view.get("calendar_name", "") or ""))
        self.desc_edit.setText(str(view.get("description", "") or ""))

        eras = view.get("eras") or [{"name": "Presente", "duration": DEFAULT_ERA_DURATION}]
        present = view.get("present") if isinstance(view.get("present"), dict) else {}
        present_index = int(present.get("era_index", len(eras) - 1) or 0)
        present_year_within = max(1, int(present.get("year_within", 1) or 1))
        self.timeline.set_eras(eras, present_index, present_year_within)

        self._clear_month_rows()
        for month in view.get("months") or []:
            length = int(month.get("length", DEFAULT_MONTH_LENGTH) or 1)
            self._add_month_row(str(month.get("name", "")), length)

        self._clear_weekday_rows()
        for weekday in view.get("weekdays") or []:
            self._add_weekday_row(str(weekday))

        self._refresh_anchor_combo()
        anchor = int(view.get("week_anchor", 0) or 0)
        if self.anchor_combo.count():
            self.anchor_combo.setCurrentIndex(min(max(0, anchor), self.anchor_combo.count() - 1))

        self._refresh_present_month_combo()
        self.present_year_spin.blockSignals(True)
        self.present_year_spin.setValue(present_year_within)
        self.present_year_spin.blockSignals(False)
        month = str(present.get("month", "") or "")
        month_idx = self.present_month_combo.findData(month)
        if month_idx >= 0:
            self.present_month_combo.setCurrentIndex(month_idx)
        self.present_day_spin.setValue(max(1, int(present.get("day", 1) or 1)))

        self.months_section.set_expanded(bool(self._month_rows))
        self.week_section.set_expanded(bool(self._weekday_rows))
        self._loading = False
        self._refresh_present_row()
        self._refresh_inspector()
        self._sync_present_date_visibility()
