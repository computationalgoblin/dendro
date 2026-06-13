"""Desktop controller for ProjectChronologyService (H05)."""

from __future__ import annotations

from typing import Any

from hosts.DesktopHostPySide.app_trace import _apptrace
from packages.application.project_chronology_service import ProjectChronologyService


class ProjectChronologyController:
    def __init__(self, project_service: Any):
        if project_service is None:
            raise ValueError("ProjectChronologyController requires project_service")
        self.ps = project_service
        self.service = ProjectChronologyService(project_service)

    def get(self):
        _apptrace("CTRL ProjectChronologyController.get")
        return self.service.get()

    def update(self, data: dict):
        _apptrace(f"CTRL ProjectChronologyController.update keys={list(data.keys())}"[:120])
        return self.service.update(data)

    def apply_candidate(self, proposal: dict):
        _apptrace("CTRL ProjectChronologyController.apply_candidate")
        return self.service.apply_candidate(proposal)
