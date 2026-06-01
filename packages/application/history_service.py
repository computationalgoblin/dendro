"""HistoryService — centralized history recording (B25-T00). No schema bump. Uses existing project history structure."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from packages.domain.result import Error, Ok, Result

def _ts(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass
class HistoryEntry:
    timestamp: str
    event_type: str
    description: str
    affected_entity_ids: list[str]
    metadata: dict[str, Any]

    def to_dict(self): return {"timestamp": self.timestamp, "event_type": self.event_type, "description": self.description, "affected_entity_ids": self.affected_entity_ids, "metadata": self.metadata}
    @classmethod
    def from_dict(cls, d): return cls(timestamp=d.get("timestamp",""), event_type=d.get("event_type",""), description=d.get("description",""), affected_entity_ids=d.get("affected_entity_ids",[]), metadata=d.get("metadata",{}))

@dataclass
class HistoryService:
    project_service: Any

    def _proj(self): return self.project_service.active_project

    def _ensure_history(self):
        proj = self._proj()
        if not hasattr(proj, 'history_entries') or not isinstance(proj.history_entries, list):
            proj.history_entries = []
        return proj.history_entries

    def record(self, event_type, description, affected_entity_ids=None, metadata=None):
        entry = HistoryEntry(timestamp=_ts(), event_type=event_type, description=description,
                            affected_entity_ids=affected_entity_ids or [], metadata=metadata or {})
        self._ensure_history().append(entry)
        self._proj().touch()
        return entry

    def get_for_entity(self, entity_id):
        return self.get_history(entity_id=entity_id)

    def get_history(self, entity_id=None, object_type=None, object_id=None, session_id=None, event_type=None, limit=50):
        entries = []
        for e in reversed(self._ensure_history()):
            if entity_id and entity_id not in e.affected_entity_ids: continue
            if object_type and e.metadata.get("object_type") != object_type: continue
            if object_id and e.metadata.get("object_id") != object_id: continue
            if event_type and e.event_type != event_type: continue
            entries.append(e)
            if len(entries) >= limit: break
        return entries
