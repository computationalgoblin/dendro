"""IssuesHistoryView — open issues + recent history (B27.1-T03)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem, QPushButton)
from hosts.DesktopHostPySide.app_context import AppContext

class IssuesHistoryView(QWidget):
    def __init__(self, ctx: AppContext, controller):
        super().__init__(); self.ctx = ctx; self.controller = controller
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self.issues_table = QTableWidget(); self.issues_table.setColumnCount(4)
        self.issues_table.setHorizontalHeaderLabels(["Type","Severity","Description","Affected"])
        tabs.addTab(self.issues_table, "Issues")
        self.history_table = QTableWidget(); self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["Timestamp","Event","Description"])
        tabs.addTab(self.history_table, "History")
        layout.addWidget(tabs)
        act = QHBoxLayout()
        btn_validate = QPushButton("Run Validators"); btn_validate.clicked.connect(self._run_validators); act.addWidget(btn_validate)
        btn = QPushButton("Refrescar"); btn.clicked.connect(self.refresh); act.addWidget(btn)
        layout.addLayout(act)

    def _run_validators(self):
        from packages.application.issue_service import IssueService, run_validators
        p = self.controller._proj
        if p is None: return
        try:
            svc = IssueService(project_service=self.controller.ps)
            r = svc.run_validation()
            self.ctx.log("info", f"Validators complete: {r}")
            self.refresh()
        except Exception as e: self.ctx.log("error", f"Validators failed: {e}")

    def refresh(self):
        p = self.controller._proj
        if p is None: return
        issues = getattr(p, 'issues', [])
        self.issues_table.setRowCount(len(issues))
        for i, iss in enumerate(issues):
            self.issues_table.setItem(i, 0, QTableWidgetItem(iss.type.value if hasattr(iss.type, 'value') else str(iss.type)))
            self.issues_table.setItem(i, 1, QTableWidgetItem(iss.severity.value if hasattr(iss.severity, 'value') else str(iss.severity)))
            self.issues_table.setItem(i, 2, QTableWidgetItem(iss.description[:80]))
            self.issues_table.setItem(i, 3, QTableWidgetItem(str(len(iss.affected_entity_ids))))
        self.issues_table.resizeColumnsToContents()

        entries = getattr(p, 'history_entries', [])
        self.history_table.setRowCount(min(len(entries), 50))
        for i, e in enumerate(reversed(entries[-50:])):
            self.history_table.setItem(i, 0, QTableWidgetItem(e.timestamp[:19] if hasattr(e, 'timestamp') else ""))
            self.history_table.setItem(i, 1, QTableWidgetItem(e.event_type if hasattr(e, 'event_type') else ""))
            self.history_table.setItem(i, 2, QTableWidgetItem(e.description[:80] if hasattr(e, 'description') else ""))
        self.history_table.resizeColumnsToContents()
