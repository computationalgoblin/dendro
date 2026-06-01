"""ImportController — wraps ImportService for UI (B27.2-T01)."""
from packages.application.import_service import ImportService
from packages.application.project_service import ProjectService
from packages.persistence.store import ProjectStore

class ImportController:
    def __init__(self, project_service=None, store=None):
        store = store or ProjectStore()
        self.ps = project_service or ProjectService(store=store)
        self.svc = ImportService(project_service=self.ps)

    def import_document(self, path): self.svc.import_document(path)
        return self.svc.import_document(path)

    def list_baskets(self):
        return self.svc.list_baskets() if hasattr(self.svc, 'list_baskets') else []

    def get_basket(self, bid):
        return self.svc.get_basket(bid)

    def accept(self, basket_id, cand_id):
        return self.svc.accept_import_candidate(basket_id, cand_id)

    def reject(self, basket_id, cand_id):
        return self.svc.reject_import_candidate(basket_id, cand_id)

    def edit(self, basket_id, cand_id, data):
        return self.svc.edit_import_candidate(basket_id, cand_id, data)

    def merge(self, basket_id, cand_ids):
        return self.svc.merge_import_candidates(basket_id, cand_ids)

    def partial(self, basket_id, filters=None):
        return self.svc.partial_import(basket_id, filters or {})
