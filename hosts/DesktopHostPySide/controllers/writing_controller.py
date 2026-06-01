"""WritingController — wraps WritingService (B27.2-T09)."""
from packages.application.writing_service import WritingService
from packages.application.project_service import ProjectService
from packages.persistence.store import ProjectStore

class WritingController:
    def __init__(self, project_service=None, store=None):
        store = store or ProjectStore()
        self.ps = project_service or ProjectService(store=store)
        self.ws = WritingService(project_service=self.ps)

    def list_all(self): return self.ws.list_units()
    def create(self, data): return self.ws.create_unit(data)
    def tree(self): return self.ws.get_tree()
