"""ImportController — wraps ImportService for UI (B27.2-T01)."""
from pathlib import Path
from packages.application.import_service import ImportService
from packages.domain.import_models import ImportFormat
from packages.domain.result import Error
from hosts.DesktopHostPySide.app_trace import _apptrace

class ImportController:
    def __init__(self, project_service=None):
        self.ps = project_service
        self.svc = ImportService(project_service=self.ps)

    def import_document(self, path):
        _apptrace(f"CTRL ImportController.import_document path={path!r}"[:120])
        suffix = Path(path).suffix.lower()
        if suffix == ".txt":
            fmt = ImportFormat.TEXT_PLAIN
        elif suffix == ".pdf":
            fmt = ImportFormat.PDF
        else:
            return Error(f"Unsupported format: {suffix}. Use .txt or .pdf")
        return self.svc.import_document(path, fmt)

    def list_baskets(self):
        _apptrace(f"CTRL ImportController.list_baskets"[:120])
        return self.svc.list_baskets() if hasattr(self.svc, 'list_baskets') else []

    def get_basket(self, bid):
        _apptrace(f"CTRL ImportController.get_basket bid={bid!r}"[:120])
        return self.svc.get_basket(bid)

    def accept(self, basket_id, cand_id):
        _apptrace(f"CTRL ImportController.accept basket_id={basket_id!r} cand_id={cand_id!r}"[:120])
        return self.svc.accept_import_candidate(basket_id, cand_id)

    def reject(self, basket_id, cand_id):
        _apptrace(f"CTRL ImportController.reject basket_id={basket_id!r} cand_id={cand_id!r}"[:120])
        return self.svc.reject_import_candidate(basket_id, cand_id)

    def edit(self, basket_id, cand_id, data):
        _apptrace(f"CTRL ImportController.edit basket_id={basket_id!r} cand_id={cand_id!r}"[:120])
        return self.svc.edit_import_candidate(basket_id, cand_id, data)

    def merge(self, basket_id, cand_ids):
        _apptrace(f"CTRL ImportController.merge basket_id={basket_id!r} cand_ids={cand_ids!r}"[:120])
        return self.svc.merge_import_candidates(basket_id, cand_ids)

    def partial(self, basket_id, filters=None):
        _apptrace(f"CTRL ImportController.partial basket_id={basket_id!r}"[:120])
        return self.svc.partial_import(basket_id, filters or {})
