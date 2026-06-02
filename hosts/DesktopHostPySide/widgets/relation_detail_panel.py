"""Relation detail panel for B31-T05.

RightDrawer content opened from the graph when an edge is selected. It reads and
updates relations through RelationController; source/target are shown as human
references in normal mode.
"""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.design_system import Badge, enum_human, human_ref
from packages.domain.entity import CanonState, VisibilityState
from packages.domain.relation import Direction, IntensityLevel, RelationType
from packages.domain.result import Error


def _enum_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


class RelationDetailPanel(QWidget):
    """Contextual relation editor shown inside the global RightDrawer."""

    def __init__(self, ctx: AppContext, relation_controller, relation_id: str, *, on_saved=None):
        super().__init__()
        self.ctx = ctx
        self.relation_controller = relation_controller
        self.relation_id = relation_id
        self.on_saved = on_saved
        self._relation = None
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.title = QLabel("Relación")
        self.title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ECEFF4;")
        self.title.setWordWrap(True)
        header.addWidget(self.title, 1)
        self.type_badge = Badge("Relación", "info")
        header.addWidget(self.type_badge)
        layout.addLayout(header)

        self.summary = QLabel("")
        self.summary.setObjectName("mutedLabel")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.ends_box = QGroupBox("Extremos")
        ends_layout = QVBoxLayout(self.ends_box)
        self.source_label = QLabel("Origen: —")
        self.target_label = QLabel("Destino: —")
        for widget in [self.source_label, self.target_label]:
            widget.setObjectName("mutedLabel")
            widget.setWordWrap(True)
            ends_layout.addWidget(widget)
        layout.addWidget(self.ends_box)

        form_box = QGroupBox("Ficha")
        form = QFormLayout(form_box)
        self.type_combo = QComboBox()
        for item in RelationType:
            self.type_combo.addItem(enum_human(item.value), item.value)
        self.direction_combo = QComboBox()
        for item in Direction:
            self.direction_combo.addItem(enum_human(item.value), item.value)
        self.intensity_combo = QComboBox()
        for item in IntensityLevel:
            self.intensity_combo.addItem(enum_human(item.value), item.value)
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(110)
        self.temporality_edit = QTextEdit()
        self.temporality_edit.setMaximumHeight(70)
        self.causality_edit = QTextEdit()
        self.causality_edit.setMaximumHeight(70)
        self.source_edit = QTextEdit()
        self.source_edit.setMaximumHeight(70)
        self.validity_edit = QTextEdit()
        self.validity_edit.setMaximumHeight(78)
        self.tags_edit = QTextEdit()
        self.tags_edit.setMaximumHeight(60)
        self.canon_combo = QComboBox()
        for item in CanonState:
            self.canon_combo.addItem(enum_human(item.value), item.value)
        self.visibility_combo = QComboBox()
        for item in VisibilityState:
            self.visibility_combo.addItem(enum_human(item.value), item.value)
        form.addRow("Tipo:", self.type_combo)
        form.addRow("Dirección:", self.direction_combo)
        form.addRow("Intensidad:", self.intensity_combo)
        form.addRow("Descripción:", self.description_edit)
        form.addRow("Temporalidad:", self.temporality_edit)
        form.addRow("Causalidad:", self.causality_edit)
        form.addRow("Evidencia/fuente:", self.source_edit)
        form.addRow("Condiciones:", self.validity_edit)
        form.addRow("Tags:", self.tags_edit)
        form.addRow("Canon:", self.canon_combo)
        form.addRow("Visibilidad:", self.visibility_combo)
        layout.addWidget(form_box)

        self.ai_box = QGroupBox("IA contextual")
        ai_layout = QVBoxLayout(self.ai_box)
        for label in ["Profundizar relación", "Sugerir evolución", "Detectar contradicción"]:
            button = QPushButton(f"{label} · Requiere IA contextual")
            button.setEnabled(False)
            ai_layout.addWidget(button)
        layout.addWidget(self.ai_box)

        self.technical_box = QGroupBox("Datos técnicos")
        technical_layout = QVBoxLayout(self.technical_box)
        self.technical_text = QTextEdit()
        self.technical_text.setReadOnly(True)
        self.technical_text.setMaximumHeight(120)
        technical_layout.addWidget(self.technical_text)
        layout.addWidget(self.technical_box)

        actions = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.refresh)
        self.archive_btn = QPushButton("Archivar")
        self.archive_btn.clicked.connect(self.archive)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self.save)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.archive_btn)
        actions.addStretch()
        actions.addWidget(self.save_btn)
        layout.addLayout(actions)
        layout.addStretch()
        self.set_advanced_mode(self.ctx.advanced_mode)

    def _project(self):
        pc = self.ctx.project_controller
        return pc.ps.active_project if pc else None

    def _entity_by_id(self, entity_id: str):
        project = self._project()
        if project is None:
            return None
        for entity in getattr(project, "entities", []) or []:
            if getattr(entity, "id", None) == entity_id:
                return entity
        return None

    def _human_entity_ref(self, entity_id: str) -> str:
        entity = self._entity_by_id(entity_id)
        if entity is None:
            return "Entidad no encontrada"
        return human_ref(getattr(entity, "name", "Sin nombre"), enum_human(_enum_value(getattr(entity, "entity_type", None), "entidad")))

    def _set_combo_value(self, combo: QComboBox, value: str):
        idx = combo.findData(value)
        if idx < 0:
            idx = combo.findText(enum_human(value))
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def refresh(self):
        result = self.relation_controller.get(self.relation_id)
        if isinstance(result, Error):
            self.title.setText("Relación no encontrada")
            self.summary.setText(result.error)
            self.save_btn.setEnabled(False)
            self.archive_btn.setEnabled(False)
            return
        relation = result.value
        self._relation = relation
        kind = _enum_value(getattr(relation, "relation_type", None), "relación")
        self.title.setText(enum_human(kind))
        self.type_badge.setText(enum_human(kind))
        source_ref = self._human_entity_ref(getattr(relation, "source_id", ""))
        target_ref = self._human_entity_ref(getattr(relation, "target_id", ""))
        self.summary.setText(f"{source_ref} → {target_ref}")
        self.source_label.setText(f"Origen: {source_ref}")
        self.target_label.setText(f"Destino: {target_ref}")
        self._set_combo_value(self.type_combo, kind)
        self._set_combo_value(self.direction_combo, _enum_value(getattr(relation, "direction", None), ""))
        self._set_combo_value(self.intensity_combo, _enum_value(getattr(relation, "intensity", None), ""))
        self.description_edit.setPlainText(getattr(relation, "description", "") or "")
        self.temporality_edit.setPlainText(getattr(relation, "temporality", "") or "")
        self.causality_edit.setPlainText(getattr(relation, "causality", "") or "")
        self.source_edit.setPlainText(getattr(relation, "source", "") or "")
        self.validity_edit.setPlainText("\n".join(getattr(relation, "validity_conditions", []) or []))
        self.tags_edit.setPlainText("\n".join(getattr(relation, "tags", []) or []))
        self._set_combo_value(self.canon_combo, _enum_value(getattr(relation, "canon_state", None), ""))
        self._set_combo_value(self.visibility_combo, _enum_value(getattr(relation, "visibility_state", None), ""))
        self._refresh_technical(relation)
        self.set_advanced_mode(self.ctx.advanced_mode)

    def _refresh_technical(self, relation):
        payload = {
            "id": getattr(relation, "id", ""),
            "source_id": getattr(relation, "source_id", ""),
            "target_id": getattr(relation, "target_id", ""),
            "custom_metadata": getattr(relation, "custom_metadata", {}),
            "custom_relation_type_id": getattr(relation, "custom_relation_type_id", None),
            "custom_fields": [f.to_dict() if hasattr(f, "to_dict") else f for f in (getattr(relation, "custom_fields", []) or [])],
            "layer_ids": getattr(relation, "layer_ids", []),
        }
        self.technical_text.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    def set_advanced_mode(self, enabled: bool):
        self.technical_box.setVisible(bool(enabled))

    def save(self):
        if self._relation is None:
            return
        payload = {
            "relation_type": self.type_combo.currentData(),
            "direction": self.direction_combo.currentData(),
            "intensity": self.intensity_combo.currentData(),
            "description": self.description_edit.toPlainText().strip(),
            "temporality": self.temporality_edit.toPlainText().strip(),
            "causality": self.causality_edit.toPlainText().strip(),
            "source": self.source_edit.toPlainText().strip(),
            "validity_conditions": _split_lines(self.validity_edit.toPlainText()),
            "tags": _split_lines(self.tags_edit.toPlainText()),
            "canon_state": self.canon_combo.currentData(),
            "visibility_state": self.visibility_combo.currentData(),
        }
        result = self.relation_controller.update(self.relation_id, payload)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        self.ctx.selected_relation_id = self.relation_id
        self.ctx.log("info", "Relación guardada")
        self.refresh()
        if self.on_saved is not None:
            self.on_saved()

    def archive(self):
        result = self.relation_controller.archive(self.relation_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        self.ctx.log("info", "Relación archivada")
        if self.on_saved is not None:
            self.on_saved()
        if self.ctx.drawer is not None:
            self.ctx.drawer.close()
