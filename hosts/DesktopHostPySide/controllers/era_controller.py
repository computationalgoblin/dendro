"""EraController — BETA1-G02 (Fase G: El Tiempo)."""

from packages.application.era_service import EraService
from hosts.DesktopHostPySide.app_trace import _apptrace


class EraController:
    def __init__(self, project_service=None):
        self.ps = project_service
        self.svc = EraService(project_service=self.ps)

    def list_all(self):
        _apptrace("CTRL EraController.list_all"[:120])
        result = self.svc.list_eras()
        return getattr(result, "value", result)

    def get(self, era_id):
        _apptrace(f"CTRL EraController.get era_id={era_id!r}"[:120])
        return self.svc.get_era(era_id)

    def create(self, data):
        _apptrace(f"CTRL EraController.create data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"[:120])
        return self.svc.create_era(data if isinstance(data, dict) else {"name": str(data)})

    def update(self, era_id, data):
        _apptrace(f"CTRL EraController.update era_id={era_id!r}"[:120])
        return self.svc.update_era(era_id, data or {})

    def delete(self, era_id):
        _apptrace(f"CTRL EraController.delete era_id={era_id!r}"[:120])
        return self.svc.delete_era(era_id)

    def present_year(self):
        _apptrace("CTRL EraController.present_year"[:120])
        result = self.svc.get_present_year()
        return getattr(result, "value", 0)

    def set_present_year(self, year):
        _apptrace(f"CTRL EraController.set_present_year year={year!r}"[:120])
        return self.svc.set_present_year(year)

    def era_for_year(self, year):
        _apptrace(f"CTRL EraController.era_for_year year={year!r}"[:120])
        result = self.svc.era_for_year(year)
        return getattr(result, "value", None)

    def overlap_warnings(self):
        _apptrace("CTRL EraController.overlap_warnings"[:120])
        return self.svc.overlap_warnings()
