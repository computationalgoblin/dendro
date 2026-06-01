"""ImportExportView with real ImportService (B27.2-T01)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
                                QTextEdit, QFileDialog, QComboBox, QLabel, QLineEdit, QTableWidget, QTableWidgetItem)
from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.import_controller import ImportController
from packages.application.export_service import ExportService
from packages.domain.result import Error

class ImportExportView(QWidget):
    def __init__(self, ctx: AppContext, controller):
        super().__init__(); self.ctx = ctx; self.controller = controller
        self.ic = ImportController(project_service=controller.ps)
        self.es = ExportService(project_service=controller.ps)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self); tabs = QTabWidget()
        # Import tab
        imp = QWidget(); il = QVBoxLayout(imp)
        btn_file = QPushButton("Importar documento (txt/pdf)"); btn_file.clicked.connect(self._import_file); il.addWidget(btn_file)
        self.basket_combo = QComboBox(); il.addWidget(QLabel("Baskets:")); il.addWidget(self.basket_combo)
        btn_show = QPushButton("Ver basket"); btn_show.clicked.connect(self._show_basket); il.addWidget(btn_show)
        self.import_table = QTableWidget(); self.import_table.setColumnCount(4)
        self.import_table.setHorizontalHeaderLabels(["ID","Type","Name","State"]); il.addWidget(self.import_table)
        btns = QHBoxLayout()
        btn_accept = QPushButton("Accept"); btn_accept.clicked.connect(self._accept); btns.addWidget(btn_accept)
        btn_reject = QPushButton("Reject"); btn_reject.clicked.connect(self._reject); btns.addWidget(btn_reject)
        il.addLayout(btns)
        self.import_output = QTextEdit(); self.import_output.setReadOnly(True); self.import_output.setMaximumHeight(60)
        il.addWidget(self.import_output)
        btn_refresh = QPushButton("Refrescar baskets"); btn_refresh.clicked.connect(self._refresh_baskets); il.addWidget(btn_refresh)
        tabs.addTab(imp, "Import")

        # Export tab
        exp = QWidget(); el = QVBoxLayout(exp)
        aud = QHBoxLayout(); aud.addWidget(QLabel("Audience:"))
        self.audience_cb = QComboBox(); self.audience_cb.addItems(["gm","player","public"]); aud.addWidget(self.audience_cb)
        el.addLayout(aud)
        btn_all = QPushButton("Export All"); btn_all.clicked.connect(self._export_all); el.addWidget(btn_all)
        self.entity_sel = QLineEdit(); self.entity_sel.setPlaceholderText("Entity ID"); el.addWidget(self.entity_sel)
        btn_entity = QPushButton("Export Entity"); btn_entity.clicked.connect(self._export_entity); el.addWidget(btn_entity)
        self.session_sel = QLineEdit(); self.session_sel.setPlaceholderText("Session ID"); el.addWidget(self.session_sel)
        btn_session = QPushButton("Export Session"); btn_session.clicked.connect(self._export_session); el.addWidget(btn_session)
        self.export_output = QTextEdit(); self.export_output.setReadOnly(True); el.addWidget(self.export_output)
        tabs.addTab(exp, "Export")
        layout.addWidget(tabs)

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import", "", "Text (*.txt *.md);;PDF (*.pdf);;All (*)")
        if path:
            r = self.ic.import_document(path)
            if isinstance(r, Error): self.ctx.log("error", f"Import failed: {r.error}"); return
            self._refresh_baskets()
            self.ctx.log("info", f"Imported {path}")
            # Refresh candidate inbox
            try:
                for v in [self.parentWidget().parentWidget().findChildren(QWidget)]:
                    if hasattr(v, 'refresh') and 'Candidate' in type(v).__name__: v.refresh()
            except: pass

    def _refresh_baskets(self):
        r = self.ic.list_baskets()
        baskets = r.value if hasattr(r, 'value') else (r if isinstance(r, list) else [])
        self.basket_combo.clear()
        for b in baskets: self.basket_combo.addItem(f"Basket {b.id[:12]} ({len(b.import_candidates)} cands)", b.id)

    def _show_basket(self):
        bid = self.basket_combo.currentData()
        if not bid: return
        r = self.ic.get_basket(bid)
        b = r.value if hasattr(r, 'value') else r
        if isinstance(b, Error): self.ctx.log("error", b.error); return
        cands = getattr(b, 'import_candidates', [])
        self.import_table.setRowCount(len(cands))
        for i, c in enumerate(cands):
            self.import_table.setItem(i, 0, QTableWidgetItem(c.id[:12]))
            self.import_table.setItem(i, 1, QTableWidgetItem(c.candidate_type))
            name = c.proposed_data.get("entity_name", "?") if isinstance(c.proposed_data, dict) else "?"
            self.import_table.setItem(i, 2, QTableWidgetItem(name))
            self.import_table.setItem(i, 3, QTableWidgetItem(c.review_state.value if hasattr(c.review_state, 'value') else str(c.review_state)))
        self.import_table.resizeColumnsToContents()

    def _accept(self):
        bid = self.basket_combo.currentData()
        row = self.import_table.currentRow()
        if bid and row >= 0:
            cid = self.import_table.item(row, 0).text()
            r = self.ic.accept(bid, cid)
            if isinstance(r, Error): self.ctx.log("error", str(r.error))
            else: self.ctx.log("info", f"Accepted {cid[:8]} → Candidate B14"); self._show_basket()

    def _reject(self):
        bid = self.basket_combo.currentData()
        row = self.import_table.currentRow()
        if bid and row >= 0:
            cid = self.import_table.item(row, 0).text()
            r = self.ic.reject(bid, cid)
            if isinstance(r, Error): self.ctx.log("error", str(r.error))
            else: self.ctx.log("info", f"Rejected {cid[:8]}"); self._show_basket()

    def _export_all(self):
        r = self.es.export_all(self.audience_cb.currentText())
        self.export_output.setText(str(r.value if hasattr(r, 'value') else r)[:2000])

    def _export_entity(self):
        eid = self.entity_sel.text().strip()
        if eid:
            r = self.es.export_entity_profile(eid, self.audience_cb.currentText())
            self.export_output.setText(r.value if hasattr(r, 'value') else str(r))

    def _export_session(self):
        sid = self.session_sel.text().strip()
        if sid:
            r = self.es.export_session_player_summary(sid)
            self.export_output.setText(r.value if hasattr(r, 'value') else str(r))
