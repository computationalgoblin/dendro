"""EntityController — wraps EntityService for UI (B27.1-T02)."""
from __future__ import annotations

from packages.application.entity_service import EntityService
from packages.application.relation_service import RelationService


class EntityController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("EntityController requires project_service")
        self.ps = project_service
        self.es = EntityService(self.ps)
        self.rs = RelationService(self.ps)

    def list_all(self):
        return list(self.ps.active_project.entities) if self.ps.active_project else []

    def get(self, eid):
        return self.es.get_by_id(eid)

    def create(self, data):
        return self.es.create_entity(data)

    def update(self, eid, data):
        return self.es.update_entity(eid, data)

    def archive(self, eid):
        return self.es.archive_entity(eid)

    def restore(self, eid):
        return self.es.restore_entity(eid)

    def relations_for(self, eid):
        result = self.rs.get_neighborhood(eid)
        return result.value if hasattr(result, "value") else []
