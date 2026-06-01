"""RelationView — relation table with create (B27.1-T02)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                                QPushButton, QDialog, QFormLayout, QComboBox, QDialogButtonBox, QLabel)
from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.relation_controller import RelationController
from packages.domain.result import Error

class RelationView(QWidget):
    def __init__(self, ctx: AppContext, rc: RelationController):
        super().__init__(); self.ctx = ctx; self.rc = rc; self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_create = QPushButton("Crear relación"); btn_create.clicked.connect(self._create); act.addWidget(btn_create)
        btn_refresh = QPushButton("Refrescar"); btn_refresh.clicked.connect(self.refresh); act.addWidget(btn_refresh)
        layout.addLayout(act)
        self.table = QTableWidget(); self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Source","Type","Target","ID","Canon"]); layout.addWidget(self.table)
        self.detail = QLabel(""); layout.addWidget(self.detail)

    def refresh(self):
        rels = self.rc.list_all()
        self.table.setRowCount(len(rels))
        for i, r in enumerate(rels):
            src_name = self._entity_name(r.source_id) if hasattr(self.rc.ps.active_project, 'entities') else r.source_id[:8]
            tgt_name = self._entity_name(r.target_id) if hasattr(self.rc.ps.active_project, 'entities') else r.target_id[:8]
            self.table.setItem(i, 0, QTableWidgetItem(src_name))
            self.table.setItem(i, 1, QTableWidgetItem(r.relation_type.value if hasattr(r.relation_type, 'value') else str(r.relation_type)))
            self.table.setItem(i, 2, QTableWidgetItem(tgt_name))
            self.table.setItem(i, 3, QTableWidgetItem(r.id[:12]))
            self.table.setItem(i, 4, QTableWidgetItem(r.canon_state.value if hasattr(r.canon_state, 'value') else str(r.canon_state)))
        self.table.resizeColumnsToContents()

    def _entity_name(self, eid):
        for e in self.rc.ps.active_project.entities: 
            if e.id == eid: return e.name
        return eid[:8]

    def _create(self):
        dlg = QDialog(self); form = QFormLayout(dlg)
        src = QComboBox(); tgt = QComboBox(); type_cb = QComboBox()
        entities = list(self.rc.ps.active_project.entities) if self.rc.ps.active_project else []
        for e in entities: src.addItem(f"{e.name} ({e.id[:8]})", e.id); tgt.addItem(f"{e.name} ({e.id[:8]})", e.id)
        type_cb.addItems(["es_aliado_de","es_enemigo_de","ubicado_en","pertenece_a","contiene","causo"])
        form.addRow("Source:", src); form.addRow("Target:", tgt); form.addRow("Type:", type_cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            r = self.rc.create(src.currentData(), tgt.currentData(), type_cb.currentText())
            self.ctx.log("info" if not isinstance(r, Error) else "error", f"Relation created" if not isinstance(r, Error) else r.error)
            self.refresh()

    def _detail_dialog(self, index):
        row = index.row()
        r_id = self.table.item(row, 3).text()
        rels = self.rc.list_all()
        rel = None
        for r in rels:
            if r.id.startswith(r_id): rel = r; break
        if rel is None: return
        dlg = QDialog(self); dlg.setWindowTitle("Relation Detail"); dlg.setMinimumSize(500, 300)
        lo = QVBoxLayout(dlg)
        txt = QTextEdit(); txt.setReadOnly(True)
        lines = [
            f"ID: {rel.id}",
            f"Source: {self._entity_name(rel.source_id)} ({rel.source_id[:16]})",
            f"Type: {rel.relation_type.value if hasattr(rel.relation_type, 'value') else str(rel.relation_type)}",
            f"Target: {self._entity_name(rel.target_id)} ({rel.target_id[:16]})",
            f"Canon: {rel.canon_state.value if hasattr(rel.canon_state, 'value') else str(rel.canon_state)}",
            f"Visibility: {getattr(rel, 'visibility_state', '—')}",
            f"Desc: {getattr(rel, 'description', '—')}",
            f"Metadata: {getattr(rel, 'metadata', {})}",
        ]
        txt.setPlainText('\n'.join(lines))
        lo.addWidget(txt)
        btns = QDialogButtonBox(QDialogButtonBox.Ok); btns.accepted.connect(dlg.accept); lo.addWidget(btns)
        dlg.exec()
