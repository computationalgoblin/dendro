from packages.application.timeline_service import TimelineService
class TimelineController:
    def __init__(self, project_service=None): self.ps = project_service; self.svc = TimelineService(project_service=self.ps)
    def list_all(self):
        result = self.svc.list_events()
        return getattr(result, "value", [])
    def create(self, data): return self.svc.create_event(data)
