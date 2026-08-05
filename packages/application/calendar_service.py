"""BETA2-CAL-02 — Servicio de calendario unificado por eras encadenadas.

Única ruta de escritura del editor de calendario: configura eras CANÓNICAS (`Era`)
encadenadas por duración y el presente como (era + año dentro de la era), derivando el
`present_year` absoluto (verdad para todo el downstream). La config de meses/semana/ancla
se guarda normalizada en `metadata` a través de `ProjectChronologyService`.

Cumple "no parallel models" (las eras canónicas mandan) y "la UI nunca escribe
persistencia directamente" (todo pasa por servicios de aplicación con `Result`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.application.era_service import EraService
from packages.application.project_chronology_service import ProjectChronologyService
from packages.domain.calendar_math import CalendarConfig
from packages.domain.result import Error, Ok, Result

# Duración nominal para una era abierta cuando no hay espejo en era_lengths.
DEFAULT_OPEN_DURATION = 100


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _durations_from_payload(eras_in: Any) -> list[tuple[str, int]]:
    durations: list[tuple[str, int]] = []
    for item in eras_in or []:
        if isinstance(item, dict):
            durations.append((str(item.get("name", "") or ""), _int(item.get("duration"), 1)))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            durations.append((str(item[0] or ""), _int(item[1], 1)))
    return durations


def _months_from_payload(months_in: Any) -> list[dict[str, Any]]:
    months: list[dict[str, Any]] = []
    for item in months_in or []:
        if isinstance(item, dict):
            name = str(item.get("name", "") or "").strip()
            if name:
                months.append({"name": name, "length": max(1, _int(item.get("length"), 30))})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            name = str(item[0] or "").strip()
            if name:
                months.append({"name": name, "length": max(1, _int(item[1], 30))})
    return months


@dataclass
class CalendarService:
    """Orquesta el puente eras canónicas ↔ config de calendario."""

    project_service: Any
    era_service: EraService = field(init=False)
    chronology_service: ProjectChronologyService = field(init=False)

    def __post_init__(self) -> None:
        self.era_service = EraService(self.project_service)
        self.chronology_service = ProjectChronologyService(self.project_service)

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------

    def configure(self, payload: dict[str, Any]) -> Result[Any, str]:
        """Configura el calendario completo desde el editor unificado.

        Payload: ``{calendar_name, description, start_year, eras:[{name,duration}],
        present:{era_index, year_within, month, day}, months:[{name,length}],
        weekdays:[...], week_anchor}``.

        BETA-MULTIAGENT2-FIX-12 (G2-29): ``start_year`` (opcional, 0 por defecto) es
        el año en que empieza la PRIMERA era — el ancla de «mi historia pasa en este
        mundo». Ausente = comportamiento anterior, bit a bit.
        """
        if not isinstance(payload, dict):
            return Error("Calendar payload must be a dict")
        durations = _durations_from_payload(payload.get("eras"))
        if not durations:
            return Error("At least one era is required")
        start_year = _int(payload.get("start_year"), 0)

        present = payload.get("present") if isinstance(payload.get("present"), dict) else {}
        last = len(durations) - 1
        present_index = present.get("era_index")
        if present_index is None:
            present_index = last
        present_index = min(max(0, _int(present_index, last)), last)
        year_within = max(1, _int(present.get("year_within"), 1))

        eras_result = self.era_service.set_eras_from_durations(
            durations, present_index, year_within, start_year=start_year
        )
        if isinstance(eras_result, Error):
            return eras_result
        present_abs = eras_result.value

        months = _months_from_payload(payload.get("months"))
        weekdays = [str(w).strip() for w in (payload.get("weekdays") or []) if str(w).strip()]
        current_date = {
            "era": str(durations[present_index][0]).strip(),
            "year": year_within,
            "month": str(present.get("month", "") or ""),
            "day": max(1, _int(present.get("day"), 1)),
        }
        era_lengths = {str(name).strip(): int(duration) for name, duration in durations}
        data = {
            "calendar_name": payload.get("calendar_name", ""),
            "description": payload.get("description", ""),
            "calendar_configured": True,
            "calendar": {
                "months": months,
                "weekdays": weekdays,
                "week_anchor": _int(payload.get("week_anchor"), 0),
            },
            "current_date": current_date,
            "current_year": int(present_abs),
            "era_lengths": era_lengths,
        }
        return self.chronology_service.update(data)

    # ------------------------------------------------------------------
    # Lectura / derivación para el editor
    # ------------------------------------------------------------------

    def get_view(self) -> Result[dict[str, Any], str]:
        """Deriva el estado del editor desde las eras canónicas + metadata."""
        result = self.chronology_service.get()
        if isinstance(result, Error):
            return result
        chronology = result.value
        chronology.ensure_default_era()
        meta = dict(getattr(chronology, "metadata", {}) or {})
        era_lengths = meta.get("era_lengths") if isinstance(meta.get("era_lengths"), dict) else {}
        eras = chronology.sorted_eras()

        eras_view: list[dict[str, Any]] = []
        for era in eras:
            if era.end_year is not None:
                duration = era.end_year - era.start_year + 1
            else:
                duration = _int(era_lengths.get(era.name), 0) or DEFAULT_OPEN_DURATION
            eras_view.append(
                {"name": era.name, "duration": max(1, duration), "description": era.description}
            )

        present_abs = _int(getattr(chronology, "present_year", 0), 0)
        present_index = len(eras) - 1 if eras else 0
        year_within = 1
        target = chronology.era_for_year(present_abs)
        for index, era in enumerate(eras):
            if target is not None and era.id == target.id:
                present_index = index
                year_within = max(1, present_abs - era.start_year + 1)
                break

        cal = CalendarConfig.from_metadata(meta)
        raw_date = meta.get("current_date")
        current_date = raw_date if isinstance(raw_date, dict) else {}
        view = {
            "calendar_name": str(getattr(chronology, "calendar_name", "") or ""),
            "description": str(getattr(chronology, "description", "") or ""),
            # FIX-12 (G2-29): el ancla se DERIVA de la primera era canónica; no se
            # inventa ni se guarda aparte (sin cambio de forma en disco). Un
            # proyecto anterior al arreglo devuelve 0, que es lo que ya tenía.
            "start_year": int(eras[0].start_year) if eras else 0,
            "eras": eras_view,
            "present": {
                "era_index": present_index,
                "year_within": year_within,
                "month": str(current_date.get("month", "") or ""),
                "day": max(1, _int(current_date.get("day"), 1)),
            },
            "months": [{"name": name, "length": length} for name, length in cal.months],
            "weekdays": list(cal.weekdays),
            "week_anchor": cal.week_anchor,
        }
        return Ok(view)

    def weekday_of(
        self,
        era_index: int,
        year_within: int,
        month: str,
        day: int,
    ) -> Result[str, str]:
        """Día de la semana real de una fecha guardada (o `Error` si no aplica)."""
        result = self.chronology_service.get()
        if isinstance(result, Error):
            return result
        chronology = result.value
        eras = chronology.sorted_eras()
        if not eras:
            return Error("No hay eras definidas")
        index = min(max(0, _int(era_index, 0)), len(eras) - 1)
        era = eras[index]
        cal = CalendarConfig.from_metadata(getattr(chronology, "metadata", {}) or {})
        if not cal.supports_exact_dates():
            return Error("El calendario no tiene meses ni semana definidos")
        name = cal.weekday_name(era.start_year, _int(year_within, 1), str(month), _int(day, 1))
        if name is None:
            return Error("Fecha inválida para el cálculo del día de la semana")
        return Ok(name)


__all__ = ["CalendarService", "DEFAULT_OPEN_DURATION"]
