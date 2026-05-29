"""
Source service — application-layer lifecycle for traceable origins.

Provides ``SourceService``, a stateful service that manages ``Source``
objects within the active project.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packages.domain.entity import NarrativeEntity
from packages.domain.result import Error, Ok, Result
from packages.domain.source_history import Source, SourceType
from packages.persistence.store import ProjectStore


@dataclass
class SourceService:
    project_service: Any  # ProjectService
    store: ProjectStore = field(default_factory=ProjectStore)
    _current_path: Path | None = None

    def _active_project(self):
        ps = self.project_service
        if ps.active_project is None:
            return Error("No active project")
        return Ok(ps.active_project)

    def create_source(self, data: dict[str, Any]) -> Result[Source, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        name = str(data.get("name", "")).strip()
        if not name:
            return Error("Source name cannot be empty")

        source = Source.from_dict(data)
        source.name = name
        proj.value.sources.append(source)
        proj.value.touch()
        return Ok(source)

    def get_by_id(self, source_id: str) -> Result[Source, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        for s in proj.value.sources:
            if s.id == source_id:
                return Ok(s)
        return Error(f"Source with id '{source_id}' not found")

    def link_to_entity(self, source_id: str, entity_id: str) -> Result[None, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        source = None
        for s in proj.value.sources:
            if s.id == source_id:
                source = s
                break
        if source is None:
            return Error(f"Source with id '{source_id}' not found")

        entity_exists = any(e.id == entity_id for e in proj.value.entities)
        if not entity_exists:
            return Error(f"Entity with id '{entity_id}' not found")

        if entity_id not in source.derived_entity_ids:
            source.derived_entity_ids.append(entity_id)
        proj.value.touch()
        return Ok(None)

    def link_to_relation(self, source_id: str, relation_id: str) -> Result[None, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        source = None
        for s in proj.value.sources:
            if s.id == source_id:
                source = s
                break
        if source is None:
            return Error(f"Source with id '{source_id}' not found")

        relation_exists = any(r.id == relation_id for r in proj.value.relations)
        if not relation_exists:
            return Error(f"Relation with id '{relation_id}' not found")

        if relation_id not in source.derived_relation_ids:
            source.derived_relation_ids.append(relation_id)
        proj.value.touch()
        return Ok(None)

    def get_sources_for_entity(self, entity_id: str) -> Result[list[Source], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([s for s in proj.value.sources if entity_id in s.derived_entity_ids])

    def get_sources_for_relation(self, relation_id: str) -> Result[list[Source], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([s for s in proj.value.sources if relation_id in s.derived_relation_ids])

    def get_entities_from_source(self, source_id: str) -> Result[list[NarrativeEntity], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        source = None
        for s in proj.value.sources:
            if s.id == source_id:
                source = s
                break
        if source is None:
            return Error(f"Source with id '{source_id}' not found")
        entities = [e for e in proj.value.entities if e.id in source.derived_entity_ids]
        return Ok(entities)

    def list_all(self) -> Result[list[Source], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok(list(proj.value.sources))
