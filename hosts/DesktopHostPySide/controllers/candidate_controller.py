"""CandidateController — wraps CandidateService (B27.1-T03)."""
from packages.application.candidate_service import CandidateService
from packages.application.project_service import ProjectService

class CandidateController:
    def __init__(self, project_service=None):
        self.ps = project_service or ProjectService(store=store)
        self.cs = CandidateService(project_service=self.ps)

    def list_all(self):
        return list(self.ps.active_project.candidates) if self.ps.active_project else []

    def accept(self, cid):
        return self.cs.accept_candidate(cid)

    def reject(self, cid):
        return self.cs.reject_candidate(cid)
