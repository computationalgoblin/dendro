from packages.application.framework_service import FrameworkService
from hosts.DesktopHostPySide.app_trace import _apptrace

class FrameworkController:
    def __init__(self, project_service=None):
        self.ps = project_service; self.svc = FrameworkService(project_service=self.ps)

    def list_all(self):
        _apptrace(f"CTRL FrameworkController.list_all"[:120])
        result = self.svc.list_frameworks()
        return getattr(result, "value", [])

    def create(self, data):
        _apptrace(f"CTRL FrameworkController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self.svc.create_framework(data)
