"""RelationView — relation table with drawer-based create/edit/detail (B31-T02)."""
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
from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
from hosts.DesktopHostPySide.widgets.drawer_forms import DrawerForm
from hosts.DesktopHostPySide.widgets.technical_visibility import set_columns_visible
from packages.domain.result import Error


def _relation_type_value(relation) -> str:
    return relation.relation_type.value if hasattr(relation.relation_type, "value") else str(relation.relation_type)


def _relation_display_label(relation) -> str:
    meta = dict(getattr(relation, "custom_metadata", {}) or {})
    custom = str(meta.get("custom_relation_label") or "").strip()
    if custom:
        return custom
    return _relation_type_value(relation)


def _slug_label(label: str) -> str:
    value = "_".join((label or "").strip().lower().split())
    return value or "esta_relacionado_con"


class RelationCreateForm(DrawerForm):
    """Create relation form for RightDrawer."""

    def __init__(self, ctx, rc, refresh_cb, parent=None):
        self._rc = rc
        self._refresh_cb = refresh_cb
        super().__init__(ctx, title="Crear relación", parent=parent)

        entities = list(rc.ps.active_project.entities) if rc.ps.active_project else []
        self._src = QComboBox()
        self._tgt = QComboBox()
        for e in entities:
            self._src.addItem(e.name, e.id)
            self._tgt.addItem(e.name, e.id)
        self._type_cb = QComboBox()
        self._type_cb.setEditable(True)
        self._type_cb.lineEdit().setPlaceholderText("Ej: mentor de, protege, depende de…")
        self._type_cb.addItem("relacionado con", "esta_relacionado_con")
        project = getattr(rc.ps, "active_project", None)
        for custom in list(getattr(project, "custom_relation_types", []) or []) if project is not None else []:
            if getattr(custom, "is_active", True):
                self._type_cb.addItem(str(getattr(custom, "name", "")), f"custom:{getattr(custom, 'id', '')}")
        self.form_layout.addRow("Origen:", self._src)
        self.form_layout.addRow("Destino:", self._tgt)
        self.form_layout.addRow("Tipo:", self._type_cb)

    def _on_accept(self):
        type_text = self._type_cb.currentText().strip()
        type_data = str(self._type_cb.currentData() or "")
        payload_meta: dict[str, str] = {}
        payload: dict[str, object] = {"custom_metadata": payload_meta}
        relation_type = "esta_relacionado_con"
        if type_data.startswith("custom:"):
            payload["custom_relation_type_id"] = type_data.split(":", 1)[1]
            payload_meta["custom_relation_label"] = type_text
        elif type_data and type_data != "esta_relacionado_con":
            relation_type = type_data
        elif type_text and _slug_label(type_text) != "esta_relacionado_con":
            payload_meta["custom_relation_label"] = type_text
        if not payload_meta:
            payload.pop("custom_metadata")
        r = self._rc.create(
            self._src.currentData(), self._tgt.currentData(),
            relation_type,
            payload,
        )
        if isinstance(r, Error):
            self.ctx.log("error", r.error)
        else:
            self.ctx.log("info", "Relación creada")
            self._refresh_cb()
        self._close_drawer()


class RelationEditForm(DrawerForm):
    """Edit relation description in RightDrawer."""

    def __init__(self, ctx, rc, relation, refresh_cb, parent=None):
        self._rc = rc
        self._relation = relation
        self._refresh_cb = refresh_cb
        super().__init__(ctx, title="Editar relación", parent=parent)

        src_name = self._entity_name(relation.source_id)
        tgt_name = self._entity_name(relation.target_id)
        self.form_layout.addRow("Origen:", QLabel(src_name))
        self.form_layout.addRow("Destino:", QLabel(tgt_name))
        self._desc = QTextEdit()
        self._desc.setPlainText(getattr(relation, "description", "") or "")
        self._desc.setMaximumHeight(120)
        self.form_layout.addRow("Descripción:", self._desc)

    def _entity_name(self, entity_id):
        project = self._rc.ps.active_project
        if project is None:
            return entity_id
        for entity in getattr(project, "entities", []):
            if entity.id == entity_id:
                return entity.name
        return entity_id

    def _on_accept(self):
        r = self._rc.update(self._relation.id, {"description": self._desc.toPlainText()})
        if isinstance(r, Error):
            self.ctx.log("error", r.error)
        else:
            self.ctx.log("info", "Relación actualizada")
            self._refresh_cb()
        self._close_drawer()


class RelationView(QWidget):
    def __init__(self, ctx: AppContext, rc: RelationController):
        super().__init__()
        self.ctx = ctx
        self.rc = rc
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_create = QPushButton("Crear relación")
        btn_create.clicked.connect(self._create)
        act.addWidget(btn_create)
        btn_refresh = QPushButton("Refrescar")
        btn_refresh.clicked.connect(self.refresh)
        act.addWidget(btn_refresh)
        layout.addLayout(act)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Origen", "Tipo", "Destino", "ID", "Canon"])
        self.table.itemSelectionChanged.connect(self._show_detail)
        self.table.doubleClicked.connect(self._detail_drawer)
        layout.addWidget(self.table)

        self.detail = QLabel("Selecciona una relación")
        layout.addWidget(self.detail)
        btn_edit = QPushButton("Editar seleccionada")
        btn_edit.clicked.connect(self._edit)
        layout.addWidget(btn_edit)
        btn_archive = QPushButton("Archivar/Restaurar")
        btn_archive.clicked.connect(self._archive)
        layout.addWidget(btn_archive)

    def refresh(self):
        relations = self.rc.list_all()
        self.table.setRowCount(len(relations))
        for i, relation in enumerate(relations):
            id_item = QTableWidgetItem(relation.id[:12])
            id_item.setData(Qt.ItemDataRole.UserRole, relation.id)
            self.table.setItem(i, 0, QTableWidgetItem(self._entity_name(relation.source_id)))
            self.table.setItem(i, 1, QTableWidgetItem(_relation_display_label(relation)))
            self.table.setItem(i, 2, QTableWidgetItem(self._entity_name(relation.target_id)))
            self.table.setItem(i, 3, id_item)
            self.table.setItem(i, 4, QTableWidgetItem(
                relation.canon_state.value if hasattr(relation.canon_state, "value") else str(relation.canon_state)
            ))
        self.table.resizeColumnsToContents()
        self.set_advanced_mode(self.ctx.advanced_mode)

    def set_advanced_mode(self, enabled: bool):
        set_columns_visible(self.table, [3], bool(enabled))

    def _entity_name(self, entity_id):
        project = self.rc.ps.active_project
        if project is None:
            return entity_id
        for entity in getattr(project, "entities", []):
            if entity.id == entity_id:
                return entity.name
        return entity_id

    def _selected_relation_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 3)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _create(self):
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = RelationCreateForm(self.ctx, self.rc, self.refresh)
        drawer.set_content(form, title="Crear relación")
        drawer.open()

    def _detail_drawer(self, index):
        relation_id = self.table.item(index.row(), 3).data(Qt.ItemDataRole.UserRole)
        result = self.rc.get(relation_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        relation = result.value
        # Show detail in drawer as read-only view
        drawer = self.ctx.drawer
        if drawer is None:
            return
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(18, 14, 18, 14)
        lo.setSpacing(10)
        rel_type = _relation_display_label(relation)
        canon = relation.canon_state.value if hasattr(relation.canon_state, "value") else str(relation.canon_state)
        lines = [
            ("Origen", self._entity_name(relation.source_id)),
            ("Destino", self._entity_name(relation.target_id)),
            ("Tipo", rel_type),
            ("Canon", canon),
            ("Descripción", getattr(relation, "description", "—") or "—"),
        ]
        if self.ctx.advanced_mode:
            lines.extend([
                ("ID", relation.id),
                ("Visibilidad", str(getattr(relation, "visibility_state", "—"))),
                ("Metadata", str(getattr(relation, "custom_metadata", {}))),
            ])
        for label, value in lines:
            lbl = QLabel(f"<b>{label}:</b> {value}")
            lbl.setWordWrap(True)
            lo.addWidget(lbl)
        lo.addStretch()
        drawer.set_content(w, title="Detalle de relación")
        drawer.open()

    def _show_detail(self):
        relation_id = self._selected_relation_id()
        if not relation_id:
            return
        result = self.rc.get(relation_id)
        if isinstance(result, Error):
            self.detail.setText(f"Error: {result.error}")
            self.ctx.log("error", result.error)
            return
        relation = result.value
        self.ctx.selected_relation_id = relation.id
        rel_type = _relation_display_label(relation)
        self.detail.setText(
            f"{self._entity_name(relation.source_id)}\n"
            f"-- {rel_type} -->\n"
            f"{self._entity_name(relation.target_id)}"
        )

    def _edit(self):
        relation_id = self._selected_relation_id() or self.ctx.selected_relation_id
        if not relation_id:
            self.ctx.log("error", "No hay relación seleccionada")
            return
        result = self.rc.get(relation_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        drawer = self.ctx.drawer
        if drawer is None:
            return
        form = RelationEditForm(self.ctx, self.rc, result.value, self.refresh)
        drawer.set_content(form, title="Editar relación")
        drawer.open()

    def _archive(self):
        relation_id = self._selected_relation_id() or self.ctx.selected_relation_id
        if not relation_id:
            self.ctx.log("error", "No hay relación seleccionada")
            return
        result = self.rc.get(relation_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        relation = result.value
        if getattr(relation.canon_state, "value", str(relation.canon_state)) == "archivado":
            action_result = self.rc.restore(relation_id)
            action = "restaurada"
        else:
            action_result = self.rc.archive(relation_id)
            action = "archivada"
        if isinstance(action_result, Error):
            self.ctx.log("error", action_result.error)
        else:
            self.ctx.log("info", f"Relación {action}")
            self.refresh()
