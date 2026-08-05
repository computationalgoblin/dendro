"""Project chronology domain model.

The project chronology is the project-level temporal container for milestones.
It references canonical milestone ids, but it does not turn milestones into
graph nodes or narrative entities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.domain.era import Era


@dataclass
class ProjectChronology:
    """Project-owned chronology/calendar metadata for milestone views.

    BETA1-G02: además del registro de hitos, es el CALENDARIO del proyecto —
    contiene las eras y el año presente. Toda entidad pertenece a una era
    derivadamente (la que contiene su birth_year): no hay atemporalidad.
    """

    id: str = "project_chronology"
    calendar_name: str = ""
    description: str = ""
    calendar_system: str = "project"
    milestone_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    # BETA1-G02: tiempo del mundo
    eras: list[Era] = field(default_factory=list)
    present_year: int = 0

    # ── BETA1-G02: helpers temporales ───────────────────────────────────

    def ensure_default_era(self) -> Era:
        """Garantiza al menos una era (la abierta 'Presente'). Idempotente."""
        if not self.eras:
            self.eras.append(Era(name="Presente", start_year=self.present_year, end_year=None, order=0))
        return self.eras[-1]

    def era_for_year(self, year: int) -> Era | None:
        """Era que contiene *year* (la más específica si hubiera solape)."""
        candidates = [era for era in self.eras if era.contains(year)]
        if not candidates:
            return None
        # La de inicio más tardío gana (más específica)
        return max(candidates, key=lambda era: era.start_year)

    def sorted_eras(self) -> list[Era]:
        return sorted(self.eras, key=lambda era: (era.start_year, era.order))

    def year_label(self, year: int | None) -> str:
        """«año N (Era X, año M)» — puente año absoluto ↔ era (BETA-MULTIAGENT-FIX-03).

        Los prompts recibían año absoluto y año-de-era sin traducción y la IA
        alegaba incoherencias temporales falsas. Sin año → «sin fecha»; año fuera
        de toda era → «año N» pelado (degradación sin crash).
        """
        if year is None:
            return "sin fecha"
        y = int(year)
        era = self.era_for_year(y)
        if era is None or getattr(era, "start_year", None) is None:
            return f"año {y}"
        within = max(1, y - int(era.start_year) + 1)
        return f"año {y} ({era.name}, año {within})"

    def link_milestone(self, milestone_id: str) -> None:
        normalized = str(milestone_id).strip()
        if normalized and normalized not in self.milestone_ids:
            self.milestone_ids.append(normalized)

    def unlink_milestone(self, milestone_id: str) -> None:
        normalized = str(milestone_id).strip()
        self.milestone_ids = [mid for mid in self.milestone_ids if mid != normalized]

    def includes_milestone(self, milestone_id: str) -> bool:
        return str(milestone_id).strip() in self.milestone_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "calendar_name": self.calendar_name,
            "description": self.description,
            "calendar_system": self.calendar_system,
            "milestone_ids": list(self.milestone_ids),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "eras": [era.to_dict() for era in self.eras],
            "present_year": int(self.present_year),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectChronology:
        if not isinstance(data, dict):
            data = {}
        raw_id = data.get("id")
        return cls(
            id=raw_id if isinstance(raw_id, str) and raw_id.strip() else "project_chronology",
            calendar_name=str(data.get("calendar_name", "")),
            description=str(data.get("description", "")),
            calendar_system=str(data.get("calendar_system", "project") or "project"),
            milestone_ids=_parse_str_list(data.get("milestone_ids")),
            metadata=_parse_dict(data.get("metadata")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            eras=_parse_eras(data.get("eras")),
            present_year=_parse_int(data.get("present_year"), 0),
        )


def format_year_with_era(chronology: "ProjectChronology | None", year: int | None) -> str:
    """Helper ÚNICO del puente temporal para los serializadores de prompts.

    Tolera cronología ausente (proyectos sin calendario): devuelve el año pelado.
    """
    if year is None:
        return "sin fecha"
    if chronology is None:
        return f"año {int(year)}"
    return chronology.year_label(year)


def _parse_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _parse_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _parse_eras(value: Any) -> list[Era]:
    if isinstance(value, list):
        return [Era.from_dict(item) for item in value if isinstance(item, dict)]
    return []


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = ["ProjectChronology"]
