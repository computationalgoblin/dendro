"""IssueController — wraps IssueService and specialized validators for Desktop UI."""
from __future__ import annotations

from packages.application.issue_service import IssueService
from packages.application.faction_service import FactionService
from packages.application.secrets_service import SecretsService
from packages.application.writing_service import WritingService
from packages.application.session_service import SessionService
from hosts.DesktopHostPySide.app_trace import _apptrace


class IssueController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("IssueController requires project_service")
        self.ps = project_service
        self.issue_service = IssueService(project_service=self.ps)
        self.faction_service = FactionService(project_service=self.ps)
        self.secrets_service = SecretsService(project_service=self.ps)
        self.writing_service = WritingService(project_service=self.ps)
        self.session_service = SessionService(project_service=self.ps)

    def list_all(self):
        _apptrace(f"CTRL IssueController.list_all"[:120])
        result = self.issue_service.list_issues()
        return result.value if hasattr(result, "value") else []

    def run_global_validation(self):
        _apptrace(f"CTRL IssueController.run_global_validation"[:120])
        return self.issue_service.run_validation()

    def run_secret_validation(self):
        _apptrace(f"CTRL IssueController.run_secret_validation"[:120])
        return self.secrets_service.run_secret_validation()

    def run_faction_validation(self):
        _apptrace(f"CTRL IssueController.run_faction_validation"[:120])
        return self.faction_service.run_faction_validation()

    def run_writing_validation(self):
        _apptrace(f"CTRL IssueController.run_writing_validation"[:120])
        return self.writing_service.detect_writing_issues()

    def run_session_check(self, session_id):
        _apptrace(f"CTRL IssueController.run_session_check session_id={session_id!r}"[:120])
        return self.session_service.check_continuity(session_id)

    def session_issues(self, session_id):
        _apptrace(f"CTRL IssueController.session_issues session_id={session_id!r}"[:120])
        return self.session_service.get_relevant_issues(session_id)
