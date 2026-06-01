from packages.application.source_service import SourceService
class SourceController:
    def __init__(self, project_service=None): self.ps = project_service; self.svc = SourceService(project_service=self.ps)
    def list_all(self): return self.svc.list_all()
    def create(self, data): return self.svc.create_source(data)
