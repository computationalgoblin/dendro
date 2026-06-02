"""Node detail panel for B31-T04.

RightDrawer content opened from the graph when a node is selected. It reads and
updates entities through the UI controller; technical fields remain hidden unless
advanced mode is active.
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
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.widgets.design_system import Badge, enum_human, human_ref
from packages.domain.entity import CanonState, EntityType, VisibilityState
from packages.domain.result import Error


def _enum_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(getattr(value, "value", value))


def _split_csv(text: str) -> list[str]:
    return [chunk.strip() for chunk in (text or "").split(",") if chunk.strip()]


class NodeDetailPanel(QWidget):
    """Contextual entity editor shown inside the global RightDrawer."""

    def __init__(self, ctx: AppContext, entity_controller, entity_id: str, *, on_saved=None):
        super().__init__()
        self.ctx = ctx
        self.entity_controller = entity_controller
        self.entity_id = entity_id
        self.on_saved = on_saved
        self._entity = None
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        head = QHBoxLayout()
        self.title = QLabel("Entidad")
        self.title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ECEFF4;")
        self.title.setWordWrap(True)
        head.addWidget(self.title, 1)
        self.type_badge = Badge("Entidad", "info")
        head.addWidget(self.type_badge)
        layout.addLayout(head)

        self.summary = QLabel("")
        self.summary.setObjectName("mutedLabel")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        form_box = QGroupBox("Ficha")
        form = QFormLayout(form_box)
        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        for item in EntityType:
            self.type_combo.addItem(enum_human(item.value), item.value)
        self.brief_edit = QTextEdit()
        self.brief_edit.setMaximumHeight(78)
        self.extended_edit = QTextEdit()
        self.extended_edit.setMaximumHeight(120)
        self.private_notes_edit = QTextEdit()
        self.private_notes_edit.setMaximumHeight(82)
        self.exportable_notes_edit = QTextEdit()
        self.exportable_notes_edit.setMaximumHeight(82)
        self.canon_combo = QComboBox()
        for item in CanonState:
            self.canon_combo.addItem(enum_human(item.value), item.value)
        self.visibility_combo = QComboBox()
        for item in VisibilityState:
            self.visibility_combo.addItem(enum_human(item.value), item.value)
        form.addRow("Nombre:", self.name_edit)
        form.addRow("Tipo:", self.type_combo)
        form.addRow("Descripción breve:", self.brief_edit)
        form.addRow("Cuerpo:", self.extended_edit)
        form.addRow("Notas privadas:", self.private_notes_edit)
        form.addRow("Notas exportables:", self.exportable_notes_edit)
        form.addRow("Canon:", self.canon_combo)
        form.addRow("Visibilidad:", self.visibility_combo)
        layout.addWidget(form_box)

        self.context_box = QGroupBox("Contexto narrativo")
        context_layout = QVBoxLayout(self.context_box)
        self.relations_label = QLabel("Relaciones: —")
        self.relations_label.setWordWrap(True)
        self.appearances_label = QLabel("Apariciones: —")
        self.appearances_label.setWordWrap(True)
        self.campaigns_label = QLabel("Campañas: —")
        self.campaigns_label.setWordWrap(True)
        self.knowledge_label = QLabel("Secretos/Pistas: —")
        self.knowledge_label.setWordWrap(True)
        self.layers_label = QLabel("Capas/Dominios: —")
        self.layers_label.setWordWrap(True)
        for widget in [self.relations_label, self.appearances_label, self.campaigns_label, self.knowledge_label, self.layers_label]:
            widget.setObjectName("mutedLabel")
            context_layout.addWidget(widget)
        layout.addWidget(self.context_box)

        self.ai_box = QGroupBox("IA contextual")
        ai_layout = QVBoxLayout(self.ai_box)
        for label in ["Mejorar descripción", "Sugerir relaciones", "Detectar contradicciones"]:
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
        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self.save)
        self.refresh_btn = QPushButton("Refrescar")
        self.refresh_btn.clicked.connect(self.refresh)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.refresh_btn)
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

    def _set_combo_value(self, combo: QComboBox, value: str):
        idx = combo.findData(value)
        if idx < 0:
            idx = combo.findText(enum_human(value))
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def refresh(self):
        result = self.entity_controller.get(self.entity_id)
        if isinstance(result, Error):
            self.title.setText("Entidad no encontrada")
            self.summary.setText(result.error)
            self.save_btn.setEnabled(False)
            return
        entity = result.value
        self._entity = entity
        kind = _enum_value(getattr(entity, "entity_type", None), "entidad")
        self.title.setText(getattr(entity, "name", "Sin nombre") or "Sin nombre")
        self.type_badge.setText(enum_human(kind))
        self.summary.setText(
            f"{enum_human(kind)} · {enum_human(_enum_value(getattr(entity, 'canon_state', None), ''))} · "
            f"{enum_human(_enum_value(getattr(entity, 'visibility_state', None), ''))}"
        )
        self.name_edit.setText(getattr(entity, "name", ""))
        self._set_combo_value(self.type_combo, kind)
        self.brief_edit.setPlainText(getattr(entity, "brief_description", "") or "")
        self.extended_edit.setPlainText(getattr(entity, "extended_description", "") or "")
        self.private_notes_edit.setPlainText(getattr(entity, "private_notes", "") or "")
        self.exportable_notes_edit.setPlainText(getattr(entity, "exportable_notes", "") or "")
        self._set_combo_value(self.canon_combo, _enum_value(getattr(entity, "canon_state", None), ""))
        self._set_combo_value(self.visibility_combo, _enum_value(getattr(entity, "visibility_state", None), ""))
        self._refresh_context(entity)
        self._refresh_technical(entity)
        self.set_advanced_mode(self.ctx.advanced_mode)

    def _refresh_context(self, entity):
        project = self._project()
        if project is None:
            return
        entity_id = getattr(entity, "id", "")
        relation_lines = []
        for relation in getattr(project, "relations", []) or []:
            src = getattr(relation, "source_id", "")
            tgt = getattr(relation, "target_id", "")
            if entity_id not in {src, tgt}:
                continue
            other = self._entity_by_id(tgt if src == entity_id else src)
            other_ref = human_ref(getattr(other, "name", "?"), enum_human(_enum_value(getattr(other, "entity_type", None), ""))) if other else "Entidad vinculada"
            relation_lines.append(f"{enum_human(_enum_value(getattr(relation, 'relation_type', None), 'relación'))}: {other_ref}")
        self.relations_label.setText("Relaciones: " + ("; ".join(relation_lines[:8]) if relation_lines else "—"))

        appearances = []
        for session in getattr(project, "sessions", []) or []:
            refs = set(getattr(session, "planned_location_ids", []) or []) | set(getattr(session, "planned_npc_ids", []) or [])
            if entity_id in refs or getattr(session, "entity_id", None) == entity_id:
                appearances.append(getattr(session, "name", "Sesión"))
            for scene in getattr(session, "scenes", []) or []:
                refs_scene = set(getattr(scene, "npc_ids", []) or [])
                if entity_id in refs_scene or getattr(scene, "location_id", None) == entity_id:
                    appearances.append(f"{getattr(session, 'name', 'Sesión')} / {getattr(scene, 'name', 'Escena')}")
        self.appearances_label.setText("Apariciones: " + ("; ".join(appearances[:8]) if appearances else "—"))

        campaigns = []
        for campaign in getattr(project, "campaigns", []) or []:
            refs = {getattr(campaign, "world_entity_id", None)} | set(getattr(campaign, "active_location_entity_ids", []) or [])
            if entity_id in refs:
                campaigns.append(getattr(campaign, "name", "Campaña"))
        self.campaigns_label.setText("Campañas: " + ("; ".join(campaigns[:8]) if campaigns else "—"))

        knowledge = []
        for secret in getattr(project, "secrets", []) or []:
            if getattr(secret, "entity_id", None) == entity_id:
                knowledge.append(f"Secreto: {getattr(secret, 'content', '')[:40]}")
        for clue in getattr(project, "clues", []) or []:
            if getattr(clue, "entity_id", None) == entity_id:
                knowledge.append(f"Pista: {getattr(clue, 'content', '')[:40]}")
        self.knowledge_label.setText("Secretos/Pistas: " + ("; ".join(knowledge[:6]) if knowledge else "—"))

        domain = getattr(entity, "domain", "") or "—"
        layers = ", ".join(getattr(entity, "layers", []) or []) or "—"
        if self.ctx.advanced_mode:
            domain_ids = ", ".join(getattr(entity, "domain_ids", []) or []) or "—"
            layer_ids = ", ".join(getattr(entity, "layer_ids", []) or []) or "—"
            self.layers_label.setText(f"Capas/Dominios: dominio {domain}; capas {layers}; domain_ids {domain_ids}; layer_ids {layer_ids}")
        else:
            self.layers_label.setText(f"Capas/Dominios: dominio {domain}; capas {layers}")

    def _refresh_technical(self, entity):
        payload = {
            "id": getattr(entity, "id", ""),
            "aliases": getattr(entity, "aliases", []),
            "tags": getattr(entity, "tags", []),
            "domain_ids": getattr(entity, "domain_ids", []),
            "layer_ids": getattr(entity, "layer_ids", []),
            "custom_metadata": getattr(entity, "custom_metadata", {}),
            "custom_type_id": getattr(entity, "custom_type_id", None),
            "custom_fields": [f.to_dict() if hasattr(f, "to_dict") else f for f in (getattr(entity, "custom_fields", []) or [])],
        }
        self.technical_text.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

    def set_advanced_mode(self, enabled: bool):
        self.technical_box.setVisible(bool(enabled))
        self.layers_label.setText(self.layers_label.text())

    def save(self):
        if self._entity is None:
            return
        payload = {
            "name": self.name_edit.text().strip(),
            "entity_type": self.type_combo.currentData(),
            "brief_description": self.brief_edit.toPlainText().strip(),
            "extended_description": self.extended_edit.toPlainText().strip(),
            "private_notes": self.private_notes_edit.toPlainText().strip(),
            "exportable_notes": self.exportable_notes_edit.toPlainText().strip(),
            "canon_state": self.canon_combo.currentData(),
            "visibility_state": self.visibility_combo.currentData(),
        }
        result = self.entity_controller.update(self.entity_id, payload)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        self.ctx.log("info", "Entidad guardada")
        self.ctx.selected_entity_id = self.entity_id
        self.refresh()
        if self.on_saved is not None:
            self.on_saved()
