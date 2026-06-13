"""Project chronology domain model.

The project chronology is the project-level temporal container for milestones.
It references canonical milestone ids, but it does not turn milestones into
graph nodes or narrative entities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProjectChronology:
    """Project-owned chronology/calendar metadata for milestone views."""

    id: str = "project_chronology"
    calendar_name: str = ""
    description: str = ""
    calendar_system: str = "project"
    milestone_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

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
        )


def _parse_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _parse_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


__all__ = ["ProjectChronology"]
