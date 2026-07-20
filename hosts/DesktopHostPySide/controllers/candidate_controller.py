"""CandidateController — wraps CandidateService (B27.1-T03)."""
from __future__ import annotations

from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.relation_service import RelationService
from hosts.DesktopHostPySide.app_trace import _apptrace


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
        # BETA2-MEM-04: motor de impacto (marca Falta regar al florecer canon).
        self.impact = NarrativeImpactService(self.ps)

    def list_all(self):
        """List candidates pending review (not accepted/rejected/postponed)."""
        _apptrace(f"CTRL CandidateController.list_all"[:120])
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
        _apptrace(f"CTRL CandidateController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self.cs.create_candidate(data)

    def accept(self, cid):
        _apptrace(f"CTRL CandidateController.accept cid={cid!r}"[:120])
        return self.cs.accept_candidate(cid, impact_service=self.impact)

    def reject(self, cid):
        _apptrace(f"CTRL CandidateController.reject cid={cid!r}"[:120])
        return self.cs.reject_candidate(cid)

    def postpone(self, cid):
        _apptrace(f"CTRL CandidateController.postpone cid={cid!r}"[:120])
        return self.cs.postpone_candidate(cid)

    def merge(self, cid, target_entity_id):
        _apptrace(f"CTRL CandidateController.merge cid={cid!r} target={target_entity_id!r}"[:120])
        return self.cs.merge_candidate(cid, target_entity_id)
