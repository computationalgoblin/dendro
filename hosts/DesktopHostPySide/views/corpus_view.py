"""CorpusView — entity table with filters, detail, create/edit (B27.3 bugbash)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
from hosts.DesktopHostPySide.widgets.drawer_forms import DrawerForm
from hosts.DesktopHostPySide.widgets.inspector_panel import InspectorPanel
from hosts.DesktopHostPySide.widgets.technical_visibility import set_columns_visible
from packages.domain.entity import (
    CanonState,
    CertaintyLevel,
    DevelopmentLevel,
    EntityType,
    NarrativeImportance,
    VisibilityState,
)
from packages.domain.result import Error


def _enum_values(enum_cls):
    return [item.value for item in enum_cls]


def _split_csv(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


class CorpusView(QWidget):
    def __init__(self, ctx: AppContext, ec: EntityController):
        super().__init__()
        self.ctx = ctx
        self.ec = ec
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        flt = QHBoxLayout()
        self.filter_text = QLineEdit()
        self.filter_text.setPlaceholderText("Filtrar...")
        self.filter_text.textChanged.connect(self.refresh)
        flt.addWidget(self.filter_text)
        self.filter_type = QComboBox()
        self.filter_type.addItems(["Todos", "personaje", "objeto", "nota"])
        self.filter_type.currentTextChanged.connect(self.refresh)
        flt.addWidget(self.filter_type)
        self.filter_canon = QComboBox()
        self.filter_canon.addItems(["Todos", "borrador", "canonico", "archivado"])
        self.filter_canon.currentTextChanged.connect(self.refresh)
        flt.addWidget(self.filter_canon)
        layout.addLayout(flt)

        act = QHBoxLayout()
        btn_create = QPushButton("Crear entidad")
        btn_create.clicked.connect(self._create)
        act.addWidget(btn_create)
        btn_refresh = QPushButton("Refrescar")
        btn_refresh.clicked.connect(self.refresh)
        act.addWidget(btn_refresh)
        layout.addLayout(act)

        body = QHBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Tipo", "Canon", "Visibilidad"])
        self.table.itemSelectionChanged.connect(self._show_detail)
        self.table.doubleClicked.connect(self._detail_dialog)
        body.addWidget(self.table, 3)

        self.inspector = InspectorPanel("Entity Inspector")
        body.addWidget(self.inspector, 1)
        layout.addLayout(body)

        self.detail = QLabel("Selecciona una entidad")
        layout.addWidget(self.detail)
        btn_edit = QPushButton("Editar seleccionada")
        btn_edit.clicked.connect(self._edit)
        layout.addWidget(btn_edit)
        btn_archive = QPushButton("Archivar/Restaurar")
        btn_archive.clicked.connect(self._archive)
        layout.addWidget(btn_archive)

    def refresh(self):
        entities = self.ec.list_all()
        ft = self.filter_text.text().lower().strip()
        ftype = self.filter_type.currentText()
        fcanon = self.filter_canon.currentText()
        if ftype != "Todos":
            entities = [e for e in entities if e.entity_type.value == ftype]
        if fcanon != "Todos":
            entities = [e for e in entities if e.canon_state.value == fcanon]
        if ft:
            entities = [e for e in entities if ft in e.name.lower() or ft in e.id.lower()]

        self.table.setRowCount(len(entities))
        for i, entity in enumerate(entities):
            id_item = QTableWidgetItem(entity.id[:12])
            id_item.setData(Qt.UserRole, entity.id)
            self.table.setItem(i, 0, id_item)
            self.table.setItem(i, 1, QTableWidgetItem(entity.name))
            self.table.setItem(i, 2, QTableWidgetItem(entity.entity_type.value))
            self.table.setItem(i, 3, QTableWidgetItem(entity.canon_state.value))
            self.table.setItem(i, 4, QTableWidgetItem(entity.visibility_state.value))
        self.table.resizeColumnsToContents()
        self.set_advanced_mode(self.ctx.advanced_mode)

    def set_advanced_mode(self, enabled: bool):
        set_columns_visible(self.table, [0], bool(enabled))
        self.inspector.set_advanced_mode(enabled)

    def _selected_entity_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _archive(self):
        entity_id = self._selected_entity_id() or self.ctx.selected_entity_id
        if not entity_id:
            self.ctx.log("error", "No hay entidad seleccionada")
            return
        entity_result = self.ec.get(entity_id)
        if isinstance(entity_result, Error):
            self.ctx.log("error", entity_result.error)
            return
        entity = entity_result.value
        if entity.canon_state.value == "archivado":
            result = self.ec.restore(entity_id)
            action = "restored"
        else:
            result = self.ec.archive(entity_id)
            action = "archived"
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
        else:
            self.ctx.log("info", f"Entity {action}: {entity_id}")
            self.refresh()

    def _detail_dialog(self, index):
        entity_id = self.table.item(index.row(), 0).data(Qt.UserRole)
        result = self.ec.get(entity_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        entity = result.value
        relations = self.ec.relations_for(entity.id)
        drawer = self.ctx.drawer
        if drawer is None:
            return
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(18, 14, 18, 14)
        lo.setSpacing(12)
        txt = QTextEdit()
        txt.setReadOnly(True)
        relation_lines = []
        for relation in relations:
            rel_type = relation.relation_type.value if hasattr(relation.relation_type, "value") else str(relation.relation_type)
            if self.ctx.advanced_mode:
                relation_lines.append(f"- {relation.id} :: {relation.source_id} --{rel_type}--> {relation.target_id}")
            else:
                relation_lines.append(f"- {rel_type}")
        lines = [
            f"Nombre: {entity.name}",
            f"Tipo: {entity.entity_type.value}",
            f"Canon: {entity.canon_state.value}",
            f"Descripción: {entity.brief_description or '—'}",
            f"Descripción extendida: {getattr(entity, 'extended_description', None) or '—'}",
            f"Dominio: {getattr(entity, 'domain', None) or '—'}",
            f"Capas: {', '.join(getattr(entity, 'layers', [])) or '—'}",
            f"Tags: {', '.join(getattr(entity, 'tags', [])) or '—'}",
            "",
            "Relaciones vinculadas:",
            *(relation_lines or ["- (ninguna)"]),
        ]
        if self.ctx.advanced_mode:
            lines.extend([
                "",
                "Datos técnicos — Modo avanzado",
                f"ID: {entity.id}",
                f"Domain IDs: {', '.join(getattr(entity, 'domain_ids', [])) or '—'}",
                f"Layer IDs: {', '.join(getattr(entity, 'layer_ids', [])) or '—'}",
                f"Metadata: {getattr(entity, 'custom_metadata', {})}",
            ])
        txt.setPlainText("\n".join(lines))
        lo.addWidget(txt)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(drawer.close)
        lo.addWidget(btn_close)
        drawer.set_content(w, title=f"Entity: {entity.name}")
        drawer.open()

    def _entity_fields(self, entity):
        return [
            {"name": "name", "label": "Nombre", "value": entity.name},
            {"name": "aliases", "label": "Aliases (csv)", "value": entity.aliases},
            {"name": "entity_type", "label": "Tipo", "kind": "combo", "value": entity.entity_type, "options": _enum_values(EntityType)},
            {"name": "brief_description", "label": "Descripción breve", "kind": "multiline", "value": entity.brief_description},
            {"name": "extended_description", "label": "Descripción extendida", "kind": "multiline", "value": entity.extended_description},
            {"name": "canon_state", "label": "Canon", "kind": "combo", "value": entity.canon_state, "options": _enum_values(CanonState)},
            {"name": "visibility_state", "label": "Visibilidad", "kind": "combo", "value": entity.visibility_state, "options": _enum_values(VisibilityState)},
            {"name": "certainty_level", "label": "Certeza", "kind": "combo", "value": entity.certainty_level, "options": _enum_values(CertaintyLevel)},
            {"name": "tags", "label": "Tags (csv)", "value": entity.tags},
            {"name": "domain", "label": "Domain", "value": entity.domain},
            {"name": "layers", "label": "Layers (csv)", "value": entity.layers},
            {"name": "origin", "label": "Origen", "value": entity.origin},
            {"name": "domain_ids", "label": "Domain IDs (csv)", "value": entity.domain_ids},
            {"name": "layer_ids", "label": "Layer IDs (csv)", "value": entity.layer_ids},
            {"name": "private_notes", "label": "Notas privadas", "kind": "multiline", "value": entity.private_notes},
            {"name": "exportable_notes", "label": "Notas exportables", "kind": "multiline", "value": entity.exportable_notes},
            {"name": "narrative_importance", "label": "Importancia", "kind": "combo", "value": entity.narrative_importance, "options": _enum_values(NarrativeImportance)},
            {"name": "development_level", "label": "Desarrollo", "kind": "combo", "value": entity.development_level, "options": _enum_values(DevelopmentLevel)},
            {"name": "custom_metadata", "label": "Metadata JSON", "kind": "json", "value": entity.custom_metadata},
            {"name": "custom_type_id", "label": "Custom type ID", "value": entity.custom_type_id or ""},
            {"name": "custom_fields", "label": "Custom fields JSON", "kind": "json", "value": [f.to_dict() if hasattr(f, "to_dict") else f for f in entity.custom_fields]},
        ]

    def _inspector_payload(self, values):
        payload = dict(values)
        for key in ("aliases", "tags", "layers", "domain_ids", "layer_ids"):
            if key in payload:
                payload[key] = _split_csv(payload.get(key))
        if "custom_metadata" in payload:
            payload["custom_metadata"] = _as_dict(payload.get("custom_metadata"))
        if "custom_fields" in payload:
            payload["custom_fields"] = _as_list(payload.get("custom_fields"))
        return payload

    def _save_inspector(self, entity_id, values):
        result = self.ec.update(entity_id, self._inspector_payload(values))
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            raise RuntimeError(result.error)
        self.ctx.log("info", f"Updated entity {entity_id}")
        self.ctx.selected_entity_id = entity_id
        self.refresh()
        self._select_entity_row(entity_id)

    def _select_entity_row(self, entity_id):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.UserRole) == entity_id:
                self.table.selectRow(row)
                return

    def _show_detail(self):
        entity_id = self._selected_entity_id()
        if not entity_id:
            return
        result = self.ec.get(entity_id)
        if isinstance(result, Error):
            self.detail.setText(f"Error: {result.error}")
            self.ctx.log("error", result.error)
            return
        entity = result.value
        rel_count = len(self.ec.relations_for(entity.id))
        self.detail.setText(
            f"{entity.entity_type.value}: {entity.name}\n"
            f"Desc: {entity.brief_description or '(sin desc)'}\n"
            f"Canon: {entity.canon_state.value} | Vis: {entity.visibility_state.value} | Relaciones: {rel_count}"
        )
        self.inspector.bind(
            title=f"Entity · {entity.name}",
            object_id=entity.id,
            fields=self._entity_fields(entity),
            on_save=lambda values, eid=entity.id: self._save_inspector(eid, values),
            on_revert=lambda eid=entity.id: self._rebind_entity(eid),
        )
        self.ctx.selected_entity_id = entity.id

    def _rebind_entity(self, entity_id):
        result = self.ec.get(entity_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        entity = result.value
        self.inspector.bind(
            title=f"Entity · {entity.name}",
            object_id=entity.id,
            fields=self._entity_fields(entity),
            on_save=lambda values, eid=entity.id: self._save_inspector(eid, values),
            on_revert=lambda eid=entity.id: self._rebind_entity(eid),
        )

    def _create(self):
        drawer = self.ctx.drawer
        if drawer is None:
            return

        class _CreateForm(DrawerForm):
            def __init__(self, ctx, ec, refresh_cb):
                super().__init__(ctx, title="Crear entidad")
                self._ec = ec
                self._refresh = refresh_cb
                self.name_edit = QLineEdit()
                self.type_cb = QComboBox()
                self.type_cb.addItems(["personaje", "objeto", "nota"])
                self.form_layout.addRow("Nombre:", self.name_edit)
                self.form_layout.addRow("Tipo:", self.type_cb)

            def _on_accept(self):
                result = self._ec.create({"name": self.name_edit.text(), "entity_type": self.type_cb.currentText()})
                if isinstance(result, Error):
                    self.ctx.log("error", result.error)
                else:
                    self.ctx.log("info", f"Created entity {result.value.id}")
                    self._refresh()
                self._close_drawer()

        form = _CreateForm(self.ctx, self.ec, self.refresh)
        drawer.set_content(form, title="Crear entidad")
        drawer.open()

    def _edit(self):
        entity_id = self._selected_entity_id() or self.ctx.selected_entity_id
        if not entity_id:
            self.ctx.log("error", "No hay entidad seleccionada")
            return
        result = self.ec.get(entity_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        entity = result.value
        drawer = self.ctx.drawer
        if drawer is None:
            return

        class _EditForm(DrawerForm):
            def __init__(self, ctx, ec, entity_obj, refresh_cb):
                super().__init__(ctx, title=f"Editar: {entity_obj.name}")
                self._ec = ec
                self._entity = entity_obj
                self._refresh = refresh_cb
                self.name_ed = QLineEdit(entity_obj.name)
                self.brief_ed = QLineEdit(entity_obj.brief_description or "")
                self.form_layout.addRow("Nombre:", self.name_ed)
                self.form_layout.addRow("Descripción:", self.brief_ed)

            def _on_accept(self):
                update_result = self._ec.update(
                    self._entity.id,
                    {"name": self.name_ed.text(), "brief_description": self.brief_ed.text()},
                )
                if isinstance(update_result, Error):
                    self.ctx.log("error", update_result.error)
                else:
                    self.ctx.log("info", f"Updated entity {self._entity.id}")
                    self._refresh()
                self._close_drawer()

        form = _EditForm(self.ctx, self.ec, entity, self.refresh)
        drawer.set_content(form, title=f"Editar: {entity.name}")
        drawer.open()
