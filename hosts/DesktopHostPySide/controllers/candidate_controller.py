"""CandidateController — wraps CandidateService (B27.1-T03)."""
from __future__ import annotations

from packages.application.candidate_service import CandidateService
from packages.application.entity_service import EntityService
from packages.application.history_service import HistoryService
from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.relation_service import RelationService
from packages.application.source_service import SourceService
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.controllers.mutation_hook import MutationNotifier


class CandidateController(MutationNotifier):
    """BETA-MULTIAGENT2-FIX-14 (G2-22): hereda el aviso de mutación.

    Hasta aquí era una clase suelta: aceptar/rechazar/estadiar una semilla mutaba
    el canon en memoria y NADIE se enteraba. La cadena rota era, en orden: sin
    ``on_mutated`` → sin ``_dirty`` → sin autoguardado → sin
    ``_record_undo_snapshot`` → ``UndoHistory.can_undo()`` False → Ctrl+Z inerte.
    De paso, los candidatos estadiados por un job de IA ya pagado vivían solo en
    RAM hasta que otra cosa guardase (GUI-19).
    """

    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("CandidateController requires project_service")
        self.ps = project_service
        self.cs = CandidateService(
            project_service=self.ps,
            entity_service=EntityService(self.ps),
            relation_service=RelationService(self.ps),
            # BETA-MULTIAGENT2-FIX-08 (G2-14/B3): sin estos dos, aceptar una semilla
            # dejaba el canon sin fuente y el historial mudo (ni un solo evento
            # `aceptacion_sugerencia` tras 24 entidades y una aceptación).
            history_service=HistoryService(self.ps),
            source_service=SourceService(project_service=self.ps),
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
        return self._notify_mutation(self.cs.create_candidate(data))

    def accept(self, cid):
        _apptrace(f"CTRL CandidateController.accept cid={cid!r}"[:120])
        return self._notify_mutation(self.cs.accept_candidate(cid, impact_service=self.impact))

    def reject(self, cid):
        _apptrace(f"CTRL CandidateController.reject cid={cid!r}"[:120])
        return self._notify_mutation(self.cs.reject_candidate(cid))

    def postpone(self, cid):
        _apptrace(f"CTRL CandidateController.postpone cid={cid!r}"[:120])
        return self._notify_mutation(self.cs.postpone_candidate(cid))

    def merge(self, cid, target_entity_id):
        _apptrace(f"CTRL CandidateController.merge cid={cid!r} target={target_entity_id!r}"[:120])
        return self._notify_mutation(self.cs.merge_candidate(cid, target_entity_id))
