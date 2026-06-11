"""ProjectController — wraps ProjectService for UI (B27.1-T01)."""
from __future__ import annotations
from pathlib import Path
from packages.application.project_service import ProjectService
from packages.domain.result import Error
from hosts.DesktopHostPySide.app_trace import _apptrace

class ProjectController:
    def __init__(self, store=None):
        if store is None:
            from packages.persistence.store import ProjectStore
            store = ProjectStore()
        self.store = store
        self.ps = ProjectService(store=self.store)
        self.current_path: str | None = None

    def open(self, path: str):
        _apptrace(f"CTRL ProjectController.open path={path!r}"[:120])
        result = self.ps.open(Path(path))
        if hasattr(result, 'error'):
            raise ValueError(f"Cannot open project: {result.error}")
        self.current_path = path

    def create(self, name: str, path: str | None = None):
        _apptrace(f"CTRL ProjectController.create name={name!r}"[:120])
        result = self.ps.create(name=name)
        if hasattr(result, "error"):
            return result
        project = self.ps.active_project
        if project is not None:
            project.world_layers = []
        if path:
            self.current_path = str(path)
        return result

    def save(self):
        _apptrace(f"CTRL ProjectController.save"[:120])
        if not self.current_path:
            return Error("No project file path selected")
        return self.ps.save(Path(self.current_path))

    def close(self):
        _apptrace(f"CTRL ProjectController.close"[:120])
        self.ps.close()
        self.current_path = None

    @property
    def _proj(self):
        return self.ps.active_project

    def counts(self) -> dict:
        _apptrace(f"CTRL ProjectController.counts"[:120])
        p = self._proj
        if p is None: return {}
        return {"name": p.name, "schema": getattr(p, 'schema_version', '?'),
                "entities": len(getattr(p, 'entities', [])), "relations": len(getattr(p, 'relations', [])),
                "candidates": len(getattr(p, 'candidates', [])), "sessions": len(getattr(p, 'sessions', [])),
                "campaigns": len(getattr(p, 'campaigns', [])), "secrets": len(getattr(p, 'secrets', [])),
                "factions": len(getattr(p, 'factions', [])), "clues": len(getattr(p, 'clues', [])),
                "fronts": len(getattr(p, 'fronts', [])), "clocks": len(getattr(p, 'campaign_clocks', []))}
