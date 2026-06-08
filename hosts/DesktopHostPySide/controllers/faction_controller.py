"""FactionController — wraps FactionService for Desktop UI."""
from __future__ import annotations

from packages.application.entity_service import EntityService
from packages.application.faction_service import FactionService
from hosts.DesktopHostPySide.app_trace import _apptrace


class FactionController:
    def __init__(self, project_service):
        if project_service is None:
            raise ValueError("FactionController requires project_service")
        self.ps = project_service
        self.entity_service = EntityService(project_service=self.ps)
        self.svc = FactionService(project_service=self.ps, entity_service=self.entity_service)

    def list_factions(self, state=None):
        _apptrace(f"CTRL FactionController.list_factions state={state!r}"[:120])
        return self.svc.list_factions(state=state)

    def list_fronts(self, state=None):
        _apptrace(f"CTRL FactionController.list_fronts state={state!r}"[:120])
        return self.svc.list_fronts(state=state)

    def get_faction(self, faction_id):
        _apptrace(f"CTRL FactionController.get_faction faction_id={faction_id!r}"[:120])
        return self.svc.get_faction(faction_id)

    def update_faction(self, faction_id, data):
        _apptrace(f"CTRL FactionController.update_faction faction_id={faction_id!r}"[:120])
        return self.svc.update_faction(faction_id, data)

    def get_front(self, front_id):
        _apptrace(f"CTRL FactionController.get_front front_id={front_id!r}"[:120])
        return self.svc.get_front(front_id)

    def update_front(self, front_id, data):
        _apptrace(f"CTRL FactionController.update_front front_id={front_id!r}"[:120])
        return self.svc.update_front(front_id, data)

    def create_faction(self, data):
        _apptrace(f"CTRL FactionController.create_faction data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self.svc.create_faction(data)

    def create_front(self, data):
        _apptrace(f"CTRL FactionController.create_front data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self.svc.create_front(data)

    def add_stage(self, front_id, data):
        _apptrace(f"CTRL FactionController.add_stage front_id={front_id!r}"[:120])
        return self.svc.add_stage(front_id, data)

    def add_ally(self, faction_id, other_id):
        _apptrace(f"CTRL FactionController.add_ally faction_id={faction_id!r} other_id={other_id!r}"[:120])
        return self.svc.add_ally(faction_id, other_id)

    def add_enemy(self, faction_id, other_id):
        _apptrace(f"CTRL FactionController.add_enemy faction_id={faction_id!r} other_id={other_id!r}"[:120])
        return self.svc.add_enemy(faction_id, other_id)

    def run_validation(self):
        _apptrace(f"CTRL FactionController.run_validation"[:120])
        return self.svc.run_faction_validation()

    def pending_faction_entities(self):
        _apptrace(f"CTRL FactionController.pending_faction_entities"[:120])
        project = self.ps.active_project
        if project is None:
            return []
        existing = {f.entity_id for f in getattr(project, "factions", [])}
        return [
            e for e in getattr(project, "entities", [])
            if getattr(getattr(e, "entity_type", None), "value", None) == "faccion" and e.id not in existing
        ]
