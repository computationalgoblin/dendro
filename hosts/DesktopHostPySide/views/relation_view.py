"""RelationView — relation table with create/edit/archive/detail (B27.3 bugbash)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
from packages.domain.result import Error


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
        self.table.setHorizontalHeaderLabels(["Source", "Type", "Target", "ID", "Canon"])
        self.table.itemSelectionChanged.connect(self._show_detail)
        self.table.doubleClicked.connect(self._detail_dialog)
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
            id_item.setData(Qt.UserRole, relation.id)
            self.table.setItem(i, 0, QTableWidgetItem(self._entity_name(relation.source_id)))
            self.table.setItem(i, 1, QTableWidgetItem(relation.relation_type.value if hasattr(relation.relation_type, "value") else str(relation.relation_type)))
            self.table.setItem(i, 2, QTableWidgetItem(self._entity_name(relation.target_id)))
            self.table.setItem(i, 3, id_item)
            self.table.setItem(i, 4, QTableWidgetItem(relation.canon_state.value if hasattr(relation.canon_state, "value") else str(relation.canon_state)))
        self.table.resizeColumnsToContents()

    def _entity_name(self, entity_id):
        project = self.rc.ps.active_project
        if project is None:
            return entity_id
        for entity in getattr(project, "entities", []):
            if entity.id == entity_id:
                return f"{entity.name} ({entity.id[:8]})"
        return entity_id

    def _selected_relation_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 3)
        return item.data(Qt.UserRole) if item is not None else None

    def _create(self):
        dlg = QDialog(self)
        form = QFormLayout(dlg)
        src = QComboBox()
        tgt = QComboBox()
        type_cb = QComboBox()
        entities = list(self.rc.ps.active_project.entities) if self.rc.ps.active_project else []
        for entity in entities:
            src.addItem(f"{entity.name} ({entity.id[:8]})", entity.id)
            tgt.addItem(f"{entity.name} ({entity.id[:8]})", entity.id)
        type_cb.addItems(["es_aliado_de", "es_enemigo_de", "ubicado_en", "pertenece_a", "contiene", "causo"])
        form.addRow("Source:", src)
        form.addRow("Target:", tgt)
        form.addRow("Type:", type_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            result = self.rc.create(src.currentData(), tgt.currentData(), type_cb.currentText())
            if isinstance(result, Error):
                self.ctx.log("error", result.error)
            else:
                self.ctx.log("info", f"Relation created: {result.value.id}")
                self.refresh()

    def _detail_dialog(self, index):
        relation_id = self.table.item(index.row(), 3).data(Qt.UserRole)
        result = self.rc.get(relation_id)
        if isinstance(result, Error):
            self.ctx.log("error", result.error)
            return
        relation = result.value
        dlg = QDialog(self)
        dlg.setWindowTitle("Relation Detail")
        dlg.setMinimumSize(600, 350)
        lo = QVBoxLayout(dlg)
        txt = QTextEdit()
        txt.setReadOnly(True)
        lines = [
            f"ID: {relation.id}",
            f"Source: {self._entity_name(relation.source_id)}",
            f"Type: {relation.relation_type.value if hasattr(relation.relation_type, 'value') else str(relation.relation_type)}",
            f"Target: {self._entity_name(relation.target_id)}",
            f"Canon: {relation.canon_state.value if hasattr(relation.canon_state, 'value') else str(relation.canon_state)}",
            f"Visibility: {getattr(getattr(relation, 'visibility_state', None), 'value', getattr(relation, 'visibility_state', '—'))}",
            f"Description: {getattr(relation, 'description', '—')}",
            f"Metadata: {getattr(relation, 'custom_metadata', {})}",
        ]
        txt.setPlainText("\n".join(lines))
        lo.addWidget(txt)
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dlg.accept)
        lo.addWidget(btns)
        dlg.exec()

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
        self.detail.setText(
            f"{self._entity_name(relation.source_id)}\n"
            f"-- {relation.relation_type.value if hasattr(relation.relation_type, 'value') else str(relation.relation_type)} -->\n"
            f"{self._entity_name(relation.target_id)}\n"
            f"ID: {relation.id}"
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
        relation = result.value
        dlg = QDialog(self)
        form = QFormLayout(dlg)
        desc = QTextEdit()
        desc.setPlainText(getattr(relation, "description", "") or "")
        form.addRow("Descripción:", desc)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            update_result = self.rc.update(relation.id, {"description": desc.toPlainText()})
            if isinstance(update_result, Error):
                self.ctx.log("error", update_result.error)
            else:
                self.ctx.log("info", f"Updated relation {relation.id}")
                self.refresh()

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
            action = "restored"
        else:
            action_result = self.rc.archive(relation_id)
            action = "archived"
        if isinstance(action_result, Error):
            self.ctx.log("error", action_result.error)
        else:
            self.ctx.log("info", f"Relation {action}: {relation_id}")
            self.refresh()
