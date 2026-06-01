"""RelationController — wraps RelationService for UI (B27.1-T02)."""
from packages.application.relation_service import RelationService
from packages.application.project_service import ProjectService
from packages.persistence.store import ProjectStore

class RelationController:
    def __init__(self, project_service=None, store=None):
        store = store or ProjectStore()
        self.ps = project_service or ProjectService(store=store)
        self.rs = RelationService(self.ps)

    def list_all(self):
        return list(self.ps.active_project.relations) if self.ps.active_project else []

    def create(self, source_id, target_id, relation_type, data=None):
        return self.rs.create_relation(source_id, target_id, relation_type, data or {})
