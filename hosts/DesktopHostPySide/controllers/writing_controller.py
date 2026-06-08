"""WritingController — wraps WritingService (B27.2-T09)."""
from packages.application.writing_service import WritingService
from packages.application.project_service import ProjectService
from hosts.DesktopHostPySide.app_trace import _apptrace

class WritingController:
    def __init__(self, project_service=None):
        self.ps = project_service or ProjectService(store=store)
        self.ws = WritingService(project_service=self.ps)

    def list_all(self):
        _apptrace(f"CTRL WritingController.list_all"[:120])
        return self.ws.list_units()

    def create(self, data):
        _apptrace(f"CTRL WritingController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self.ws.create_unit(data)

    def tree(self):
        _apptrace(f"CTRL WritingController.tree"[:120])
        return self.ws.get_tree()
