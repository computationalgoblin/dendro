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
        return list(self.ps.active_project.candidates) if self.ps.active_project else []

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
