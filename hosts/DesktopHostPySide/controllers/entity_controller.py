"""EntityController — wraps EntityService for UI (B27.1-T02)."""
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService

class EntityController:
    def __init__(self, project_service=None):
        self.ps = project_service or ProjectService(store=store)
        self.es = EntityService(self.ps)

    def list_all(self):
        return list(self.ps.active_project.entities) if self.ps.active_project else []

    def get(self, eid):
        return self.es.get_by_id(eid)

    def create(self, data):
        return self.es.create_entity(data)

    def update(self, eid, data):
        return self.es.update_entity(eid, data)
