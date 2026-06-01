"""FactionController — wraps FactionService for Desktop UI."""
from __future__ import annotations

from packages.application.entity_service import EntityService
from packages.application.faction_service import FactionService


class FactionController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("FactionController requires project_service")
        self.ps = project_service
        self.entity_service = EntityService(project_service=self.ps)
        self.svc = FactionService(project_service=self.ps, entity_service=self.entity_service)

    def list_factions(self, state=None):
        return self.svc.list_factions(state=state)

    def list_fronts(self, state=None):
        return self.svc.list_fronts(state=state)

    def get_faction(self, faction_id):
        return self.svc.get_faction(faction_id)

    def update_faction(self, faction_id, data):
        return self.svc.update_faction(faction_id, data)

    def get_front(self, front_id):
        return self.svc.get_front(front_id)

    def update_front(self, front_id, data):
        return self.svc.update_front(front_id, data)

    def create_faction(self, data):
        return self.svc.create_faction(data)

    def create_front(self, data):
        return self.svc.create_front(data)

    def add_stage(self, front_id, data):
        return self.svc.add_stage(front_id, data)

    def add_ally(self, faction_id, other_id):
        return self.svc.add_ally(faction_id, other_id)

    def add_enemy(self, faction_id, other_id):
        return self.svc.add_enemy(faction_id, other_id)

    def run_validation(self):
        return self.svc.run_faction_validation()

    def pending_faction_entities(self):
        project = self.ps.active_project
        if project is None:
            return []
        existing = {f.entity_id for f in getattr(project, "factions", [])}
        return [
            e for e in getattr(project, "entities", [])
            if getattr(getattr(e, "entity_type", None), "value", None) == "faccion" and e.id not in existing
        ]
