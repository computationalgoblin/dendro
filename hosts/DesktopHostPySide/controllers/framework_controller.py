from packages.application.framework_service import FrameworkService
class FrameworkController:
    def __init__(self, project_service=None): self.ps = project_service; self.svc = FrameworkService(project_service=self.ps)
    def list_all(self): return self.svc.list_frameworks()
    def create(self, data): return self.svc.create_framework(data)
