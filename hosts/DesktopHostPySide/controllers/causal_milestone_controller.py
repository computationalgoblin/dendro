"""CausalMilestoneController — UI controller wrapping CausalMilestoneService (B41-T03)."""

from __future__ import annotations

from typing import Any

from packages.application.candidate_service import CandidateService
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.domain.result import Error, Ok


class CausalMilestoneController:
    """Thin UI adapter: delegates all logic to CausalMilestoneService.

    Never touches persistence or domain collections directly.
    """

    def __init__(self, project_service: Any):
        if project_service is None:
            raise ValueError("CausalMilestoneController requires project_service")
        self.ps = project_service
        self.cs = CandidateService(project_service=self.ps)
        self.svc = CausalMilestoneService(
            project_service=self.ps,
            candidate_service=self.cs,
        )

    # ── CRUD ──

    def create_manual(self, data: dict):
        return self.svc.create_hito_manual(data)

    def create_candidate(self, data: dict, *, source: str = "ia", confidence: float = 0.5):
        return self.svc.create_hito_candidate(data, source=source, confidence=confidence)

    def approve(self, hito_or_candidate_id: str):
        return self.svc.approve_hito(hito_or_candidate_id)

    def reject(self, hito_or_candidate_id: str):
        return self.svc.reject_hito(hito_or_candidate_id)

    def update(self, hito_id: str, data: dict):
        return self.svc.update_hito(hito_id, data)

    # ── Queries ──

    def list_all(self):
        project = self.ps.active_project
        if not project:
            return []
        return list(getattr(project, "causal_milestones", []) or [])

    def list_for_leaf(self, leaf_id: str):
        result = self.svc.list_hitos_for_leaf(leaf_id)
        return result.value if isinstance(result, Ok) else []

    def list_for_branch(self, branch_id: str):
        result = self.svc.list_hitos_for_branch(branch_id)
        return result.value if isinstance(result, Ok) else []

    def list_for_ring(self, ring_id: str):
        result = self.svc.list_hitos_for_ring(ring_id)
        return result.value if isinstance(result, Ok) else []

    def list_for_relation(self, relation_id: str):
        result = self.svc.list_hitos_for_relation(relation_id)
        return result.value if isinstance(result, Ok) else []

    def causal_chain(self, hito_id: str):
        result = self.svc.list_causal_chain(hito_id)
        return result.value if isinstance(result, Ok) else []

    def relations_without_hito(self):
        result = self.svc.find_relations_without_hito()
        return result.value if isinstance(result, Ok) else []

    def hitos_without_consequences(self):
        result = self.svc.find_hitos_without_consequences()
        return result.value if isinstance(result, Ok) else []
