"""Application service for project chronology/calendar configuration (H05)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.domain.calendar_math import CalendarConfig
from packages.domain.project_chronology import ProjectChronology
from packages.domain.result import Error, Ok, Result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _named_lengths(value: Any, default_length: int) -> dict[str, int]:
    result: dict[str, int] = {}
    if isinstance(value, dict):
        for key, raw_length in value.items():
            name = str(key).strip()
            if name:
                result[name] = max(1, _int_value(raw_length, default_length))
        return result
    for line in _str_list(value):
        name = line
        length = default_length
        for separator in (":", "=", ","):
            if separator in line:
                left, right = line.split(separator, 1)
                name = left.strip()
                length = _int_value(right.strip(), default_length)
                break
        if name:
            result[name] = max(1, length)
    return result


def _current_date(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "era": str(value.get("era", "") or "").strip(),
        "year": _int_value(value.get("year"), 1),
        "month": str(value.get("month", "") or "").strip(),
        "day": _int_value(value.get("day"), 1),
    }


VAGUE_PERIODS = ["Antiguedad", "Historia reciente", "Actualidad"]
FULL_MONTHS = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]
FULL_WEEKDAYS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class ProjectChronologyService:
    """Updates project chronology through application layer routes."""

    project_service: Any

    def _project(self):
        project = getattr(self.project_service, "active_project", None)
        if project is None:
            return Error("No active project")
        return Ok(project)

    def get(self) -> Result[ProjectChronology, str]:
        project = self._project()
        if isinstance(project, Error):
            return project
        chronology = getattr(project.value, "project_chronology", None)
        if chronology is None:
            chronology = ProjectChronology()
            project.value.project_chronology = chronology
        return Ok(chronology)

    def update(self, data: dict[str, Any]) -> Result[ProjectChronology, str]:
        current = self.get()
        if isinstance(current, Error):
            return current
        chronology = current.value
        metadata = dict(getattr(chronology, "metadata", {}) or {})
        incoming_meta = data.get("metadata")
        if isinstance(incoming_meta, dict):
            metadata.update(incoming_meta)

        # BETA2-CAL: la ruta unificada (CalendarService) escribe eras canónicas por
        # separado; aquí solo normaliza la config de meses/semana/ancla sin el clobber
        # legacy de era_lengths/current_date. El resto de rutas (apply_candidate/IA/tests
        # H05/H07) sigue por el camino legacy de los tres modos.
        if data.get("calendar_configured"):
            mode = self._apply_unified_calendar(metadata, data)
        else:
            mode = self._apply_legacy_calendar(metadata, data)

        chronology.calendar_name = str(data.get("calendar_name", chronology.calendar_name) or "").strip()
        chronology.description = str(data.get("description", chronology.description) or "").strip()
        chronology.calendar_system = str(data.get("calendar_system", mode) or mode).strip()
        chronology.metadata = metadata
        now = _now_iso()
        if not chronology.created_at:
            chronology.created_at = now
        chronology.updated_at = now

        project = self._project()
        if isinstance(project, Error):
            return project
        if hasattr(project.value, "touch"):
            project.value.touch()
        return Ok(chronology)

    def _apply_unified_calendar(self, metadata: dict[str, Any], data: dict[str, Any]) -> str:
        """Ruta unificada (BETA2-CAL): ``mode`` DERIVADO de si hay meses+semana.

        No aplica el clobber legacy: respeta ``era_lengths``/``current_date`` que envía el
        servicio (espejo de las eras canónicas). Normaliza la config de meses/semana/ancla
        bajo ``metadata['calendar']`` y mantiene los espejos que consumen el picker y la
        vista cronológica.
        """
        cal = CalendarConfig.from_metadata(data)
        has_exact = cal.supports_exact_dates()
        mode = "full_calendar" if has_exact else "vague_periods"
        months = cal.month_names()
        month_lengths = {name: length for name, length in cal.months}
        if months:
            months_per_year = max(1, len(months))
        else:
            months_per_year = max(1, _int_value(metadata.get("months_per_year"), 1))
        if "era_lengths" in data:
            era_lengths = _named_lengths(data.get("era_lengths"), 100)
        else:
            era_lengths = dict(metadata.get("era_lengths") or {})
        if "current_date" in data:
            current_date = _current_date(data.get("current_date"))
        else:
            current_date = _current_date(metadata.get("current_date"))
        prev_year = _int_value(metadata.get("current_year"), 1)
        current_year = _int_value(data.get("current_year"), prev_year)
        default_days = min(month_lengths.values()) if month_lengths else 30
        metadata.update({
            "mode": mode,
            "calendar_kind": mode,
            "calendar_configured": True,
            "calendar": cal.to_metadata(),
            "months": list(months),
            "month_lengths": month_lengths,
            "weekdays": list(cal.weekdays),
            "week_anchor": cal.week_anchor,
            "era_lengths": era_lengths,
            "past_eras": list(era_lengths.keys()),
            "eras": list(era_lengths.keys()),
            "current_date": current_date,
            "current_year": current_year,
            "days_per_month": max(1, _int_value(data.get("days_per_month"), default_days)),
            "months_per_year": months_per_year,
            "units": ["era", "ano", "mes", "dia"] if has_exact else ["era", "ano"],
            "supports_exact_dates": has_exact,
            "date_resolution": "dia" if has_exact else "ano",
            "display_format": "{era} {year}, {month} {day}" if has_exact else "{era} {year}",
        })
        return mode

    def _apply_legacy_calendar(self, metadata: dict[str, Any], data: dict[str, Any]) -> str:
        """Ruta legacy de los tres modos (none/vague_periods/full_calendar)."""
        mode = str(data.get("mode", metadata.get("mode", "")) or "none").strip()
        if mode not in {"none", "vague_periods", "full_calendar"}:
            legacy = {
                "relative": "vague_periods",
                "narrative": "vague_periods",
                "custom_calendar": "full_calendar",
            }
            mode = legacy.get(mode, "none")
        metadata["mode"] = mode
        metadata["calendar_kind"] = mode
        for key in ("eras", "periods", "cycles", "units"):
            if key in data:
                metadata[key] = _str_list(data.get(key))
        for key in ("months", "weekdays", "past_eras"):
            if key in data:
                metadata[key] = _str_list(data.get(key))
        if "month_lengths" in data:
            metadata["month_lengths"] = _named_lengths(data.get("month_lengths"), _int_value(data.get("days_per_month"), 30))
        if "era_lengths" in data:
            metadata["era_lengths"] = _named_lengths(data.get("era_lengths"), 100)
        if "current_date" in data:
            metadata["current_date"] = _current_date(data.get("current_date"))
        for key in ("display_format", "date_resolution"):
            if key in data:
                metadata[key] = str(data.get(key, "") or "").strip()
        if "supports_exact_dates" in data:
            metadata["supports_exact_dates"] = bool(data.get("supports_exact_dates"))
        if "days_per_month" in data:
            metadata["days_per_month"] = max(1, _int_value(data.get("days_per_month"), 30))
        if "months_per_year" in data:
            metadata["months_per_year"] = max(1, _int_value(data.get("months_per_year"), len(metadata.get("months") or FULL_MONTHS)))
        if "current_year" in data:
            metadata["current_year"] = _int_value(data.get("current_year"), 1)
        if mode == "none":
            metadata.update({
                "periods": [],
                "eras": [],
                "past_eras": [],
                "months": [],
                "month_lengths": {},
                "era_lengths": {},
                "current_date": {},
                "weekdays": [],
                "units": [],
                "supports_exact_dates": False,
                "date_resolution": "",
                "display_format": "",
            })
        elif mode == "vague_periods":
            periods = metadata.get("periods") or metadata.get("eras") or VAGUE_PERIODS
            metadata.update({
                "periods": list(periods),
                "eras": list(periods),
                "era_lengths": {str(period): 1 for period in periods},
                "units": ["periodo narrativo"],
                "supports_exact_dates": False,
                "date_resolution": "periodo",
                "display_format": "{periodo}",
            })
        elif mode == "full_calendar":
            months = metadata.get("months") or FULL_MONTHS
            weekdays = metadata.get("weekdays") or FULL_WEEKDAYS
            eras = metadata.get("past_eras") or metadata.get("eras") or []
            month_lengths = dict(metadata.get("month_lengths") or {})
            for month in months:
                month_lengths.setdefault(str(month), max(1, _int_value(metadata.get("days_per_month"), 30)))
            era_lengths = dict(metadata.get("era_lengths") or {})
            for era in eras:
                era_lengths.setdefault(str(era), 100)
            current_date = _current_date(metadata.get("current_date"))
            if not current_date:
                current_date = {
                    "era": str(eras[-1] if eras else "Actualidad"),
                    "year": _int_value(metadata.get("current_year"), 1),
                    "month": str(months[0] if months else ""),
                    "day": 1,
                }
            metadata.update({
                "months": list(months),
                "weekdays": list(weekdays),
                "past_eras": list(eras),
                "eras": list(eras),
                "month_lengths": month_lengths,
                "era_lengths": era_lengths,
                "current_date": current_date,
                "units": ["era", "ano", "mes", "dia"],
                "months_per_year": max(1, _int_value(metadata.get("months_per_year"), len(months))),
                "days_per_month": max(1, _int_value(metadata.get("days_per_month"), 30)),
                "current_year": _int_value(metadata.get("current_year"), 1),
                "supports_exact_dates": True,
                "date_resolution": metadata.get("date_resolution") or "dia",
                "display_format": metadata.get("display_format") or "{era} {year}, {month} {day}",
            })
        return mode

    def apply_candidate(self, proposal: dict[str, Any]) -> Result[ProjectChronology, str]:
        """Apply a reviewed chronology proposal after explicit user acceptance."""

        if not isinstance(proposal, dict):
            return Error("Chronology proposal must be a JSON object")
        kind = str(proposal.get("kind", "") or "")
        if kind and kind != "project_chronology_suggestion":
            return Error("Candidate is not a project chronology suggestion")
        mode = str(proposal.get("mode", "") or "vague_periods")
        mode = {
            "relative": "vague_periods",
            "narrative": "vague_periods",
            "custom_calendar": "full_calendar",
        }.get(mode, mode)
        supports_exact = bool(proposal.get("supports_exact_dates", False))
        if mode == "full_calendar" and not supports_exact:
            return Error("Full calendar proposals must support exact dates")
        data = {
            "calendar_name": proposal.get("title") or proposal.get("calendar_name") or "",
            "description": proposal.get("summary") or proposal.get("description") or "",
            "calendar_system": mode,
            "mode": mode,
            "eras": proposal.get("eras") or [],
            "past_eras": proposal.get("past_eras") or proposal.get("eras") or [],
            "era_lengths": proposal.get("era_lengths") or {},
            "periods": proposal.get("periods") or [],
            "cycles": proposal.get("cycles") or [],
            "units": proposal.get("units") or [],
            "months": proposal.get("months") or [],
            "month_lengths": proposal.get("month_lengths") or {},
            "weekdays": proposal.get("weekdays") or [],
            "current_date": proposal.get("current_date") or {},
            "display_format": proposal.get("display_format") or "",
            "date_resolution": proposal.get("date_resolution") or "",
            "supports_exact_dates": supports_exact,
            "metadata": {
                "rationale": proposal.get("rationale") or "",
                "risks": proposal.get("risks") or [],
                "questions_for_user": proposal.get("questions_for_user") or [],
                "accepted_from_candidate": True,
            },
        }
        return self.update(data)
