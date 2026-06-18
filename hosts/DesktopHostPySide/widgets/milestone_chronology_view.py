"""Milestone chronology drawer view for Creation (H03).

The view is UI-only: milestones remain `CausalMilestone` domain objects and are
never represented as graph/canvas nodes.
"""

from __future__ import annotations

from hashlib import sha1
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.design_system import (
    Badge,
    Card,
    EmptyState,
    SectionHeader,
    enum_human,
    make_scroll_area,
)
from hosts.DesktopHostPySide.widgets.calendar_date_picker import CalendarDatePicker
from hosts.DesktopHostPySide.widgets.chronology_config_panel import ChronologyConfigPanel
from packages.domain.result import Error


def _raw_enum(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _metadata(obj: Any) -> dict[str, Any]:
    value = getattr(obj, "metadata", {}) or {}
    return dict(value) if isinstance(value, dict) else {}


def _chronology_metadata(chronology: Any) -> dict[str, Any]:
    value = getattr(chronology, "metadata", {}) or {}
    return dict(value) if isinstance(value, dict) else {}


def milestone_sort_value(milestone: Any) -> tuple[int, Any, str]:
    """Return a stable chronology key without imposing a Gregorian calendar."""

    meta = _metadata(milestone)
    sort_index = meta.get("sort_index")

    # BETA1-G03: el año diegético (G02) es el tiempo canónico; el
    # sort_index manual desempata dentro del mismo año.
    year = getattr(milestone, "year", None)
    if isinstance(year, int) and not isinstance(year, bool):
        try:
            tiebreak = float(sort_index)
        except (TypeError, ValueError):
            tiebreak = 0.0
        return (0, (float(year), tiebreak), str(getattr(milestone, "title", "")))
    try:
        return (0, float(sort_index), str(getattr(milestone, "title", "")))
    except (TypeError, ValueError):
        pass

    for key in ("chronology_key", "calendar_key", "calendar_date"):
        value = str(meta.get(key, "") or "").strip()
        if value:
            return (1, value.lower(), str(getattr(milestone, "title", "")))

    temporality = getattr(milestone, "temporality", None)
    for attr in ("absolute_date", "world_date", "relative_date", "period", "era"):
        value = str(getattr(temporality, attr, "") or "").strip()
        if value:
            return (2, value.lower(), str(getattr(milestone, "title", "")))

    created = str(getattr(milestone, "created_at", "") or "").strip()
    return (9, created.lower(), str(getattr(milestone, "title", "")))


def milestone_temporal_label(milestone: Any) -> str:
    meta = _metadata(milestone)
    for key in ("chronology_key", "calendar_key", "calendar_date"):
        value = str(meta.get(key, "") or "").strip()
        if value:
            return value
    exact = meta.get("exact_date")
    if isinstance(exact, dict):
        era = str(exact.get("era", "") or "").strip()
        month = str(exact.get("month", "") or "").strip()
        year = str(exact.get("year", "") or "").strip()
        day = str(exact.get("day", "") or "").strip()
        if era and month and year and day:
            return f"{era}, ano {year}, {month} {day}"
    sort_index = meta.get("sort_index")
    if sort_index not in (None, ""):
        return f"Orden {sort_index}"
    temporality = getattr(milestone, "temporality", None)
    for attr in ("absolute_date", "world_date", "relative_date", "period", "era"):
        value = str(getattr(temporality, attr, "") or "").strip()
        if value:
            return value
    # BETA1-G03: sin etiqueta manual, el año diegético ubica el hito
    year = getattr(milestone, "year", None)
    if isinstance(year, int) and not isinstance(year, bool):
        return f"Año {year}"
    return "Sin ubicar"


def milestone_primary_entity_id(milestone: Any) -> str:
    meta = _metadata(milestone)
    explicit = str(meta.get("primary_entity_id", "") or "").strip()
    if explicit:
        return explicit
    affected = list(getattr(milestone, "affected_entity_ids", []) or [])
    return str(affected[0]) if affected else ""


def stable_entity_color(entity: Any | None, fallback: str = "") -> str:
    """Resolve a user-facing color swatch from entity metadata or stable hash."""

    if entity is not None:
        meta = getattr(entity, "custom_metadata", {}) or {}
        if isinstance(meta, dict):
            for key in ("color", "ui_color", "accent_color"):
                value = str(meta.get(key, "") or "").strip()
                if value.startswith("#") and len(value) in (4, 7):
                    return value
        fallback = str(getattr(entity, "name", "") or getattr(entity, "id", "") or fallback)
    digest = sha1(str(fallback or "milestone").encode("utf-8")).hexdigest()
    palette = ["#7A733D", "#58744A", "#5F6F8F", "#8A6849", "#7C5E7F", "#4F7C78"]
    return palette[int(digest[:2], 16) % len(palette)]


class MilestoneChronologyView(QWidget):
    """Filterable milestone chronology/detail drawer for Creation."""

    def __init__(
        self,
        controller: Any,
        *,
        project_getter: Callable[[], Any] | None = None,
        entity_controller: Any = None,
        relation_controller: Any = None,
        layer_controller: Any = None,
        chronology_controller: Any = None,
        on_saved: Callable[[], None] | None = None,
        initial_entity_id: str = "",
        initial_relation_id: str = "",
        initial_hito_id: str = "",
    ):
        super().__init__()
        self.controller = controller
        self.project_getter = project_getter
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.layer_controller = layer_controller
        self.chronology_controller = chronology_controller
        self.on_saved = on_saved
        self._selected_hito_id = str(initial_hito_id or "")
        self._initial_entity_id = str(initial_entity_id or "")
        self._relation_filter_id = str(initial_relation_id or "")
        self._selected_hito: Any | None = None
        self._cards_by_id: dict[str, Card] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(12)
        root.addWidget(SectionHeader("Cronologia", "Hitos causales del proyecto, fuera del grafo principal."))
        if self.chronology_controller is not None:
            root.addWidget(ChronologyConfigPanel(self.chronology_controller, on_saved=self.on_saved, compact=True))

        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filtrar por titulo, resumen o cuerpo")
        self.search_input.textChanged.connect(self.refresh)
        filter_row.addWidget(self.search_input, 2)
        self.entity_filter = QComboBox()
        self.entity_filter.currentIndexChanged.connect(self.refresh)
        filter_row.addWidget(self.entity_filter, 1)
        root.addLayout(filter_row)
        self.relation_filter_label = QLabel("")
        self.relation_filter_label.setObjectName("mutedLabel")
        self.relation_filter_label.setWordWrap(True)
        root.addWidget(self.relation_filter_label)

        action_row = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setObjectName("mutedLabel")
        action_row.addWidget(self.count_label)
        action_row.addStretch(1)
        self.create_btn = QPushButton("Crear hito")
        self.create_btn.setToolTip("Crear un hito minimo por la ruta segura existente")
        self.create_btn.clicked.connect(self._create_minimal_milestone)
        action_row.addWidget(self.create_btn)
        root.addLayout(action_row)

        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        root.addWidget(make_scroll_area(self.cards_widget), 1)

        self.detail_frame = QFrame()
        self.detail_frame.setObjectName("milestoneDetail")
        self.detail_frame.setStyleSheet(
            "QFrame#milestoneDetail { background: #FFFDF7; border: 1px solid #D8D6C8; border-radius: 12px; }"
        )
        detail = QVBoxLayout(self.detail_frame)
        detail.setContentsMargins(12, 10, 12, 12)
        detail.setSpacing(8)
        detail.addWidget(SectionHeader("Detalle", "Edita campos narrativos sin datos tecnicos."))
        form = QFormLayout()
        self.title_edit = QLineEdit()
        self.summary_edit = QTextEdit()
        self.summary_edit.setMaximumHeight(76)
        self.body_edit = QTextEdit()
        self.body_edit.setMaximumHeight(96)
        self.temporal_edit = QLineEdit()
        self.temporal_edit.setPlaceholderText("Era, periodo o clave de calendario")
        self.exact_date_picker = CalendarDatePicker(compact=True)
        self.exact_date_picker.setObjectName("milestoneExactDatePicker")
        # BETA1-G03: año diegético del hito (G02) — tiempo canónico
        self.year_edit = QSpinBox()
        self.year_edit.setRange(-999999999, 999999999)
        self.sort_edit = QSpinBox()
        self.sort_edit.setRange(-999999, 999999)
        self.primary_entity_combo = QComboBox()
        self.status_combo = QComboBox()
        for raw, label in [
            ("candidate", "Semilla"),
            ("canon", "Canon"),
            ("hypothesis", "Hipotesis"),
            ("rejected", "Rechazado"),
            ("archived", "Archivado"),
        ]:
            self.status_combo.addItem(label, raw)
        form.addRow("Titulo", self.title_edit)
        form.addRow("Resumen", self.summary_edit)
        form.addRow("Cuerpo", self.body_edit)
        form.addRow("Año", self.year_edit)
        form.addRow("Fecha / posicion", self.temporal_edit)
        form.addRow("Fecha exacta", self.exact_date_picker)
        form.addRow("Orden relativo", self.sort_edit)
        form.addRow("Entidad principal", self.primary_entity_combo)
        form.addRow("Estado", self.status_combo)
        detail.addLayout(form)
        self.linked_label = QLabel("")
        self.linked_label.setWordWrap(True)
        self.linked_label.setObjectName("mutedLabel")
        detail.addWidget(self.linked_label)
        buttons = QHBoxLayout()
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setObjectName("deleteMilestoneButton")
        self.delete_btn.clicked.connect(lambda: self._delete_selected_milestone())
        buttons.addWidget(self.delete_btn)
        buttons.addStretch(1)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._populate_detail)
        buttons.addWidget(self.cancel_btn)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save_detail)
        buttons.addWidget(self.save_btn)
        detail.addLayout(buttons)
        root.addWidget(self.detail_frame)

        self._populate_entity_filter()
        if self._initial_entity_id:
            idx = self.entity_filter.findData(self._initial_entity_id)
            if idx >= 0:
                self.entity_filter.setCurrentIndex(idx)
        self.refresh()

    def project(self) -> Any:
        if self.project_getter is not None:
            return self.project_getter()
        ps = getattr(self.controller, "ps", None)
        return getattr(ps, "active_project", None)

    def milestones(self) -> list[Any]:
        if hasattr(self.controller, "list_all"):
            return list(self.controller.list_all())
        project = self.project()
        return list(getattr(project, "causal_milestones", []) or [])

    def chronology(self) -> Any | None:
        if self.chronology_controller is not None and hasattr(self.chronology_controller, "get"):
            value = self.chronology_controller.get()
            if not isinstance(value, Error):
                return getattr(value, "value", value)
        project = self.project()
        return getattr(project, "project_chronology", None)

    def chronology_metadata(self) -> dict[str, Any]:
        return _chronology_metadata(self.chronology())

    def entities(self) -> list[Any]:
        if self.entity_controller is not None and hasattr(self.entity_controller, "list_all"):
            return list(self.entity_controller.list_all())
        project = self.project()
        return list(getattr(project, "entities", []) or [])

    def entity_by_id(self, entity_id: str) -> Any | None:
        for entity in self.entities():
            if str(getattr(entity, "id", "")) == str(entity_id):
                return entity
        return None

    def entity_name(self, entity_id: str) -> str:
        entity = self.entity_by_id(entity_id)
        return str(getattr(entity, "name", "") or "Elemento vinculado") if entity else "Elemento vinculado"

    def relation_by_id(self, relation_id: str) -> Any | None:
        if self.relation_controller is not None and hasattr(self.relation_controller, "get"):
            value = self.relation_controller.get(relation_id)
            if isinstance(value, Error):
                return None
            value = getattr(value, "value", value)
            if value is not None:
                return value
        if self.relation_controller is not None and hasattr(self.relation_controller, "list_all"):
            for relation in self.relation_controller.list_all():
                if str(getattr(relation, "id", "")) == str(relation_id):
                    return relation
        project = self.project()
        for relation in getattr(project, "relations", []) or []:
            if str(getattr(relation, "id", "")) == str(relation_id):
                return relation
        return None

    def relation_label(self, relation_id: str) -> str:
        relation = self.relation_by_id(relation_id)
        if relation is None:
            return "relacion seleccionada"
        source = self.entity_name(str(getattr(relation, "source_id", "") or ""))
        target = self.entity_name(str(getattr(relation, "target_id", "") or ""))
        return f"{source} - {target}"

    def _populate_entity_filter(self) -> None:
        current = self.entity_filter.currentData()
        self.entity_filter.blockSignals(True)
        self.entity_filter.clear()
        self.entity_filter.addItem("Todas las entidades", "")
        for entity in sorted(self.entities(), key=lambda e: str(getattr(e, "name", ""))):
            self.entity_filter.addItem(str(getattr(entity, "name", "") or "Sin nombre"), str(getattr(entity, "id", "")))
        if current:
            idx = self.entity_filter.findData(current)
            if idx >= 0:
                self.entity_filter.setCurrentIndex(idx)
        self.entity_filter.blockSignals(False)

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._cards_by_id.clear()

    def filtered_milestones(self) -> list[Any]:
        text = self.search_input.text().strip().lower()
        entity_id = str(self.entity_filter.currentData() or "")
        relation_id = self._relation_filter_id
        items = sorted(self.milestones(), key=milestone_sort_value)
        result = []
        for hito in items:
            haystack = " ".join([
                str(getattr(hito, "title", "")),
                str(getattr(hito, "description", "")),
                str(getattr(hito, "rationale", "")),
                str(_metadata(hito).get("body", "")),
            ]).lower()
            if text and text not in haystack:
                continue
            affected = [str(v) for v in (getattr(hito, "affected_entity_ids", []) or [])]
            if entity_id and entity_id not in affected and milestone_primary_entity_id(hito) != entity_id:
                continue
            caused = [str(v) for v in (getattr(hito, "caused_relation_ids", []) or [])]
            if relation_id and relation_id not in caused:
                continue
            result.append(hito)
        return result

    def refresh(self) -> None:
        self._populate_entity_filter()
        if self._relation_filter_id:
            self.relation_filter_label.setText("Filtro de relacion: " + self.relation_label(self._relation_filter_id))
            self.relation_filter_label.setVisible(True)
        else:
            self.relation_filter_label.setVisible(False)
        self._clear_cards()
        hitos = self.filtered_milestones()
        self.count_label.setText(f"{len(hitos)} hito(s)")
        if not hitos:
            self.cards_layout.addWidget(EmptyState("No hay hitos todavia.", "Crea un hito para empezar la cronologia causal."))
            self.cards_layout.addStretch(1)
            self._selected_hito = None
            self.detail_frame.setVisible(False)
            return

        for hito in hitos:
            self.cards_layout.addWidget(self._milestone_card(hito))
        self.cards_layout.addStretch(1)
        if self._selected_hito_id:
            self.select_milestone(self._selected_hito_id)
        else:
            self.detail_frame.setVisible(False)

    def _milestone_card(self, hito: Any) -> Card:
        title = str(getattr(hito, "title", "") or "Hito sin titulo")
        subtitle = milestone_temporal_label(hito)
        card = Card(title, subtitle)
        card.setObjectName("milestoneCard")
        card.setProperty("hitoTitle", title)
        row = card.add_row()
        primary_id = milestone_primary_entity_id(hito)
        primary = self.entity_by_id(primary_id)
        color = stable_entity_color(primary, primary_id or title)
        swatch = QLabel("")
        swatch.setObjectName("milestoneColorSwatch")
        swatch.setFixedSize(14, 14)
        swatch.setStyleSheet(f"background: {color}; border-radius: 7px;")
        row.addWidget(swatch)
        if primary_id:
            row.addWidget(Badge(self.entity_name(primary_id), "info"))
        row.addWidget(Badge(enum_human(_raw_enum(getattr(hito, "status", ""))), "neutral"))
        row.addStretch(1)
        delete = QPushButton("Eliminar")
        delete.setObjectName("deleteMilestoneCardButton")
        delete.setToolTip("Eliminar este hito de la cronologia")
        delete.clicked.connect(lambda _=False, hid=str(getattr(hito, "id", "")): self._delete_milestone(hid))
        row.addWidget(delete)
        detail = QPushButton("Detalle")
        detail.clicked.connect(lambda: self.select_milestone(str(getattr(hito, "id", ""))))
        row.addWidget(detail)

        summary = str(getattr(hito, "description", "") or getattr(hito, "rationale", "") or "").strip()
        if summary:
            card.add_text(summary[:220], muted=True)
        chips = [self.entity_name(eid) for eid in (getattr(hito, "affected_entity_ids", []) or [])]
        if chips:
            card.add_text("Vinculos: " + ", ".join(chips[:6]), muted=True)
        self._cards_by_id[str(getattr(hito, "id", ""))] = card
        return card

    def select_milestone(self, hito_id: str) -> None:
        self._selected_hito_id = str(hito_id)
        self._selected_hito = None
        for hito in self.milestones():
            if str(getattr(hito, "id", "")) == self._selected_hito_id:
                self._selected_hito = hito
                break
        self._populate_detail()

    def _populate_detail(self) -> None:
        hito = self._selected_hito
        if hito is None:
            self.detail_frame.setVisible(False)
            return
        self.detail_frame.setVisible(True)
        meta = _metadata(hito)
        self.title_edit.setText(str(getattr(hito, "title", "")))
        self.summary_edit.setPlainText(str(getattr(hito, "description", "")))
        self.body_edit.setPlainText(str(meta.get("body", "") or getattr(hito, "rationale", "")))
        self.temporal_edit.setText(str(meta.get("chronology_key", "") or ""))
        calendar_meta = self.chronology_metadata()
        exact_enabled = str(calendar_meta.get("mode") or "") == "full_calendar"
        self.exact_date_picker.setVisible(exact_enabled)
        self.exact_date_picker.set_calendar(calendar_meta)
        if exact_enabled:
            exact_date = meta.get("exact_date") if isinstance(meta.get("exact_date"), dict) else {}
            self.exact_date_picker.set_date(exact_date or calendar_meta.get("current_date") or {})
            if not self.temporal_edit.text().strip():
                self.temporal_edit.setText(self.exact_date_picker.date_label())
        try:
            self.sort_edit.setValue(int(meta.get("sort_index", 0) or 0))
        except (TypeError, ValueError):
            self.sort_edit.setValue(0)
        # BETA1-G03: año (None pre-migración → present_year del calendario)
        year = getattr(hito, "year", None)
        if not isinstance(year, int) or isinstance(year, bool):
            year = int(getattr(self.chronology(), "present_year", 0) or 0)
        self.year_edit.setValue(year)
        self.primary_entity_combo.blockSignals(True)
        self.primary_entity_combo.clear()
        self.primary_entity_combo.addItem("Sin entidad principal", "")
        for entity in sorted(self.entities(), key=lambda e: str(getattr(e, "name", ""))):
            self.primary_entity_combo.addItem(str(getattr(entity, "name", "") or "Sin nombre"), str(getattr(entity, "id", "")))
        primary_id = milestone_primary_entity_id(hito)
        idx = self.primary_entity_combo.findData(primary_id)
        if idx >= 0:
            self.primary_entity_combo.setCurrentIndex(idx)
        self.primary_entity_combo.blockSignals(False)
        status_raw = _raw_enum(getattr(hito, "status", "candidate"))
        status_idx = self.status_combo.findData(status_raw)
        self.status_combo.setCurrentIndex(status_idx if status_idx >= 0 else 0)
        linked = [self.entity_name(eid) for eid in (getattr(hito, "affected_entity_ids", []) or [])]
        self.linked_label.setText("Entidades vinculadas: " + (", ".join(linked) if linked else "ninguna"))

    def _save_detail(self) -> None:
        hito = self._selected_hito
        if hito is None:
            return
        hito_id = str(getattr(hito, "id", ""))
        meta = _metadata(hito)
        primary_id = str(self.primary_entity_combo.currentData() or "")
        meta.update({
            "sort_index": int(self.sort_edit.value()),
            "chronology_key": self.temporal_edit.text().strip(),
            "primary_entity_id": primary_id,
            "body": self.body_edit.toPlainText().strip(),
        })
        calendar_meta = self.chronology_metadata()
        if str(calendar_meta.get("mode") or "") == "full_calendar":
            exact_date = self.exact_date_picker.date()
            exact_label = self.exact_date_picker.date_label()
            meta["exact_date"] = exact_date
            if exact_label:
                meta["chronology_key"] = exact_label
        affected = [str(v) for v in (getattr(hito, "affected_entity_ids", []) or []) if str(v)]
        if primary_id and primary_id not in affected:
            affected.insert(0, primary_id)
        payload = {
            "title": self.title_edit.text().strip() or "Hito sin titulo",
            "description": self.summary_edit.toPlainText().strip(),
            "rationale": self.body_edit.toPlainText().strip(),
            "status": str(self.status_combo.currentData() or "candidate"),
            "affected_entity_ids": affected,
            "metadata": meta,
            "year": int(self.year_edit.value()),  # BETA1-G03
        }
        result = self.controller.update(hito_id, payload)
        if isinstance(result, Error):
            self.count_label.setText(result.error)
            return
        if self.on_saved:
            self.on_saved()
        self.refresh()
        self.select_milestone(hito_id)

    def _delete_selected_milestone(self) -> None:
        hito = self._selected_hito
        if hito is None:
            return
        self._delete_milestone(str(getattr(hito, "id", "")))

    def _delete_milestone(self, hito_id: str, *, confirm: bool = True) -> None:
        if not hasattr(self.controller, "delete"):
            self.count_label.setText("Eliminacion no disponible")
            return
        hito_id = str(hito_id or "").strip()
        if not hito_id:
            return
        if confirm:
            reply = QMessageBox.question(
                self,
                "Eliminar hito",
                "Eliminar este hito de la cronologia?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        result = self.controller.delete(hito_id)
        if isinstance(result, Error):
            self.count_label.setText(result.error)
            return
        if self._selected_hito_id == hito_id:
            self._selected_hito_id = ""
            self._selected_hito = None
        if self.on_saved:
            self.on_saved()
        self.refresh()

    def _create_minimal_milestone(self) -> None:
        if not hasattr(self.controller, "create_manual"):
            self.count_label.setText("Creacion no disponible")
            return
        existing = self.milestones()
        payload = {
            "title": "Nuevo hito",
            "description": "",
            "metadata": {"sort_index": len(existing) + 1},
        }
        result = self.controller.create_manual(payload)
        if isinstance(result, Error):
            self.count_label.setText(result.error)
            return
        created = getattr(result, "value", None)
        self._selected_hito_id = str(getattr(created, "id", ""))
        if self.on_saved:
            self.on_saved()
        self.refresh()
