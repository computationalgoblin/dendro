"""IssuesHistoryView — open issues + recent history (B27.3 bugbash)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hosts.DesktopHostPySide.app_context import AppContext


class IssuesHistoryView(QWidget):
    def __init__(self, ctx: AppContext, controller, session_controller=None):
        super().__init__()
        self.ctx = ctx
        self.controller = controller
        self.session_controller = session_controller
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(5)
        self.issues_table.setHorizontalHeaderLabels(["ID", "Type", "Severity", "Description", "Affected"])
        tabs.addTab(self.issues_table, "Issues")
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["Timestamp", "Event", "Description"])
        tabs.addTab(self.history_table, "History")
        layout.addWidget(tabs)

        act = QHBoxLayout()
        for label, handler in [
            ("Validación global", self._run_global),
            ("Writing check", self._run_writing),
            ("Secret/Faction checks", self._run_specialized),
            ("Session check", self._run_session_check),
            ("Refrescar", self.refresh),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            act.addWidget(btn)
        layout.addLayout(act)

    def _project(self):
        return self.controller.ps.active_project if getattr(self.controller, "ps", None) else None

    def _run_global(self):
        result = self.controller.run_global_validation()
        if hasattr(result, "error"):
            self.ctx.log("error", f"Global validation failed: {result.error}")
        else:
            self.ctx.log("info", f"Global validation: {result.value}")
        self.refresh()

    def _append_external_issues(self, issues, origin):
        project = self._project()
        if project is None:
            return 0
        existing = {issue.id for issue in getattr(project, "issues", [])}
        new_count = 0
        for issue in issues:
            if issue.id not in existing:
                project.issues.append(issue)
                existing.add(issue.id)
                new_count += 1
        if new_count:
            project.touch()
        self.ctx.log("info", f"{origin}: {new_count} incidencias nuevas")
        return new_count

    def _run_writing(self):
        issues = self.controller.run_writing_validation()
        self._append_external_issues(issues, "writing")
        self.refresh()

    def _run_specialized(self):
        secret_issues = self.controller.run_secret_validation()
        faction_issues = self.controller.run_faction_validation()
        self._append_external_issues(secret_issues, "secret/clue")
        self._append_external_issues(faction_issues, "faction")
        self.refresh()

    def _run_session_check(self):
        sid = self.ctx.selected_session_id
        if not sid:
            self.ctx.log("error", "Selecciona una sesión antes de ejecutar session check")
            return
        result = self.controller.run_session_check(sid)
        if hasattr(result, "error"):
            self.ctx.log("error", f"Session check failed: {result.error}")
        else:
            self.ctx.log("info", f"Session check: {result.value}")
        issues = self.controller.session_issues(sid)
        self.ctx.log("info", f"Session issues linked: {len(issues)}")
        self.refresh()

    def refresh(self):
        project = self._project()
        if project is None:
            self.issues_table.setRowCount(0)
            self.history_table.setRowCount(0)
            return

        issues = getattr(project, "issues", [])
        self.issues_table.setRowCount(len(issues))
        for i, issue in enumerate(issues):
            self.issues_table.setItem(i, 0, QTableWidgetItem(issue.id[:12]))
            self.issues_table.setItem(i, 1, QTableWidgetItem(issue.type.value if hasattr(issue.type, "value") else str(issue.type)))
            self.issues_table.setItem(i, 2, QTableWidgetItem(issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity)))
            self.issues_table.setItem(i, 3, QTableWidgetItem(issue.description[:100]))
            self.issues_table.setItem(i, 4, QTableWidgetItem(str(len(getattr(issue, "affected_entity_ids", [])))))
        self.issues_table.resizeColumnsToContents()

        entries = getattr(project, "history_entries", None) or getattr(project, "history", [])
        self.history_table.setRowCount(min(len(entries), 50))
        for i, entry in enumerate(reversed(entries[-50:])):
            timestamp = getattr(entry, "timestamp", "")
            event_type = getattr(entry, "event_type", getattr(entry, "type", ""))
            description = getattr(entry, "description", str(entry))
            self.history_table.setItem(i, 0, QTableWidgetItem(str(timestamp)[:19]))
            self.history_table.setItem(i, 1, QTableWidgetItem(str(event_type)))
            self.history_table.setItem(i, 2, QTableWidgetItem(str(description)[:100]))
        self.history_table.resizeColumnsToContents()
