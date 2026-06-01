"""ImportController — wraps ImportService for UI (B27.2-T01)."""
from pathlib import Path
from packages.application.import_service import ImportService
from packages.domain.import_models import ImportFormat
from packages.domain.result import Error

class ImportController:
    def __init__(self, project_service=None):
        self.ps = project_service
        self.svc = ImportService(project_service=self.ps)

    def import_document(self, path):
        suffix = Path(path).suffix.lower()
        if suffix == ".txt":
            fmt = ImportFormat.TEXT_PLAIN
        elif suffix == ".pdf":
            fmt = ImportFormat.PDF
        else:
            return Error(f"Unsupported format: {suffix}. Use .txt or .pdf")
        return self.svc.import_document(path, fmt)

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
