"""
History service — application-layer audit trail.

Provides ``HistoryService`` for recording traceability events.
Integration with EntityService and RelationService is optional:
pass ``history_service`` to any mutating method and a
``HistoryEntry`` will be appended on success.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.domain.result import Error, Ok, Result
from packages.domain.source_history import HistoryEntry, HistoryEventType


@dataclass
class HistoryService:
    """Records audit events in the active project.

    Injected into EntityService and RelationService as an optional
    parameter.  When present, each successful mutation produces a
    ``HistoryEntry``.  When absent (None), existing behaviour is
    unchanged.
    """

    project_service: Any  # ProjectService

    def _active_project(self):
        ps = self.project_service
        if ps.active_project is None:
            return Error("No active project")
        return Ok(ps.active_project)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, entry: HistoryEntry) -> Result[None, str]:
        """Append a HistoryEntry to the active project."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        proj.value.history.append(entry)
        return Ok(None)

    @staticmethod
    def make_entry(
        event_type: HistoryEventType,
        affected_entity_id: str | None = None,
        affected_relation_id: str | None = None,
        affected_source_id: str | None = None,
        previous_value: Any | None = None,
        new_value: Any | None = None,
        change_origin: str = "",
        reason: str = "",
        operation: str = "",
    ) -> HistoryEntry:
        """Factory for a HistoryEntry with mandatory fields."""
        return HistoryEntry(
            event_type=event_type,
            affected_entity_id=affected_entity_id,
            affected_relation_id=affected_relation_id,
            affected_source_id=affected_source_id,
            previous_value=previous_value,
            new_value=new_value,
            change_origin=change_origin,
            reason=reason,
            operation=operation,
        )

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_for_entity(self, entity_id: str) -> Result[list[HistoryEntry], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([h for h in proj.value.history if h.affected_entity_id == entity_id])

    def get_for_relation(self, relation_id: str) -> Result[list[HistoryEntry], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([h for h in proj.value.history if h.affected_relation_id == relation_id])

    def get_recent(self, limit: int = 20) -> Result[list[HistoryEntry], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        sorted_entries = sorted(
            proj.value.history, key=lambda h: h.timestamp, reverse=True
        )
        return Ok(sorted_entries[:limit])


__all__ = ["HistoryService"]
