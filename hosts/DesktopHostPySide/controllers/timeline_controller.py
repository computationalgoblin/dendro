from packages.application.timeline_service import TimelineService
from hosts.DesktopHostPySide.app_trace import _apptrace

class TimelineController:
    def __init__(self, project_service=None):
        self.ps = project_service; self.svc = TimelineService(project_service=self.ps)

    def list_all(self):
        _apptrace(f"CTRL TimelineController.list_all"[:120])
        result = self.svc.list_events()
        return getattr(result, "value", [])

    def create(self, data):
        _apptrace(f"CTRL TimelineController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self.svc.create_event(data)
