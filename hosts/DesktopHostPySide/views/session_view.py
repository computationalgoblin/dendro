"""SessionView — session list with create (B27.1-T04)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                                QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox)
from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.session_controller import SessionController
from packages.domain.result import Error

class SessionView(QWidget):
    def __init__(self, ctx: AppContext, sc: SessionController):
        super().__init__(); self.ctx = ctx; self.sc = sc; self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_create = QPushButton("Crear sesión"); btn_create.clicked.connect(self._create); act.addWidget(btn_create)
        btn_refresh = QPushButton("Refrescar"); btn_refresh.clicked.connect(self.refresh); act.addWidget(btn_refresh)
        layout.addLayout(act)
        self.table = QTableWidget(); self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID","Name","State","Campaign"])
        self.table.itemSelectionChanged.connect(self._select); layout.addWidget(self.table)

    def refresh(self):
        sessions = self.sc.list_all()
        self.table.setRowCount(len(sessions))
        for i, s in enumerate(sessions):
            self.table.setItem(i, 0, QTableWidgetItem(s.id[:12]))
            self.table.setItem(i, 1, QTableWidgetItem(s.name))
            self.table.setItem(i, 2, QTableWidgetItem(s.state.value))
            self.table.setItem(i, 3, QTableWidgetItem(s.campaign_id or ""))
        self.table.resizeColumnsToContents()

    def _select(self):
        row = self.table.currentRow()
        if row >= 0: self.ctx.selected_session_id = self.table.item(row, 0).text()

    def _create(self):
        dlg = QDialog(self); form = QFormLayout(dlg)
        name = QLineEdit(); camp = QLineEdit()
        form.addRow("Nombre:", name); form.addRow("Campaign ID:", camp)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            r = self.sc.create({"name": name.text(), "campaign_id": camp.text()})
            self.ctx.log("info" if not isinstance(r, Error) else "error", f"Session created" if not isinstance(r, Error) else r.error)
            self.ctx.selected_session_id = r.value.id if not isinstance(r, Error) else None
            self.refresh()
