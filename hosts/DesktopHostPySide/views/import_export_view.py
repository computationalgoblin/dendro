"""ImportExportView — import txt/pdf + export gm/player/public (B27.1-T05)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
                                QTextEdit, QFileDialog, QComboBox, QLabel, QLineEdit)
from hosts.DesktopHostPySide.app_context import AppContext
from packages.application.export_service import ExportService

class ImportExportView(QWidget):
    def __init__(self, ctx: AppContext, controller):
        super().__init__(); self.ctx = ctx; self.controller = controller
        self.es = ExportService(project_service=controller.ps)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # Import tab
        imp = QWidget(); il = QVBoxLayout(imp)
        btn_file = QPushButton("Seleccionar archivo..."); btn_file.clicked.connect(self._import_file)
        il.addWidget(btn_file)
        btn_baskets = QPushButton("List baskets"); btn_baskets.clicked.connect(self._list_baskets)
        il.addWidget(btn_baskets)
        self.import_output = QTextEdit(); self.import_output.setReadOnly(True); il.addWidget(self.import_output)
        btn_accept = QPushButton("Accept selected"); btn_accept.clicked.connect(self._import_accept)
        il.addWidget(btn_accept)
        tabs.addTab(imp, "Import")

        # Export tab
        exp = QWidget(); el = QVBoxLayout(exp)
        aud = QHBoxLayout()
        aud.addWidget(QLabel("Audience:"))
        self.audience_cb = QComboBox(); self.audience_cb.addItems(["gm","player","public"]); aud.addWidget(self.audience_cb)
        el.addLayout(aud)
        btn_all = QPushButton("Export All"); btn_all.clicked.connect(self._export_all); el.addWidget(btn_all)
        btn_entity = QPushButton("Export Entity (local selector)"); btn_entity.clicked.connect(self._export_entity)
        el.addWidget(btn_entity)
        self.entity_sel = QLineEdit(); self.entity_sel.setPlaceholderText("Entity ID"); el.addWidget(self.entity_sel)
        btn_session = QPushButton("Export Session (local selector)"); btn_session.clicked.connect(self._export_session)
        el.addWidget(btn_session)
        self.session_sel = QLineEdit(); self.session_sel.setPlaceholderText("Session ID"); el.addWidget(self.session_sel)
        self.export_output = QTextEdit(); self.export_output.setReadOnly(True); el.addWidget(self.export_output)
        tabs.addTab(exp, "Export")

        layout.addWidget(tabs)

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import", "", "Text (*.txt *.md);;PDF (*.pdf);;All (*)")
        if path: self.import_output.setText(f"Selected: {path}\nTODO: ImportService integration")

    def _list_baskets(self):
        try:
            baskets = getattr(self.controller._proj, 'import_baskets', [])
            self.import_output.setText(f"{len(baskets)} basket(s)\n" + "\n".join(f"  {b.id[:12]}: {getattr(b,'source_id','?')}" for b in baskets))
        except Exception: self.import_output.setText("No baskets or import not configured")

    def _import_accept(self): self.import_output.setText("TODO: basket selector + accept")

    def _export_all(self):
        aud = self.audience_cb.currentText()
        try:
            r = self.es.export_all(aud)
            self.export_output.setText(str(r.value if hasattr(r, 'value') else r)[:2000])
        except Exception as e: self.export_output.setText(f"Error: {e}")

    def _export_entity(self):
        eid = self.entity_sel.text().strip()
        if eid:
            try:
                r = self.es.export_entity_profile(eid, self.audience_cb.currentText())
                self.export_output.setText(r.value if hasattr(r, 'value') else str(r))
            except Exception as e: self.export_output.setText(f"Error: {e}")

    def _export_session(self):
        sid = self.session_sel.text().strip()
        if sid:
            try:
                r = self.es.export_session_player_summary(sid)
                self.export_output.setText(r.value if hasattr(r, 'value') else str(r))
            except Exception as e: self.export_output.setText(f"Error: {e}")
