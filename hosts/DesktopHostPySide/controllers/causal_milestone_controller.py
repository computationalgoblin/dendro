"""CausalMilestoneController — UI controller wrapping CausalMilestoneService (B41-T03)."""

from __future__ import annotations

from typing import Any

from packages.application.candidate_service import CandidateService
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.narrative_impact_service import NarrativeImpactService
from packages.domain.result import Error, Ok
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.controllers.mutation_hook import MutationNotifier


class CausalMilestoneController(MutationNotifier):
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
        # BETA2-MEM-04: motor de impacto (marca Falta regar al guardar canon).
        self.impact = NarrativeImpactService(self.ps)

    # ── CRUD ──

    def create_manual(self, data: dict):
        _apptrace(f"CTRL CausalMilestoneController.create_manual data_keys={list(data.keys())}"[:120])
        return self._notify_mutation(self.svc.create_hito_manual(data))

    def create_candidate(self, data: dict, *, source: str = "ia", confidence: float = 0.5):
        _apptrace(f"CTRL CausalMilestoneController.create_candidate source={source!r} conf={confidence}"[:120])
        return self._notify_mutation(
            self.svc.create_hito_candidate(data, source=source, confidence=confidence)
        )

    def approve(self, hito_or_candidate_id: str):
        _apptrace(f"CTRL CausalMilestoneController.approve id={hito_or_candidate_id!r}"[:120])
        return self._notify_mutation(self.svc.approve_hito(hito_or_candidate_id))

    def reject(self, hito_or_candidate_id: str):
        _apptrace(f"CTRL CausalMilestoneController.reject id={hito_or_candidate_id!r}"[:120])
        return self._notify_mutation(self.svc.reject_hito(hito_or_candidate_id))

    def update(self, hito_id: str, data: dict):
        _apptrace(f"CTRL CausalMilestoneController.update hito_id={hito_id!r}"[:120])
        return self._notify_mutation(
            self.svc.update_hito(hito_id, data, impact_service=self.impact)
        )

    def delete(self, hito_id: str):
        _apptrace(f"CTRL CausalMilestoneController.delete hito_id={hito_id!r}"[:120])
        return self._notify_mutation(self.svc.delete_hito(hito_id))

    # ── Subhitos: contención temporal de 1 nivel (BETA2-SUB-01) ──

    def set_parent(self, child_id: str, parent_id: str):
        _apptrace(
            f"CTRL CausalMilestoneController.set_parent child={child_id!r} parent={parent_id!r}"[:120]
        )
        return self._notify_mutation(self.svc.set_milestone_parent(child_id, parent_id))

    def clear_parent(self, child_id: str):
        _apptrace(f"CTRL CausalMilestoneController.clear_parent child={child_id!r}"[:120])
        return self._notify_mutation(self.svc.clear_milestone_parent(child_id))

    def create_subhito(self, parent_id: str, data: dict):
        _apptrace(f"CTRL CausalMilestoneController.create_subhito parent={parent_id!r}"[:120])
        return self._notify_mutation(self.svc.create_subhito(parent_id, data))

    def list_subhitos(self, parent_id: str):
        _apptrace(f"CTRL CausalMilestoneController.list_subhitos parent={parent_id!r}"[:120])
        result = self.svc.list_subhitos(parent_id)
        return result.value if isinstance(result, Ok) else []

    # ── Hilo causal setup→payoff (BETA-MULTIAGENT2-FIX-09) ──

    def link_causal(self, child_id: str, parent_id: str):
        """Declara que ``child_id`` recoge lo que plantó ``parent_id``."""
        _apptrace(
            f"CTRL CausalMilestoneController.link_causal child={child_id!r} "
            f"parent={parent_id!r}"[:120]
        )
        return self._notify_mutation(self.svc.link_causal(child_id, parent_id))

    def unlink_causal(self, child_id: str, parent_id: str):
        _apptrace(
            f"CTRL CausalMilestoneController.unlink_causal child={child_id!r} "
            f"parent={parent_id!r}"[:120]
        )
        return self._notify_mutation(self.svc.unlink_causal(child_id, parent_id))

    def causal_parents(self, hito_id: str):
        result = self.svc.list_causal_parents(hito_id)
        return result.value if isinstance(result, Ok) else []

    def causal_children(self, hito_id: str):
        result = self.svc.list_causal_children(hito_id)
        return result.value if isinstance(result, Ok) else []

    def reconcile_causal_links(self):
        """Normaliza el hilo causal del proyecto abierto (idempotente, sin IA)."""
        result = self.svc.reconcile_causal_links()
        return bool(result.value) if isinstance(result, Ok) else False

    # ── Queries ──

    def list_all(self):
        _apptrace(f"CTRL CausalMilestoneController.list_all"[:120])
        project = self.ps.active_project
        if not project:
            return []
        return list(getattr(project, "causal_milestones", []) or [])

    def list_for_leaf(self, leaf_id: str):
        _apptrace(f"CTRL CausalMilestoneController.list_for_leaf leaf_id={leaf_id!r}"[:120])
        result = self.svc.list_hitos_for_leaf(leaf_id)
        return result.value if isinstance(result, Ok) else []

    def list_for_branch(self, branch_id: str):
        _apptrace(f"CTRL CausalMilestoneController.list_for_branch branch_id={branch_id!r}"[:120])
        result = self.svc.list_hitos_for_branch(branch_id)
        return result.value if isinstance(result, Ok) else []

    def list_for_ring(self, ring_id: str):
        _apptrace(f"CTRL CausalMilestoneController.list_for_ring ring_id={ring_id!r}"[:120])
        result = self.svc.list_hitos_for_ring(ring_id)
        return result.value if isinstance(result, Ok) else []

    def list_for_relation(self, relation_id: str):
        _apptrace(f"CTRL CausalMilestoneController.list_for_relation relation_id={relation_id!r}"[:120])
        result = self.svc.list_hitos_for_relation(relation_id)
        return result.value if isinstance(result, Ok) else []

    def causal_chain(self, hito_id: str):
        _apptrace(f"CTRL CausalMilestoneController.causal_chain hito_id={hito_id!r}"[:120])
        result = self.svc.list_causal_chain(hito_id)
        return result.value if isinstance(result, Ok) else []

    def relations_without_hito(self):
        _apptrace(f"CTRL CausalMilestoneController.relations_without_hito"[:120])
        result = self.svc.find_relations_without_hito()
        return result.value if isinstance(result, Ok) else []

    def hitos_without_consequences(self):
        _apptrace(f"CTRL CausalMilestoneController.hitos_without_consequences"[:120])
        result = self.svc.find_hitos_without_consequences()
        return result.value if isinstance(result, Ok) else []
