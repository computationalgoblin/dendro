"""HistoryService — centralized history recording (B25-T00).

Uses the existing Project.history collection (domain.source_history.HistoryEntry)
and keeps a history_entries alias for B25 compatibility without creating a
second persistence collection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.domain.result import Ok
from packages.domain.source_history import HistoryEntry, HistoryEventType


@dataclass
class HistoryService:
    project_service: Any

    def _proj(self):
        return self.project_service.active_project

    def _ensure_history(self) -> list[HistoryEntry]:
        proj = self._proj()
        if not hasattr(proj, "history") or not isinstance(proj.history, list):
            proj.history = []
        # Compatibility with B25 callers/tests: expose history_entries as an
        # alias, not a second source of truth.
        if not hasattr(proj, "history_entries") or proj.history_entries is not proj.history:
            proj.history_entries = proj.history
        return proj.history

    def make_entry(
        self,
        event_type: HistoryEventType | str,
        affected_entity_id: str | None = None,
        affected_relation_id: str | None = None,
        affected_source_id: str | None = None,
        previous_value: Any | None = None,
        new_value: Any | None = None,
        change_origin: str | None = None,
        operation: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> HistoryEntry:
        """Create, but do not record, a domain HistoryEntry.

        EntityService/RelationService build an entry with this method and then
        call record(entry). Keeping creation separate prevents duplicate writes.
        """
        parsed_event = self._event_type(event_type)
        return HistoryEntry(
            event_type=parsed_event,
            affected_entity_id=affected_entity_id,
            affected_relation_id=affected_relation_id,
            affected_source_id=affected_source_id,
            previous_value=previous_value,
            new_value=new_value,
            change_origin=change_origin or "",
            operation=operation or "",
            reason=description or "",
            metadata=self._with_declared_event(metadata, event_type, parsed_event),
        )

    def record(
        self,
        event_type: HistoryEntry | dict[str, Any] | HistoryEventType | str | None = None,
        description: str | None = None,
        affected_entity_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> HistoryEntry:
        """Record a history entry.

        Supported call shapes:
        - record(HistoryEntry)
        - record(dict from HistoryEntry.to_dict() or legacy make_entry dict)
        - record("event", "description", affected_entity_ids=[...], metadata={...})
        """
        if isinstance(event_type, HistoryEntry):
            entry = event_type
        elif isinstance(event_type, dict):
            entry = self._entry_from_dict(event_type)
        else:
            entity_ids = affected_entity_ids or kwargs.get("affected_entity_ids") or []
            declared = event_type or "creacion_entidad"
            parsed = self._event_type(declared)
            entry = HistoryEntry(
                event_type=parsed,
                affected_entity_id=entity_ids[0] if entity_ids else kwargs.get("affected_entity_id"),
                affected_relation_id=kwargs.get("affected_relation_id"),
                affected_source_id=kwargs.get("affected_source_id"),
                previous_value=kwargs.get("previous_value"),
                new_value=kwargs.get("new_value"),
                change_origin=kwargs.get("change_origin", ""),
                reason=description or kwargs.get("reason", ""),
                operation=kwargs.get("operation", ""),
                metadata=self._with_declared_event(
                    metadata or kwargs.get("metadata", {}) or {}, declared, parsed
                ),
            )
        self._ensure_history().append(entry)
        proj = self._proj()
        if hasattr(proj, "touch"):
            proj.touch()
        return entry

    def add_entry(
        self,
        data: HistoryEntry | dict[str, Any] | HistoryEventType | str | None = None,
        description: str | None = None,
        **kwargs: Any,
    ) -> HistoryEntry:
        """Alias REAL de :meth:`record` (BETA2-FIX-08, G2-14/B3).

        ``add_entry`` tenía cuatro llamadores y CERO implementaciones
        (``candidate_service``, ``causal_milestone_service``,
        ``orchestrator_service`` ×2): el ``AttributeError`` se lo tragaban sus
        ``except Exception`` / ``hasattr`` y el historial quedaba mudo sin que
        nadie se enterase. Existe para que esas llamadas graben de verdad.
        """
        return self.record(data, description, **kwargs)

    @staticmethod
    def _with_declared_event(
        metadata: dict[str, Any] | None,
        declared: Any,
        parsed: HistoryEventType,
    ) -> dict[str, Any]:
        """Deja CONSTANCIA del evento declarado cuando no existe en el enum.

        ``_event_type`` degrada lo desconocido a ``CREACION_ENTIDAD``; sin esta
        nota, una cadena mal escrita se convertía en una traza falsa y silenciosa
        (BETA2-FIX-08). Ahora el valor original viaja en metadata.
        """
        meta = dict(metadata or {})
        if isinstance(declared, HistoryEventType) or declared is None:
            return meta
        raw = str(declared)
        if raw and raw != parsed.value:
            meta["event_type_declarado"] = raw
        return meta

    def get_history(
        self,
        entity_id: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        session_id: str | None = None,
        event_type: HistoryEventType | str | None = None,
        limit: int = 50,
    ) -> list[HistoryEntry]:
        target_event = self._event_type(event_type) if event_type else None
        entries: list[HistoryEntry] = []
        for entry in reversed(self._ensure_history()):
            if entity_id and entry.affected_entity_id != entity_id:
                continue
            if object_type and entry.metadata.get("object_type") != object_type:
                continue
            if object_id and entry.metadata.get("object_id") != object_id:
                continue
            if session_id and entry.metadata.get("session_id") != session_id:
                continue
            if target_event and entry.event_type != target_event:
                continue
            entries.append(entry)
            if len(entries) >= limit:
                break
        return entries

    def get_for_entity(self, entity_id: str, limit: int = 50):
        return Ok(list(reversed(self.get_history(entity_id=entity_id, limit=limit))))

    def get_recent(self, limit: int = 50):
        return Ok(self.get_history(limit=limit))

    def _event_type(self, value: HistoryEventType | str) -> HistoryEventType:
        if isinstance(value, HistoryEventType):
            return value
        try:
            return HistoryEventType(str(value))
        except ValueError:
            # Preserve compatibility with newer object-level events not present
            # in the original enum by storing them in metadata-like text through
            # the closest generic event. Existing QA asserts enum events only.
            return HistoryEventType.CREACION_ENTIDAD

    def _entry_from_dict(self, data: dict[str, Any]) -> HistoryEntry:
        if any(key in data for key in ("affected_entity_id", "affected_relation_id", "previous_value", "new_value")):
            return HistoryEntry.from_dict(data)
        affected = data.get("affected_entity_ids") or []
        return self.make_entry(
            data.get("event_type", HistoryEventType.CREACION_ENTIDAD),
            affected_entity_id=affected[0] if affected else None,
            description=data.get("description", ""),
            metadata=data.get("metadata", {}) or {},
        )
