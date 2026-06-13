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
        elif suffix in {".md", ".markdown"}:
            fmt = ImportFormat.MARKDOWN
        elif suffix == ".pdf":
            fmt = ImportFormat.PDF
        else:
            return Error(f"Unsupported format: {suffix}. Use .txt, .md, .markdown or .pdf")
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

    def apply_to_canon(self, basket_id, cand_id):
        _apptrace(f"CTRL ImportController.apply_to_canon basket_id={basket_id!r} cand_id={cand_id!r}"[:120])
        return self.svc.apply_import_candidate_to_canon(basket_id, cand_id)

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

    def extract_ai_candidates(self, basket_id):
        _apptrace(f"CTRL ImportController.extract_ai_candidates basket_id={basket_id!r}"[:120])
        return self.svc.extract_ai_candidates(basket_id)

    def analyze_duplicates(self, basket_id):
        _apptrace(f"CTRL ImportController.analyze_duplicates basket_id={basket_id!r}"[:120])
        return self.svc.analyze_import_duplicates(basket_id)

    def accept_merge_suggestion(self, basket_id, suggestion_id):
        _apptrace(f"CTRL ImportController.accept_merge_suggestion basket_id={basket_id!r} suggestion_id={suggestion_id!r}"[:120])
        return self.svc.accept_import_merge_suggestion(basket_id, suggestion_id)

    def reject_merge_suggestion(self, basket_id, suggestion_id):
        _apptrace(f"CTRL ImportController.reject_merge_suggestion basket_id={basket_id!r} suggestion_id={suggestion_id!r}"[:120])
        return self.svc.reject_import_merge_suggestion(basket_id, suggestion_id)
