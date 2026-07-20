"""RelationController — wraps RelationService for UI (B27.1-T02)."""
from __future__ import annotations

from packages.application.narrative_impact_service import NarrativeImpactService
from packages.application.relation_service import RelationService
from hosts.DesktopHostPySide.app_trace import _apptrace


class RelationController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("RelationController requires project_service")
        self.ps = project_service
        self.rs = RelationService(self.ps)
        # BETA2-MEM-04: motor de impacto (marca Falta regar al guardar canon).
        self.impact = NarrativeImpactService(self.ps)

    def list_all(self):
        _apptrace(f"CTRL RelationController.list_all"[:120])
        return list(self.ps.active_project.relations) if self.ps.active_project else []

    def get(self, relation_id):
        _apptrace(f"CTRL RelationController.get relation_id={relation_id!r}"[:120])
        return self.rs.get_by_id(relation_id)

    def create(self, source_id, target_id, relation_type, data=None):
        _apptrace(f"CTRL RelationController.create source={source_id!r} target={target_id!r} type={relation_type!r}"[:120])
        return self.rs.create_relation(source_id, target_id, relation_type, data or {})

    def update(self, relation_id, data):
        _apptrace(f"CTRL RelationController.update relation_id={relation_id!r}"[:120])
        return self.rs.update_relation(relation_id, data, impact_service=self.impact)

    def archive(self, relation_id):
        _apptrace(f"CTRL RelationController.archive relation_id={relation_id!r}"[:120])
        return self.rs.archive_relation(relation_id)

    def restore(self, relation_id):
        _apptrace(f"CTRL RelationController.restore relation_id={relation_id!r}"[:120])
        return self.rs.restore_relation(relation_id)

    def delete(self, relation_id):
        _apptrace(f"CTRL RelationController.delete relation_id={relation_id!r}"[:120])
        return self.rs.delete_relation(relation_id)
