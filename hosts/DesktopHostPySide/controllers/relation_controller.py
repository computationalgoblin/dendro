"""RelationController — wraps RelationService for UI (B27.1-T02)."""
from __future__ import annotations

from packages.application.relation_service import RelationService


class RelationController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("RelationController requires project_service")
        self.ps = project_service
        self.rs = RelationService(self.ps)

    def list_all(self):
        return list(self.ps.active_project.relations) if self.ps.active_project else []

    def get(self, relation_id):
        return self.rs.get_by_id(relation_id)

    def create(self, source_id, target_id, relation_type, data=None):
        return self.rs.create_relation(source_id, target_id, relation_type, data or {})

    def update(self, relation_id, data):
        return self.rs.update_relation(relation_id, data)

    def archive(self, relation_id):
        return self.rs.archive_relation(relation_id)

    def restore(self, relation_id):
        return self.rs.restore_relation(relation_id)
