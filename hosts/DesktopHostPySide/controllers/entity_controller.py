"""EntityController — wraps EntityService for UI (B27.1-T02)."""
from __future__ import annotations

from packages.application.entity_service import EntityService
from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.relation_service import RelationService
from hosts.DesktopHostPySide.app_trace import _apptrace
from hosts.DesktopHostPySide.controllers.mutation_hook import MutationNotifier


class EntityController(MutationNotifier):
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("EntityController requires project_service")
        self.ps = project_service
        self.es = EntityService(self.ps)
        self.rs = RelationService(self.ps)
        # BETA2-MEM-04: motor de impacto (marca Falta regar al guardar canon).
        self.impact = NarrativeImpactService(self.ps)

    def list_all(self):
        _apptrace(f"CTRL EntityController.list_all"[:120])
        return list(self.ps.active_project.entities) if self.ps.active_project else []

    def get(self, eid):
        _apptrace(f"CTRL EntityController.get eid={eid!r}"[:120])
        return self.es.get_by_id(eid)

    def create(self, data):
        _apptrace(f"CTRL EntityController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self._notify_mutation(self.es.create_entity(data))

    def update(self, eid, data):
        _apptrace(f"CTRL EntityController.update eid={eid!r}"[:120])
        return self._notify_mutation(
            self.es.update_entity(eid, data, impact_service=self.impact)
        )

    def archive(self, eid):
        _apptrace(f"CTRL EntityController.archive eid={eid!r}"[:120])
        return self._notify_mutation(self.es.archive_entity(eid))

    def restore(self, eid):
        _apptrace(f"CTRL EntityController.restore eid={eid!r}"[:120])
        return self._notify_mutation(self.es.restore_entity(eid))

    def relations_for(self, eid):
        _apptrace(f"CTRL EntityController.relations_for eid={eid!r}"[:120])
        result = self.rs.get_neighborhood(eid)
        return result.value if hasattr(result, "value") else []

    def delete(self, eid):
        _apptrace(f"CTRL EntityController.delete eid={eid!r}"[:120])
        return self._notify_mutation(self.es.delete_entity(eid))
