"""ProjectController — wraps ProjectService for UI (B27.1-T01)."""
from __future__ import annotations
from pathlib import Path
from packages.application.project_service import ProjectService
from packages.domain.result import Error, Result
from hosts.DesktopHostPySide.app_trace import _apptrace

class ProjectController:
    def __init__(self, store=None):
        # El host no importa persistence: ProjectService construye su propio
        # ProjectStore por defecto; `store` queda como punto de inyección (tests).
        self.ps = ProjectService(store=store) if store is not None else ProjectService()
        self.store = self.ps.store
        self._current_path: str | None = None

    @property
    def current_path(self) -> str | None:
        return self._current_path

    @current_path.setter
    def current_path(self, value: str | None) -> None:
        self._current_path = value

    def open(self, path: str) -> Result:
        _apptrace(f"CTRL ProjectController.open path={path!r}"[:120])
        result = self.ps.open(Path(path))
        if isinstance(result, Error):
            return result
        self.current_path = path
        return result

    def create(self, name: str, path: str | None = None):
        _apptrace(f"CTRL ProjectController.create name={name!r}"[:120])
        result = self.ps.create(name=name)
        if isinstance(result, Error):
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
                "candidates": len(getattr(p, 'candidates', []))}
