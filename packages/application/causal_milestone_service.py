"""Application service for causal milestones — B41-T02."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.application.candidate_service import CandidateService
from packages.domain.candidate_issue import CandidateState
from packages.domain.causal_milestone import CausalMilestone, CausalMilestoneStatus
from packages.domain.relation import NarrativeRelation, RelationType
from packages.domain.result import Error, Ok, Result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CausalMilestoneService:
    """Use-case service for Hitos.

    Mutating methods update the active project in memory only. Persistence stays
    explicit through ProjectService.save(), matching the application-layer policy.
    """

    project_service: Any
    candidate_service: CandidateService | None = None
    history_service: Any = None

    def _proj(self):
        project = getattr(self.project_service, "active_project", None)
        if project is None:
            return Error("No active project")
        return Ok(project)

    def _get_hito(self, hito_id: str) -> Result[CausalMilestone, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for hito in proj.value.causal_milestones:
            if hito.id == hito_id:
                return Ok(hito)
        return Error(f"Hito '{hito_id[:8]}' not found")

    def _record(self, event_type: str, description: str, hito: CausalMilestone) -> None:
        if not self.history_service:
            return
        payload = {
            "event_type": event_type,
            "description": description,
            "metadata": {"hito_id": hito.id, "hito_title": hito.title},
        }
        try:
            if hasattr(self.history_service, "add_entry"):
                self.history_service.add_entry(payload)
            elif hasattr(self.history_service, "record"):
                self.history_service.record(payload)
        except Exception:
            pass

    def create_hito_candidate(
        self,
        data: dict[str, Any],
        source: str = "ia",
        confidence: float = 0.5,
    ):
        if self.candidate_service is None:
            return Error("CandidateService not available")
        hito = CausalMilestone.from_dict(data)
        hito.status = CausalMilestoneStatus.CANDIDATE
        return self.candidate_service.create_causal_milestone_candidate(
            hito,
            source=source,
            confidence=confidence,
            justification=hito.rationale,
        )

    def create_hito_manual(self, data: dict[str, Any]) -> Result[CausalMilestone, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        hito = CausalMilestone.from_dict(data)
        hito.status = CausalMilestoneStatus.CANON
        now = _now_iso()
        if not hito.created_at:
            hito.created_at = now
        hito.updated_at = now
        proj.value.causal_milestones.append(hito)
        if hasattr(proj.value, "touch"):
            proj.value.touch()
        self._record("hito_creado", f"Hito '{hito.title}' creado manualmente", hito)
        return Ok(hito)

    def approve_hito(self, hito_or_candidate_id: str) -> Result[CausalMilestone, str]:
        existing = self._get_hito(hito_or_candidate_id)
        if isinstance(existing, Ok):
            existing.value.status = CausalMilestoneStatus.CANON
            existing.value.updated_at = _now_iso()
            self._record("hito_aprobado", f"Hito '{existing.value.title}' aprobado", existing.value)
            return existing

        if self.candidate_service is None:
            return existing
        candidate_result = self.candidate_service.get_candidate(hito_or_candidate_id)
        if isinstance(candidate_result, Error):
            return existing
        candidate = candidate_result.value
        proposed = candidate.proposed_data if isinstance(candidate.proposed_data, dict) else {}
        if proposed.get("kind") != "causal_milestone" or not isinstance(proposed.get("milestone"), dict):
            return Error("Candidate is not a causal milestone")

        hito = CausalMilestone.from_dict(proposed["milestone"])
        hito.status = CausalMilestoneStatus.CANON
        hito.candidate_id = candidate.id
        now = _now_iso()
        if not hito.created_at:
            hito.created_at = now
        hito.updated_at = now
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        proj.value.causal_milestones.append(hito)
        if hasattr(proj.value, "touch"):
            proj.value.touch()
        candidate.state = CandidateState.ACEPTADO
        candidate.final_action = "aceptado"
        candidate.reviewed_at = datetime.now(timezone.utc)
        self._record("hito_aprobado", f"Hito '{hito.title}' aprobado desde candidato", hito)
        return Ok(hito)

    def reject_hito(self, hito_or_candidate_id: str) -> Result[CausalMilestone, str]:
        existing = self._get_hito(hito_or_candidate_id)
        if isinstance(existing, Ok):
            existing.value.status = CausalMilestoneStatus.REJECTED
            existing.value.updated_at = _now_iso()
            self._record("hito_rechazado", f"Hito '{existing.value.title}' rechazado", existing.value)
            return existing
        if self.candidate_service is not None:
            candidate_result = self.candidate_service.get_candidate(hito_or_candidate_id)
            if isinstance(candidate_result, Ok):
                self.candidate_service.reject_candidate(hito_or_candidate_id)
        return existing

    def update_hito(self, hito_id: str, data: dict[str, Any]) -> Result[CausalMilestone, str]:
        current = self._get_hito(hito_id)
        if isinstance(current, Error):
            return current
        merged = current.value.to_dict()
        merged.update(data)
        updated = CausalMilestone.from_dict(merged)
        updated.updated_at = _now_iso()
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for index, hito in enumerate(proj.value.causal_milestones):
            if hito.id == hito_id:
                hito.__dict__.update(updated.__dict__)
                if hasattr(proj.value, "touch"):
                    proj.value.touch()
                self._record("hito_actualizado", f"Hito '{hito.title}' actualizado", hito)
                return Ok(hito)
        return Error(f"Hito '{hito_id[:8]}' not found")

    def list_hitos_for_leaf(self, leaf_id: str) -> Result[list[CausalMilestone], str]:
        return self._filter(lambda h: leaf_id in h.affected_entity_ids)

    def list_hitos_for_branch(self, branch_id: str) -> Result[list[CausalMilestone], str]:
        return self._filter(lambda h: branch_id in h.affected_branch_ids)

    def list_hitos_for_ring(self, ring_id: str) -> Result[list[CausalMilestone], str]:
        return self._filter(lambda h: ring_id in h.affected_layer_ids or ring_id in h.layer_ids)

    def list_hitos_for_relation(self, relation_id: str) -> Result[list[CausalMilestone], str]:
        return self._filter(lambda h: relation_id in h.caused_relation_ids)

    def _filter(self, predicate) -> Result[list[CausalMilestone], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        return Ok([hito for hito in proj.value.causal_milestones if predicate(hito)])

    def list_causal_chain(self, hito_id: str) -> Result[list[CausalMilestone], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        by_id = {hito.id: hito for hito in proj.value.causal_milestones}
        if hito_id not in by_id:
            return Error(f"Hito '{hito_id[:8]}' not found")
        ordered: list[CausalMilestone] = []
        queue = [hito_id]
        seen: set[str] = set()
        while queue:
            current_id = queue.pop(0)
            if current_id in seen or current_id not in by_id:
                continue
            seen.add(current_id)
            current = by_id[current_id]
            ordered.append(current)
            queue.extend(current.causal_child_hito_ids)
        return Ok(ordered)

    def find_relations_without_hito(self) -> Result[list[NarrativeRelation], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        explained_ids = set()
        for hito in proj.value.causal_milestones:
            explained_ids.update(hito.caused_relation_ids)
        causal_types = {
            RelationType.CAUSO,
            RelationType.FUE_CAUSADO_POR,
            RelationType.DERIVA_DE,
            RelationType.CONDICIONA,
            RelationType.EXPLICA,
            RelationType.CONTRADICE,
            RelationType.PRODUCE_CONSECUENCIA_EN,
        }
        missing = [
            relation for relation in proj.value.relations
            if relation.relation_type in causal_types and relation.id not in explained_ids
        ]
        return Ok(missing)

    def find_hitos_without_consequences(self) -> Result[list[CausalMilestone], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        return Ok([hito for hito in proj.value.causal_milestones if not hito.caused_relation_ids])
