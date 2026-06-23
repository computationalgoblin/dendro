"""Panel de detalle de un HITO causal (BETA1-HITO-MULTI).

Se abre en el RightDrawer al clicar un hito en la cronología. Es el equivalente
para hitos del panel de detalle de entidades (node/tree): un editor enfocado de
UN solo hito —sin el calendario ni la lista de toda la cronología—, con los
campos relevantes de un hito (tipo, estado, año/fecha, participantes, racional).

La UI nunca escribe persistencia directa: todo va por el CausalMilestoneController.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.widgets.calendar_date_picker import CalendarDatePicker
from hosts.DesktopHostPySide.widgets.design_system import (
    AdvancedSection,
    Badge,
    SectionHeader,
    enum_human,
    make_scroll_area,
)
from hosts.DesktopHostPySide.widgets.milestone_chronology_view import (
    milestone_temporal_label,
)
from hosts.DesktopHostPySide.widgets.stepper import BotanicalSpinBox
from packages.domain.causal_milestone import CausalMilestoneType
from packages.domain.result import Error

_STATUS_OPTIONS = [
    ("candidate", "Semilla"),
    ("canon", "Canon"),
    ("hypothesis", "Hipotesis"),
    ("rejected", "Rechazado"),
    ("archived", "Archivado"),
]


def _metadata(obj: Any) -> dict[str, Any]:
    value = getattr(obj, "metadata", {}) or {}
    return dict(value) if isinstance(value, dict) else {}


def _raw_enum(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


class MilestoneDetailPanel(QWidget):
    """Editor enfocado de un hito (un solo hito, sin calendario ni lista)."""

    def __init__(
        self,
        ctx: Any,
        controller: Any,
        milestone_id: str,
        *,
        on_saved: Callable[[], None] | None = None,
        entity_controller: Any = None,
        relation_controller: Any = None,
        chronology_controller: Any = None,
        project_getter: Callable[[], Any] | None = None,
        on_start_walk: Callable[[str], None] | None = None,
    ):
        super().__init__()
        self.ctx = ctx
        self.controller = controller
        self.milestone_id = str(milestone_id or "")
        self.on_saved = on_saved
        self.on_start_walk = on_start_walk
        self.entity_controller = entity_controller
        self.relation_controller = relation_controller
        self.chronology_controller = chronology_controller
        self.project_getter = project_getter
        self._hito: Any | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(12)

        self.header = SectionHeader("Hito", "Detalle del hito causal.")
        root.addWidget(self.header)
        self.badge_row = QHBoxLayout()
        self.badge_row.setSpacing(6)
        self.badge_row.addStretch(1)
        root.addLayout(self.badge_row)

        body = QWidget()
        form = QFormLayout(body)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.title_edit = QLineEdit()
        self.type_combo = QComboBox()
        for member in CausalMilestoneType:
            self.type_combo.addItem(enum_human(member.value), member.value)
        self.status_combo = QComboBox()
        for raw, label in _STATUS_OPTIONS:
            self.status_combo.addItem(label, raw)
        self.year_edit = BotanicalSpinBox()
        self.year_edit.setRange(-999999999, 999999999)
        self.exact_date_picker = CalendarDatePicker(compact=True)
        self.temporal_edit = QLineEdit()
        self.temporal_edit.setPlaceholderText("Era, periodo o clave de calendario")
        self.summary_edit = QTextEdit()
        self.summary_edit.setMaximumHeight(80)
        self.body_edit = QTextEdit()
        self.body_edit.setMaximumHeight(110)
        self.participants_list = QListWidget()
        self.participants_list.setMaximumHeight(150)

        form.addRow("Titulo", self.title_edit)
        form.addRow("Tipo", self.type_combo)
        form.addRow("Estado", self.status_combo)
        form.addRow("Año", self.year_edit)
        form.addRow("Fecha exacta", self.exact_date_picker)
        form.addRow("Fecha / posicion", self.temporal_edit)
        form.addRow("Resumen", self.summary_edit)
        form.addRow("Cuerpo", self.body_edit)
        form.addRow("Entidades participantes", self.participants_list)
        root.addWidget(make_scroll_area(body), 1)

        # Vínculos del hito (solo lectura): relaciones causadas, causa/consecuencia.
        self.links_section = AdvancedSection("Vinculos del hito")
        self.links_label = QLabel("")
        self.links_label.setObjectName("mutedLabel")
        self.links_label.setWordWrap(True)
        self.links_section.body_layout.addWidget(self.links_label)
        root.addWidget(self.links_section)

        # CRON: punto de entrada al recorrido cronológico desde el hito.
        if self.on_start_walk is not None:
            self.walk_btn = QPushButton("Iniciar creación cronológica")
            self.walk_btn.setObjectName("startChronologyWalkButton")
            self.walk_btn.clicked.connect(
                lambda: self.on_start_walk(self.milestone_id) if self.on_start_walk else None
            )
            root.addWidget(self.walk_btn)

        buttons = QHBoxLayout()
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.setObjectName("deleteMilestoneButton")
        self.delete_btn.clicked.connect(self._delete)
        buttons.addWidget(self.delete_btn)
        buttons.addStretch(1)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save)
        buttons.addWidget(self.save_btn)
        root.addLayout(buttons)

        self._load()

    # ── datos ──────────────────────────────────────────────────────────────

    def _project(self) -> Any:
        if self.project_getter is not None:
            return self.project_getter()
        ps = getattr(self.controller, "ps", None)
        return getattr(ps, "active_project", None)

    def _entities(self) -> list[Any]:
        if self.entity_controller is not None and hasattr(self.entity_controller, "list_all"):
            return list(self.entity_controller.list_all())
        return list(getattr(self._project(), "entities", []) or [])

    def _entity_name(self, entity_id: str) -> str:
        for entity in self._entities():
            if str(getattr(entity, "id", "")) == str(entity_id):
                return str(getattr(entity, "name", "") or "Sin nombre")
        return "Elemento vinculado"

    def _chronology_metadata(self) -> dict[str, Any]:
        chronology = None
        if self.chronology_controller is not None and hasattr(self.chronology_controller, "get"):
            value = self.chronology_controller.get()
            if not isinstance(value, Error):
                chronology = getattr(value, "value", value)
        if chronology is None:
            chronology = getattr(self._project(), "project_chronology", None)
        value = getattr(chronology, "metadata", {}) or {}
        return dict(value) if isinstance(value, dict) else {}

    def _find_hito(self) -> Any | None:
        items = self.controller.list_all() if hasattr(self.controller, "list_all") else []
        for hito in items:
            if str(getattr(hito, "id", "")) == self.milestone_id:
                return hito
        return None

    def _load(self) -> None:
        hito = self._find_hito()
        self._hito = hito
        if hito is None:
            self.header.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return
        meta = _metadata(hito)
        self.title_edit.setText(str(getattr(hito, "title", "")))
        type_idx = self.type_combo.findData(_raw_enum(getattr(hito, "milestone_type", "")))
        self.type_combo.setCurrentIndex(type_idx if type_idx >= 0 else 0)
        status_idx = self.status_combo.findData(_raw_enum(getattr(hito, "status", "candidate")))
        self.status_combo.setCurrentIndex(status_idx if status_idx >= 0 else 0)
        year = getattr(hito, "year", None)
        if not isinstance(year, int) or isinstance(year, bool):
            chronology = getattr(self._project(), "project_chronology", None)
            year = int(getattr(chronology, "present_year", 0) or 0)
        self.year_edit.setValue(year)
        self.summary_edit.setPlainText(str(getattr(hito, "description", "")))
        self.body_edit.setPlainText(str(meta.get("body", "") or getattr(hito, "rationale", "")))
        self.temporal_edit.setText(str(meta.get("chronology_key", "") or ""))
        calendar_meta = self._chronology_metadata()
        exact_enabled = str(calendar_meta.get("mode") or "") == "full_calendar"
        self.exact_date_picker.setVisible(exact_enabled)
        self.exact_date_picker.set_calendar(calendar_meta)
        if exact_enabled:
            exact_date = meta.get("exact_date") if isinstance(meta.get("exact_date"), dict) else {}
            self.exact_date_picker.set_date(exact_date or calendar_meta.get("current_date") or {})

        # Participantes (multi-select). Se lee también el legacy primary_entity_id.
        selected = {str(v) for v in (getattr(hito, "affected_entity_ids", []) or []) if str(v)}
        legacy = str(meta.get("primary_entity_id", "") or "").strip()
        if legacy:
            selected.add(legacy)
        self.participants_list.clear()
        for entity in sorted(self._entities(), key=lambda e: str(getattr(e, "name", ""))):
            eid = str(getattr(entity, "id", ""))
            item = QListWidgetItem(str(getattr(entity, "name", "") or "Sin nombre"))
            item.setData(Qt.ItemDataRole.UserRole, eid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = Qt.CheckState.Checked if eid in selected else Qt.CheckState.Unchecked
            item.setCheckState(checked)
            self.participants_list.addItem(item)

        self._refresh_badges(hito)
        self._refresh_links(hito)

    def _refresh_badges(self, hito: Any) -> None:
        while self.badge_row.count() > 1:  # conserva el stretch final
            item = self.badge_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        type_label = enum_human(_raw_enum(getattr(hito, "milestone_type", "")))
        status_label = enum_human(_raw_enum(getattr(hito, "status", "")))
        self.badge_row.insertWidget(0, Badge(type_label, "info"))
        self.badge_row.insertWidget(1, Badge(status_label, "neutral"))
        self.badge_row.insertWidget(2, Badge(milestone_temporal_label(hito), "gold"))

    def _refresh_links(self, hito: Any) -> None:
        lines: list[str] = []
        relations = [str(v) for v in (getattr(hito, "caused_relation_ids", []) or []) if str(v)]
        if relations:
            lines.append(f"Relaciones causadas: {len(relations)}")
        parents = [str(v) for v in (getattr(hito, "causal_parent_hito_ids", []) or []) if str(v)]
        children = [str(v) for v in (getattr(hito, "causal_child_hito_ids", []) or []) if str(v)]
        if parents:
            lines.append(f"Causa de (hitos previos): {len(parents)}")
        if children:
            lines.append(f"Consecuencias (hitos posteriores): {len(children)}")
        sources = [str(v) for v in (getattr(hito, "source_ids", []) or []) if str(v)]
        if sources:
            lines.append(f"Fuentes: {len(sources)}")
        self.links_label.setText("\n".join(lines) if lines else "Sin vinculos adicionales.")

    # ── acciones ───────────────────────────────────────────────────────────

    def _checked_participants(self) -> list[str]:
        result: list[str] = []
        for row in range(self.participants_list.count()):
            item = self.participants_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                eid = str(item.data(Qt.ItemDataRole.UserRole) or "")
                if eid:
                    result.append(eid)
        return result

    def _save(self) -> None:
        if self._hito is None:
            return
        meta = _metadata(self._hito)
        meta["chronology_key"] = self.temporal_edit.text().strip()
        meta["body"] = self.body_edit.toPlainText().strip()
        meta.pop("primary_entity_id", None)  # BETA1-HITO-MULTI: sin "entidad principal"
        calendar_meta = self._chronology_metadata()
        if str(calendar_meta.get("mode") or "") == "full_calendar":
            meta["exact_date"] = self.exact_date_picker.date()
            label = self.exact_date_picker.date_label()
            if label:
                meta["chronology_key"] = label
        payload = {
            "title": self.title_edit.text().strip() or "Hito sin titulo",
            "milestone_type": str(self.type_combo.currentData() or "origen"),
            "status": str(self.status_combo.currentData() or "candidate"),
            "description": self.summary_edit.toPlainText().strip(),
            "rationale": self.body_edit.toPlainText().strip(),
            "year": int(self.year_edit.value()),
            "affected_entity_ids": self._checked_participants(),
            "metadata": meta,
        }
        result = self.controller.update(self.milestone_id, payload)
        if isinstance(result, Error):
            self.ctx.log("warning", result.error) if self.ctx is not None else None
            return
        if self.on_saved:
            self.on_saved()
        self._load()

    def _delete(self) -> None:
        if self._hito is None or not hasattr(self.controller, "delete"):
            return
        reply = QMessageBox.question(
            self,
            "Eliminar hito",
            "¿Eliminar este hito de la cronologia?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        result = self.controller.delete(self.milestone_id)
        if isinstance(result, Error):
            if self.ctx is not None:
                self.ctx.log("warning", result.error)
            return
        if self.on_saved:
            self.on_saved()
        drawer = getattr(self.ctx, "drawer", None)
        if drawer is not None and hasattr(drawer, "close"):
            drawer.close()
