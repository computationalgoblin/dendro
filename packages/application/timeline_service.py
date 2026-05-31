"""TimelineService — CRUD, ordering, temporal consistency (B18-T02)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from packages.domain.temporal_models import (
    EventTemporality, TimelineEvent, TemporalPrecision, TemporalRelation,
)
from packages.domain.candidate_issue import StructuredIssue
from packages.domain.result import Error, Ok, Result


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TimelineService:
    def __init__(self, project_service: Any, issue_service: Any = None):
        self._ps = project_service
        self._is = issue_service

    def _proj(self):
        p = self._ps.active_project
        if p is None:
            return Error("No active project")
        return Ok(p)

    def create_event(self, data: dict) -> Result[TimelineEvent, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        temporality = EventTemporality.from_dict(data.get("temporality", {}))
        event = TimelineEvent(
            name=data.get("name", ""), description=data.get("description", ""),
            entity_id=data.get("entity_id"), temporality=temporality,
            created_at=_now_iso(), updated_at=_now_iso(),
        )
        proj.value.timeline_events.append(event)
        return Ok(event)

    def get_event(self, eid: str) -> Result[TimelineEvent, str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        for e in proj.value.timeline_events:
            if e.id == eid:
                return Ok(e)
        return Error(f"TimelineEvent '{eid[:8]}' not found")

    def list_events(self, filters: dict | None = None) -> Result[list[TimelineEvent], str]:
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        result = list(proj.value.timeline_events)
        if filters:
            if filters.get("domain_id"):
                result = [e for e in result if filters["domain_id"] in e.domain_ids]
            if filters.get("layer_id"):
                result = [e for e in result if filters["layer_id"] in e.layer_ids]
            if filters.get("entity_id"):
                result = [e for e in result if filters["entity_id"] in e.participant_ids]
            if filters.get("canon_state"):
                result = [e for e in result if e.canon_state == filters["canon_state"]]
        return Ok(result)

    def get_ordered_events(self, filters: dict | None = None) -> Result[list[TimelineEvent], str]:
        revents = self.list_events(filters)
        if isinstance(revents, Error):
            return revents
        events = revents.value
        # Sort: absolute_date ASC (None last), then by name
        def sort_key(e):
            d = e.temporality.absolute_date
            return (0, d or "zzzzzz", e.name) if d else (1, "", e.name)
        events.sort(key=sort_key)
        return Ok(events)

    def update_event(self, eid: str, data: dict) -> Result[TimelineEvent, str]:
        re = self.get_event(eid)
        if isinstance(re, Error):
            return re
        e = re.value
        if "name" in data: e.name = data["name"]
        if "description" in data: e.description = data["description"]
        if "temporality" in data and data["temporality"]:
            e.temporality = EventTemporality.from_dict(data["temporality"])
        e.updated_at = _now_iso()
        return Ok(e)

    def add_participant(self, event_id: str, entity_id: str) -> Result[TimelineEvent, str]:
        re = self.get_event(event_id)
        if isinstance(re, Error):
            return re
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        if not any(en.id == entity_id for en in proj.value.entities):
            return Error(f"Entity '{entity_id[:8]}' not found")
        if entity_id not in re.value.participant_ids:
            re.value.participant_ids.append(entity_id)
        return Ok(re.value)

    def add_location(self, event_id: str, location_id: str) -> Result[TimelineEvent, str]:
        re = self.get_event(event_id)
        if isinstance(re, Error):
            return re
        proj = self._proj()
        if isinstance(proj, Error):
            return proj
        if not any(en.id == location_id for en in proj.value.entities):
            return Error(f"Entity '{location_id[:8]}' not found")
        re.value.location_id = location_id
        return Ok(re.value)

    def add_cause(self, event_id: str, cause_id: str) -> Result[TimelineEvent, str]:
        if event_id == cause_id:
            return Error("Cannot add self as cause")
        re = self.get_event(event_id)
        if isinstance(re, Error):
            return re
        rc = self.get_event(cause_id)
        if isinstance(rc, Error):
            return rc
        if cause_id not in re.value.cause_ids:
            re.value.cause_ids.append(cause_id)
        if event_id not in rc.value.consequence_ids:
            rc.value.consequence_ids.append(event_id)
        return Ok(re.value)

    def add_consequence(self, event_id: str, consequence_id: str) -> Result[TimelineEvent, str]:
        if event_id == consequence_id:
            return Error("Cannot add self as consequence")
        re = self.get_event(event_id)
        if isinstance(re, Error):
            return re
        rc = self.get_event(consequence_id)
        if isinstance(rc, Error):
            return rc
        if consequence_id not in re.value.consequence_ids:
            re.value.consequence_ids.append(consequence_id)
        if event_id not in rc.value.cause_ids:
            rc.value.cause_ids.append(event_id)
        return Ok(re.value)

    def detect_temporal_inconsistencies(self) -> list[StructuredIssue]:
        proj_r = self._proj()
        if isinstance(proj_r, Error):
            return []
        proj = proj_r.value
        issues = []
        events = proj.timeline_events
        eids = {e.id for e in events}

        for e in events:
            # Broken references
            for cid in e.cause_ids:
                if cid not in eids:
                    issues.append(StructuredIssue(
                        description=f"Event '{e.name}' references non-existent cause '{cid[:8]}'",
                        affected_entity_ids=[e.id], source="deterministic",
                        metadata={"validator": "timeline", "timeline_event_id": e.id},
                    ))
            for cid in e.consequence_ids:
                if cid not in eids:
                    issues.append(StructuredIssue(
                        description=f"Event '{e.name}' references non-existent consequence '{cid[:8]}'",
                        affected_entity_ids=[e.id], source="deterministic",
                        metadata={"validator": "timeline", "timeline_event_id": e.id},
                    ))
            # Participants not existing
            for pid in e.participant_ids:
                if not any(en.id == pid for en in proj.entities):
                    issues.append(StructuredIssue(
                        description=f"Event '{e.name}' references non-existent participant '{pid[:8]}'",
                        affected_entity_ids=[e.id], source="deterministic",
                        metadata={"validator": "timeline", "timeline_event_id": e.id},
                    ))
            # Circular cause/consequence
            if e.id in e.cause_ids:
                issues.append(StructuredIssue(
                    description=f"Event '{e.name}' has self as cause",
                    affected_entity_ids=[e.id], source="deterministic",
                    metadata={"validator": "timeline", "timeline_event_id": e.id},
                ))

        return issues


__all__ = ["TimelineService"]
