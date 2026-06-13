
"""CandidateService — CRUD, acceptance, merge, history (B14-T02)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.domain.candidate_issue import Candidate, CandidateState, CandidateType
from packages.domain.causal_milestone import CausalMilestone
from packages.domain.result import Error, Ok, Result
from packages.application.project_chronology_service import ProjectChronologyService


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CandidateService:
    project_service: Any
    entity_service: Any = None
    relation_service: Any = None
    history_service: Any = None

    def _proj(self):
        p = self.project_service.active_project
        if p is None:
            return Error("No active project")
        return Ok(p)

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_candidate(self, data: dict) -> Result[Candidate, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        c = Candidate.from_dict(data)
        proj.value.candidates.append(c)
        return Ok(c)

    def create_causal_milestone_candidate(
        self,
        milestone: CausalMilestone,
        source: str = "ia",
        confidence: float = 0.5,
        justification: str = "",
    ) -> Result[Candidate, str]:
        """Create a review-only candidate for a causal milestone.

        This does not append to project.causal_milestones and therefore never
        canonizes IA output automatically. Acceptance is handled by a later B41
        service/UI ticket.
        """
        data = {
            "title": f"Hito: {milestone.title}",
            "candidate_type": CandidateType.SUGERENCIA_IA.value,
            "state": CandidateState.PENDIENTE.value,
            "proposed_data": {
                "kind": "causal_milestone",
                "milestone": milestone.to_dict(),
            },
            "affected_entity_ids": list(milestone.affected_entity_ids),
            "affected_relation_ids": list(milestone.caused_relation_ids),
            "source": source,
            "confidence": confidence,
            "justification": justification or milestone.rationale,
            "expected_impact": "Propone un hito causal/histórico para revisión; no modifica canon.",
            "metadata": {
                "kind": "causal_milestone",
                "review_required": True,
                "canonizes_automatically": False,
                "layer_ids": list(milestone.layer_ids),
            },
        }
        return self.create_candidate(data)

    def get_candidate(self, cid: str) -> Result[Candidate, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for c in proj.value.candidates:
            if c.id == cid:
                return Ok(c)
        return Error(f"Candidate '{cid[:8]}' not found")

    def list_candidates(
        self, state: str | None = None, ctype: str | None = None,
    ) -> Result[list[Candidate], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        result = list(proj.value.candidates)
        if state:
            result = [c for c in result if c.state.value == state]
        if ctype:
            result = [c for c in result if c.candidate_type.value == ctype]
        return Ok(result)

    def list_candidates_by_entity(self, eid: str) -> Result[list[Candidate], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        return Ok([c for c in proj.value.candidates if eid in c.affected_entity_ids])

    def list_candidates_by_source(self, source: str) -> Result[list[Candidate], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        return Ok([c for c in proj.value.candidates if c.source == source])

    def update_candidate(self, cid: str, data: dict) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        if "title" in data:
            c.title = data["title"]
        if "proposed_data" in data:
            c.proposed_data = data["proposed_data"]
        if "confidence" in data:
            conf = float(data["confidence"])
            if conf < 0.0 or conf > 1.0:
                return Error("confidence must be 0.0-1.0")
            c.confidence = conf
        if "justification" in data:
            c.justification = data["justification"]
        if "source" in data:
            c.source = data["source"]
        return Ok(c)

    # ── Decisions ─────────────────────────────────────────────────────

    def _add_history(self, proj, event_type: str, entity_id: str = "",
                     note: str = "", candidate_id: str = "") -> None:
        if not self.history_service:
            return
        try:
            self.history_service.add_entry({
                "event_type": event_type,
                "entity_id": entity_id,
                "description": note or f"Candidate {candidate_id[:8]} decision",
                "metadata": {"candidate_id": candidate_id},
            })
        except Exception:
            pass  # history is non-critical

    def accept_candidate(self, cid: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        proj = self._proj()
        if isinstance(proj, Error):
            return proj

        entity_id = ""
        if c.candidate_type == CandidateType.ENTIDAD:
            if not self.entity_service:
                return Error("EntityService not available")
            result = self.entity_service.create_entity(c.proposed_data)
            if isinstance(result, Error):
                return result
            entity_id = result.value.id
        elif c.candidate_type == CandidateType.RELACION:
            if not self.relation_service:
                return Error("RelationService not available")
            # Resolve endpoints: prefer direct IDs, fall back to name lookup
            sid = c.proposed_data.get("source_id", "")
            tid = c.proposed_data.get("target_id", "")
            if not sid or not tid:
                sid, tid = self._resolve_relation_endpoints_by_name(
                    proj.value, c.proposed_data
                )
            if not sid or not tid:
                return Error(
                    "No se pudieron encontrar las entidades para esta relación. "
                    "Asegúrate de que ambas entidades existen en el proyecto."
                )
            found_s = any(e.id == sid for e in proj.value.entities)
            found_t = any(e.id == tid for e in proj.value.entities)
            if not found_s or not found_t:
                return Error(
                    "Relation endpoints not found in project"
                )
            result = self.relation_service.create_relation(
                source_id=sid, target_id=tid,
                relation_type=c.proposed_data.get("relation_type", ""),
                data=c.proposed_data,
            )
            if isinstance(result, Error):
                return result
            entity_id = ""
        elif c.proposed_data.get("kind") == "causal_milestone":
            milestone_data = c.proposed_data.get("milestone")
            if not isinstance(milestone_data, dict):
                return Error("Causal milestone candidate has no milestone payload")
            hito = CausalMilestone.from_dict(milestone_data)
            proj.value.causal_milestones.append(hito)
            chronology = getattr(proj.value, "project_chronology", None)
            if chronology is not None and hasattr(chronology, "link_milestone"):
                chronology.link_milestone(hito.id)
            if hasattr(proj.value, "touch"):
                proj.value.touch()
        elif c.proposed_data.get("kind") == "project_chronology_suggestion":
            result = ProjectChronologyService(self.project_service).apply_candidate(c.proposed_data)
            if isinstance(result, Error):
                return result
        else:
            # Other types: just mark accepted without creating entity/relation
            pass

        c.state = CandidateState.ACEPTADO
        c.final_action = "aceptado"
        c.reviewed_at = _now()
        self._add_history(proj.value, "candidato_aceptado", entity_id,
                          f"Candidate '{c.title}' accepted", c.id)
        return Ok(c)

    def accept_with_changes(self, cid: str, modified: dict) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        merged = dict(c.proposed_data)
        merged.update(modified)
        c.proposed_data = merged
        result = self.accept_candidate(cid)
        if not isinstance(result, Error):
            result.value.state = CandidateState.EDITADO_ACEPTADO
            result.value.final_action = "editado_aceptado"
        return result

    def partial_accept_candidate(
        self, cid: str, accepted: dict, note: str = "",
    ) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        c.state = CandidateState.PARCIALMENTE_ACEPTADO
        c.final_action = "parcialmente_aceptado"
        c.reviewed_at = _now()
        c.proposed_data = accepted
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_parcialmente_aceptado",
                          note=note, candidate_id=c.id)
        return Ok(c)

    def reject_candidate(self, cid: str, note: str = "") -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        c.state = CandidateState.RECHAZADO
        c.final_action = "rechazado"
        c.reviewed_at = _now()
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_rechazado",
                          note=note, candidate_id=c.id)
        return Ok(c)

    def postpone_candidate(self, cid: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        c.state = CandidateState.POSPUESTO
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_pospuesto", candidate_id=c.id)
        return Ok(c)

    def merge_candidate(self, cid: str, entity_id: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        target = None
        for e in proj.value.entities:
            if e.id == entity_id:
                target = e
                break
        if not target:
            return Error(f"Entity '{entity_id[:8]}' not found")
        # Merge: set non-empty fields from proposed_data onto target
        for key, val in c.proposed_data.items():
            if val and hasattr(target, key):
                setattr(target, key, val)
        c.state = CandidateState.FUSIONADO
        c.final_action = "fusionado"
        c.reviewed_at = _now()
        self._add_history(proj.value, "candidato_fusionado", entity_id,
                          f"Candidate '{c.title}' merged into entity", c.id)
        return Ok(c)

    def convert_candidate(self, cid: str, new_type: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        try:
            c.candidate_type = CandidateType(new_type)
        except ValueError:
            return Error(f"Invalid CandidateType: {new_type}")
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_convertido",
                          f"Converted to {new_type}", candidate_id=c.id)
        return Ok(c)

    def archive_candidate(self, cid: str) -> Result[Candidate, str]:
        rc = self.get_candidate(cid)
        if isinstance(rc, Error):
            return rc
        c = rc.value
        c.state = CandidateState.ARCHIVADO
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        self._add_history(proj.value, "candidato_archivado", candidate_id=c.id)
        return Ok(c)

    @staticmethod
    def _resolve_relation_endpoints_by_name(project: Any, proposed_data: dict) -> tuple[str, str]:
        """Resolve source_name/target_name to real entity IDs by fuzzy name match."""
        source_name = str(proposed_data.get("source_name") or "").strip().lower()
        target_name = str(proposed_data.get("target_name") or "").strip().lower()
        entities = list(getattr(project, "entities", []) or [])
        sid = ""
        tid = ""
        for entity in entities:
            name = str(getattr(entity, "name", "")).strip().lower()
            if not sid and source_name and name == source_name:
                sid = str(getattr(entity, "id", ""))
            elif not sid and source_name and source_name in name:
                sid = str(getattr(entity, "id", ""))
            if not tid and target_name and name == target_name:
                tid = str(getattr(entity, "id", ""))
            elif not tid and target_name and target_name in name:
                tid = str(getattr(entity, "id", ""))
        return sid, tid


__all__ = ["CandidateService"]
