"""CandidateView — inbox with accept/reject (B27.1-T03)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
                                QPushButton, QLabel, QTextEdit)
from hosts.DesktopHostPySide.app_context import AppContext
from hosts.DesktopHostPySide.controllers.candidate_controller import CandidateController
from packages.domain.result import Error

class CandidateView(QWidget):
    def __init__(self, ctx: AppContext, cc: CandidateController):
        super().__init__(); self.ctx = ctx; self.cc = cc; self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        act = QHBoxLayout()
        btn_refresh = QPushButton("Refrescar"); btn_refresh.clicked.connect(self.refresh); act.addWidget(btn_refresh)
        layout.addLayout(act)
        self.table = QTableWidget(); self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID","Title","Type","State","Source"])
        self.table.itemSelectionChanged.connect(self._show_detail); layout.addWidget(self.table)
        self.detail = QTextEdit(); self.detail.setReadOnly(True); self.detail.setMaximumHeight(120); layout.addWidget(self.detail)
        btns = QHBoxLayout()
        btn_accept = QPushButton("Aceptar"); btn_accept.clicked.connect(self._accept); btns.addWidget(btn_accept)
        btn_reject = QPushButton("Rechazar"); btn_reject.clicked.connect(self._reject); btns.addWidget(btn_reject)
        layout.addLayout(btns)

    def refresh(self):
        cands = self.cc.list_all()
        self.table.setRowCount(len(cands))
        for i, c in enumerate(cands):
            self.table.setItem(i, 0, QTableWidgetItem(c.id[:12]))
            self.table.setItem(i, 1, QTableWidgetItem(c.title))
            self.table.setItem(i, 2, QTableWidgetItem(c.candidate_type.value))
            self.table.setItem(i, 3, QTableWidgetItem(c.state.value))
            self.table.setItem(i, 4, QTableWidgetItem(c.source or ""))
        self.table.resizeColumnsToContents()

    def _show_detail(self):
        row = self.table.currentRow()
        if row >= 0:
            cid = self.table.item(row, 0).text()
            for c in self.cc.list_all():
                if c.id.startswith(cid):
                    data = str(c.proposed_data) if c.proposed_data else "(sin datos)"
                    self.detail.setText(f"Title: {c.title}\nType: {c.candidate_type.value}\nState: {c.state.value}\nSource: {c.source or '?'}\nSource ID: {c.source_id or '?'}\nConfidence: {c.confidence}\nMetadata: {c.metadata}\n\nData: {data}")
                    self.ctx.selected_candidate_id = c.id; break

    def _accept(self):
        if self.ctx.selected_candidate_id:
            r = self.cc.accept(self.ctx.selected_candidate_id)
            self.ctx.log("info" if not isinstance(r, Error) else "error", f"Accepted" if not isinstance(r, Error) else r.error)
            self.refresh()

    def _reject(self):
        if self.ctx.selected_candidate_id:
            r = self.cc.reject(self.ctx.selected_candidate_id)
            self.ctx.log("info", f"Rejected"); self.refresh()
