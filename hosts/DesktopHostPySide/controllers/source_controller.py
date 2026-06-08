from packages.application.source_service import SourceService
from hosts.DesktopHostPySide.app_trace import _apptrace


class SourceController:
    def __init__(self, project_service=None):
        self.ps = project_service
        self.svc = SourceService(project_service=self.ps)

    def list_all(self):
        _apptrace(f"CTRL SourceController.list_all"[:120])
        result = self.svc.list_all()
        return getattr(result, "value", [])

    def create(self, data):
        _apptrace(f"CTRL SourceController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self.svc.create_source(data)
