"""CorpusView — entity table with filters, detail, create/edit (B27.1-T02)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                                QLineEdit, QComboBox, QPushButton, QLabel, QDialog, QFormLayout, QDialogButtonBox)
from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.entity_controller import EntityController
from packages.domain.result import Error

class CorpusView(QWidget):
    def __init__(self, ctx: AppContext, ec: EntityController):
        super().__init__(); self.ctx = ctx; self.ec = ec; self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        # Filters
        flt = QHBoxLayout()
        self.filter_text = QLineEdit(); self.filter_text.setPlaceholderText("Filtrar..."); self.filter_text.textChanged.connect(self.refresh)
        flt.addWidget(self.filter_text)
        self.filter_type = QComboBox(); self.filter_type.addItems(["Todos","personaje","localizacion","faccion","objeto","evento","secreto","pista","sesion","nota"])
        self.filter_type.currentTextChanged.connect(self.refresh); flt.addWidget(self.filter_type)
        self.filter_canon = QComboBox(); self.filter_canon.addItems(["Todos","borrador","canonico"]); self.filter_canon.currentTextChanged.connect(self.refresh)
        flt.addWidget(self.filter_canon)
        layout.addLayout(flt)

        # Actions
        act = QHBoxLayout()
        btn_create = QPushButton("Crear entidad"); btn_create.clicked.connect(self._create); act.addWidget(btn_create)
        btn_refresh = QPushButton("Refrescar"); btn_refresh.clicked.connect(self.refresh); act.addWidget(btn_refresh)
        layout.addLayout(act)

        # Table
        self.table = QTableWidget(); self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID","Name","Type","Canon","Visibility"])
        self.table.itemSelectionChanged.connect(self._show_detail); layout.addWidget(self.table)

        # Detail
        self.detail = QLabel("Selecciona una entidad"); layout.addWidget(self.detail)
        btn_edit = QPushButton("Editar seleccionada"); btn_edit.clicked.connect(self._edit); layout.addWidget(btn_edit)
        btn_archive = QPushButton("Archivar/Restaurar"); btn_archive.clicked.connect(self._archive); layout.addWidget(btn_archive)

    def refresh(self):
        entities = self.ec.list_all()
        ft = self.filter_text.text().lower()
        ftype = self.filter_type.currentText()
        fcanon = self.filter_canon.currentText()
        if ftype != "Todos": entities = [e for e in entities if e.entity_type.value == ftype]
        if fcanon != "Todos": entities = [e for e in entities if e.canon_state.value == fcanon]
        if ft: entities = [e for e in entities if ft in e.name.lower()]
        self.table.setRowCount(len(entities))
        for i, e in enumerate(entities):
            self.table.setItem(i, 0, QTableWidgetItem(e.id[:12])); self.table.setItem(i, 1, QTableWidgetItem(e.name))
            self.table.setItem(i, 2, QTableWidgetItem(e.entity_type.value)); self.table.setItem(i, 3, QTableWidgetItem(e.canon_state.value))
            self.table.setItem(i, 4, QTableWidgetItem(e.visibility_state.value))
        self.table.resizeColumnsToContents()

    def _archive(self):
        if not self.ctx.selected_entity_id: return
        from PySide6.QtWidgets import QMessageBox
        r = self.ec.update(self.ctx.selected_entity_id, {"canon_state": "archivado"})
        if isinstance(r, Error): self.ctx.log("error", r.error)
        else: self.ctx.log("info", f"Archived {self.ctx.selected_entity_id[:8]}"); self.refresh()

    def _show_detail(self):
        row = self.table.currentRow()
        if row >= 0:
            eid = self.table.item(row, 0).text()
            r = self.ec.get(eid)
            if isinstance(r, Error): self.detail.setText(f"Error: {r.error}"); return
            e = r.value
            self.detail.setText(f"{e.entity_type.value}: {e.name}\nDesc: {e.brief_description or '(sin desc)'}\nCanon: {e.canon_state.value} | Vis: {e.visibility_state.value}")
            self.ctx.selected_entity_id = e.id

    def _create(self):
        dlg = QDialog(self); dlg.setWindowTitle("Crear entidad")
        form = QFormLayout(dlg); name = QLineEdit(); type_cb = QComboBox()
        type_cb.addItems(["personaje","localizacion","faccion","objeto","evento","nota"])
        form.addRow("Nombre:", name); form.addRow("Tipo:", type_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            r = self.ec.create({"name": name.text(), "entity_type": type_cb.currentText()})
            if isinstance(r, Error): self.ctx.log("error", r.error)
            else: self.ctx.log("info", f"Created {name.text()}"); self.refresh()

    def _edit(self):
        if not self.ctx.selected_entity_id: return
        r = self.ec.get(self.ctx.selected_entity_id)
        if isinstance(r, Error): return
        e = r.value
        dlg = QDialog(self); form = QFormLayout(dlg)
        name_ed = QLineEdit(e.name); brief_ed = QLineEdit(e.brief_description or "")
        form.addRow("Nombre:", name_ed); form.addRow("Descripción:", brief_ed)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            r = self.ec.update(e.id, {"name": name_ed.text(), "brief_description": brief_ed.text()})
            self.ctx.log("info" if not isinstance(r, Error) else "error", f"Updated {e.id[:8]}" if not isinstance(r, Error) else r.error)
            self.refresh()
