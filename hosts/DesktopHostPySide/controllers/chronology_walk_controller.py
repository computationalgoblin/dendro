"""ChronologyWalkController — adaptador UI sobre ChronologyWalkService (CRON).

Adaptador fino: delega toda la lógica en el servicio; nunca toca persistencia ni
las colecciones de dominio directamente.
"""

from __future__ import annotations

from typing import Any

from hosts.DesktopHostPySide.app_trace import _apptrace
from packages.application.candidate_service import CandidateService
from packages.application.causal_milestone_service import CausalMilestoneService
from packages.application.chronology_walk_service import ChronologyWalkService
from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService


class ChronologyWalkController:
    """Adaptador fino: delega en ChronologyWalkService."""

    def __init__(self, project_service: Any, ai_job_service: Any):
        if project_service is None:
            raise ValueError("ChronologyWalkController requires project_service")
        if ai_job_service is None:
            raise ValueError("ChronologyWalkController requires ai_job_service")
        self.ps = project_service
        # CandidateService totalmente cableada (entity/relation) para que la
        # aplicación atómica del paso pueda materializar canon coherente.
        self.cs = CandidateService(
            project_service=self.ps,
            entity_service=EntityService(self.ps),
            relation_service=RelationService(self.ps),
        )
        self.svc = ChronologyWalkService(
            project_service=self.ps,
            ai_job_service=ai_job_service,
            candidate_service=self.cs,
            milestone_service=CausalMilestoneService(
                project_service=self.ps, candidate_service=self.cs
            ),
        )

    def apply_step(self, session_id: str, items: list[dict]):
        _apptrace(
            f"CTRL ChronologyWalkController.apply_step id={session_id!r} n={len(items)}"[:120]
        )
        return self.svc.apply_step(session_id, items)

    def start(self, start_milestone_id: str, direction, mode, depth, aggressiveness):
        _apptrace(
            f"CTRL ChronologyWalkController.start id={start_milestone_id!r} dir={direction}"[:120]
        )
        return self.svc.start_walk(start_milestone_id, direction, mode, depth, aggressiveness)

    def active(self):
        _apptrace("CTRL ChronologyWalkController.active"[:120])
        return self.svc.get_active_session()

    def resume(self, session_id: str):
        _apptrace(f"CTRL ChronologyWalkController.resume id={session_id!r}"[:120])
        return self.svc.resume(session_id)

    def analyze(self, session_id: str):
        _apptrace(f"CTRL ChronologyWalkController.analyze id={session_id!r}"[:120])
        return self.svc.analyze_step(session_id)

    def decide(self, session_id: str, decision: str, note: str = ""):
        _apptrace(f"CTRL ChronologyWalkController.decide id={session_id!r} d={decision!r}"[:120])
        return self.svc.record_decision(session_id, decision, note)

    def advance(self, session_id: str):
        _apptrace(f"CTRL ChronologyWalkController.advance id={session_id!r}"[:120])
        return self.svc.advance(session_id)

    def stop(self, session_id: str):
        _apptrace(f"CTRL ChronologyWalkController.stop id={session_id!r}"[:120])
        return self.svc.stop(session_id)

    def finalize(self, session_id: str):
        _apptrace(f"CTRL ChronologyWalkController.finalize id={session_id!r}"[:120])
        return self.svc.finalize_report(session_id)

    def attach_candidates(self, session_id: str, candidate_ids: list[str]):
        _apptrace(f"CTRL ChronologyWalkController.attach_candidates id={session_id!r}"[:120])
        return self.svc.attach_generated_candidates(session_id, candidate_ids)
