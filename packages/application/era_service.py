"""Era service — BETA1-G02 (Fase G: El Tiempo).

CRUD de eras y present_year sobre ``project.project_chronology``.
Contrato: docs/architecture/G01_time_contract.md. Validación de solape
SUAVE (warning, no bloqueo); siempre existe al menos una era.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.domain.era import Era
from packages.domain.result import Error, Ok, Result


@dataclass
class EraService:
    project_service: Any  # ProjectService (avoid circular import)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _chronology(self):
        project = getattr(self.project_service, "active_project", None)
        if project is None:
            return Error("No active project")
        chronology = getattr(project, "project_chronology", None)
        if chronology is None:
            return Error("Project has no chronology container")
        return Ok(chronology)

    def overlap_warnings(self) -> list[str]:
        """Solapes entre eras — advertencias, nunca bloqueo (contrato G01)."""
        chrono = self._chronology()
        if isinstance(chrono, Error):
            return []
        warnings: list[str] = []
        eras = chrono.value.sorted_eras()
        for previous, current in zip(eras, eras[1:]):
            prev_end = previous.end_year
            if prev_end is None or current.start_year <= prev_end:
                warnings.append(
                    f"Las eras '{previous.name}' y '{current.name}' se solapan"
                )
        return warnings

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_eras(self) -> Result[list[Era], str]:
        chrono = self._chronology()
        if isinstance(chrono, Error):
            return chrono
        chrono.value.ensure_default_era()
        return Ok(chrono.value.sorted_eras())

    def get_era(self, era_id: str) -> Result[Era, str]:
        chrono = self._chronology()
        if isinstance(chrono, Error):
            return chrono
        for era in chrono.value.eras:
            if era.id == era_id:
                return Ok(era)
        return Error(f"Era '{era_id}' not found")

    def create_era(self, data: dict[str, Any]) -> Result[Era, str]:
        chrono = self._chronology()
        if isinstance(chrono, Error):
            return chrono
        name = str((data or {}).get("name", "")).strip()
        if not name:
            return Error("Era name cannot be empty")
        era = Era.from_dict(dict(data, name=name))
        if era.end_year is not None and era.end_year < era.start_year:
            return Error("Era end_year is earlier than start_year")
        chrono.value.eras.append(era)
        self._touch()
        return Ok(era)

    def update_era(self, era_id: str, data: dict[str, Any]) -> Result[Era, str]:
        existing = self.get_era(era_id)
        if isinstance(existing, Error):
            return existing
        merged = existing.value.to_dict()
        for key in ("name", "start_year", "end_year", "order", "description"):
            if key in (data or {}):
                merged[key] = data[key]
        updated = Era.from_dict(merged)
        if not updated.name.strip():
            return Error("Era name cannot be empty")
        if updated.end_year is not None and updated.end_year < updated.start_year:
            return Error("Era end_year is earlier than start_year")
        era = existing.value
        era.name = updated.name
        era.start_year = updated.start_year
        era.end_year = updated.end_year
        era.order = updated.order
        era.description = updated.description
        self._touch()
        return Ok(era)

    def delete_era(self, era_id: str) -> Result[None, str]:
        """Elimina una era. Siempre debe quedar al menos una (contrato G01)."""
        chrono = self._chronology()
        if isinstance(chrono, Error):
            return chrono
        eras = chrono.value.eras
        if len(eras) <= 1:
            return Error("Cannot delete the last era: at least one must exist")
        for index, era in enumerate(eras):
            if era.id == era_id:
                del eras[index]
                self._touch()
                return Ok(None)
        return Error(f"Era '{era_id}' not found")

    # ------------------------------------------------------------------
    # Present year
    # ------------------------------------------------------------------

    def get_present_year(self) -> Result[int, str]:
        chrono = self._chronology()
        if isinstance(chrono, Error):
            return chrono
        return Ok(int(chrono.value.present_year))

    def set_present_year(self, year: int) -> Result[int, str]:
        chrono = self._chronology()
        if isinstance(chrono, Error):
            return chrono
        try:
            chrono.value.present_year = int(year)
        except (TypeError, ValueError):
            return Error(f"Invalid present_year: {year!r}")
        self._touch()
        return Ok(chrono.value.present_year)

    # ------------------------------------------------------------------
    # Derivación
    # ------------------------------------------------------------------

    def era_for_year(self, year: int) -> Result[Era | None, str]:
        chrono = self._chronology()
        if isinstance(chrono, Error):
            return chrono
        chrono.value.ensure_default_era()
        return Ok(chrono.value.era_for_year(int(year)))

    def _touch(self) -> None:
        project = getattr(self.project_service, "active_project", None)
        if project is not None and hasattr(project, "touch"):
            project.touch()


__all__ = ["EraService"]
