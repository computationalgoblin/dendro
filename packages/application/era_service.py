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
            return Error("El nombre de la era no puede estar vacío.")
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
            return Error("El nombre de la era no puede estar vacío.")
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
    # BETA2-CAL: eras encadenadas por duración
    # ------------------------------------------------------------------

    def set_eras_from_durations(
        self,
        durations: list[tuple[str, int]],
        present_index: int,
        present_year_within: int,
        *,
        start_year: int = 0,
    ) -> Result[int, str]:
        """Reemplaza las eras por una cadena derivada de ``(nombre, duración)``.

        Las eras se encadenan: ``start`` = ``start_year`` + suma de duraciones previas;
        todas cerradas salvo la ÚLTIMA, que queda ABIERTA (``end_year=None``) para
        preservar la no-atemporalidad. Fija ``present_year`` absoluto a partir de (era +
        año dentro de la era, estilo regnal) y lo devuelve. Reusa ids/descripciones
        existentes por posición para no churnear. Contrato G01: siempre ≥1 era.

        BETA2-FIX-12 (G2-29): ``start_year`` es el ANCLA del origen de la
        cadena — «este calendario empieza en el año 1900». Antes el cursor era 0 fijo
        y quien escribía de ESTE mundo tenía que inventarse una era tapón de 1.900
        años vacíos para que su eje coincidiera con el anno domini. Se mueve el
        ORIGEN, NO se reabre el editor por-era de años absolutos que BETA2-CAL retiró
        por modelo paralelo: las eras siguen encadenándose por duración. Por defecto
        vale 0, así que un proyecto existente se reconfigura exactamente igual.
        """
        chrono = self._chronology()
        if isinstance(chrono, Error):
            return chrono
        items = list(durations or [])
        if not items:
            return Error("At least one era is required")
        try:
            cursor = int(start_year)
        except (TypeError, ValueError):
            return Error(f"Invalid start_year: {start_year!r}")
        existing = list(chrono.value.eras)
        new_eras: list[Era] = []
        for index, item in enumerate(items):
            name = str(item[0]).strip()
            if not name:
                return Error("El nombre de la era no puede estar vacío.")
            try:
                duration = int(item[1])
            except (TypeError, ValueError, IndexError):
                return Error(f"Invalid duration for era '{name}'")
            if duration < 1:
                return Error(f"Era '{name}' duration must be >= 1")
            is_last = index == len(items) - 1
            start = cursor
            end = None if is_last else start + duration - 1
            if index < len(existing):
                era = Era(
                    id=existing[index].id,
                    name=name,
                    start_year=start,
                    end_year=end,
                    order=index,
                    description=existing[index].description,
                )
            else:
                era = Era(name=name, start_year=start, end_year=end, order=index)
            new_eras.append(era)
            cursor += duration
        position = min(max(0, int(present_index)), len(new_eras) - 1)
        present_era = new_eras[position]
        year_within = max(1, int(present_year_within))
        if present_era.end_year is not None:
            span = present_era.end_year - present_era.start_year + 1
            year_within = min(year_within, span)
        present_abs = present_era.start_year + (year_within - 1)
        chrono.value.eras = new_eras
        chrono.value.present_year = present_abs
        self._touch()
        return Ok(present_abs)

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
