"""CandidateController — wraps CandidateService (B27.1-T03)."""
from __future__ import annotations

from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService


class CandidateController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("CandidateController requires project_service")
        self.ps = project_service
        self.cs = CandidateService(
            project_service=self.ps,
            entity_service=EntityService(self.ps),
            relation_service=RelationService(self.ps),
        )

    def list_all(self):
        """List candidates pending review (not accepted/rejected/postponed)."""
        project = self.ps.active_project
        if not project:
            return []
        from packages.domain.candidate_issue import CandidateState
        excluded = {
            CandidateState.ACEPTADO,
            CandidateState.RECHAZADO,
            CandidateState.EDITADO_ACEPTADO,
            CandidateState.PARCIALMENTE_ACEPTADO,
        }
        return [c for c in project.candidates if getattr(c, "state", None) not in excluded]

    def create(self, data):
        return self.cs.create_candidate(data)

    def accept(self, cid):
        return self.cs.accept_candidate(cid)

    def reject(self, cid):
        return self.cs.reject_candidate(cid)

    def postpone(self, cid):
        return self.cs.postpone_candidate(cid)

    def merge(self, cid, target_entity_id):
        return self.cs.merge_candidate(cid, target_entity_id)
