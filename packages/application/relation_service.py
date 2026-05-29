"""
Relation service — application-layer lifecycle for narrative relations.

Provides ``RelationService``, a stateful service that orchestrates CRUD
operations on ``NarrativeRelation`` objects within the active project,
using domain filters and the persistence layer.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packages.domain.entity import CanonState, VisibilityState
from packages.domain.relation import (
    NarrativeRelation,
    RelationType,
    validate_relation,
)
from packages.domain.result import Error, Ok, Result
from packages.persistence.store import ProjectStore


@dataclass
class RelationService:
    """Application service for NarrativeRelation lifecycle.

    All mutating methods modify ``project.relations`` in memory.
    Persistence occurs when the caller explicitly calls
    ``project_service.save()`` — following the pattern established
    in Bloque 3 (EntityService).

    Attributes:
        project_service: The active ``ProjectService`` (stateful).
        store: The ``ProjectStore``.
        _current_path: Path used for persistence.
    """

    project_service: Any  # ProjectService
    store: ProjectStore = field(default_factory=ProjectStore)
    _current_path: Path | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_project(self):
        ps = self.project_service
        if ps.active_project is None:
            return Error("No active project")
        return Ok(ps.active_project)

    def _entity_exists(self, entity_id: str) -> bool:
        proj = self._active_project()
        if isinstance(proj, Error):
            return False
        return any(e.id == entity_id for e in proj.value.entities)

    def _find_entity(self, entity_id: str):
        proj = self._active_project()
        if isinstance(proj, Error):
            return None
        for e in proj.value.entities:
            if e.id == entity_id:
                return e
        return None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_relation(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: RelationType | str | None = None,
        data: dict[str, Any] | None = None,
    ) -> Result[NarrativeRelation, str]:
        """Create a new relation and add it to the active project.

        Validates referential integrity: source and target must exist.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        src = source_id or (data or {}).get("source_id", "")
        tgt = target_id or (data or {}).get("target_id", "")

        if not src or not tgt:
            return Error("source_id and target_id are required")

        if not self._entity_exists(src):
            return Error(f"Source entity '{src}' does not exist")
        if not self._entity_exists(tgt):
            return Error(f"Target entity '{tgt}' does not exist")

        rtype = relation_type
        if isinstance(rtype, str):
            try:
                rtype = RelationType(rtype)
            except ValueError:
                rtype = RelationType.ESTA_RELACIONADO_CON
        if rtype is None:
            rtype = (data or {}).get("relation_type", RelationType.ESTA_RELACIONADO_CON)
            if isinstance(rtype, str):
                try:
                    rtype = RelationType(rtype)
                except ValueError:
                    rtype = RelationType.ESTA_RELACIONADO_CON

        relation = NarrativeRelation(
            source_id=src,
            target_id=tgt,
            relation_type=rtype,
        )

        if data:
            for key in ("description", "temporality", "causality", "conditions", "source"):
                if key in data:
                    setattr(relation, key, data[key])
            if "custom_metadata" in data and isinstance(data["custom_metadata"], dict):
                relation.custom_metadata.update(data["custom_metadata"])

        issues = validate_relation(relation)
        if issues:
            return Error(f"Relation validation failed: {'; '.join(issues)}")

        proj.value.relations.append(relation)
        proj.value.touch()
        return Ok(relation)

    def update_relation(
        self, relation_id: str, data: dict[str, Any]
    ) -> Result[NarrativeRelation, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for r in proj.value.relations:
            if r.id == relation_id:
                for key in ("description", "temporality", "causality",
                             "conditions", "source"):
                    if key in data:
                        setattr(r, key, data[key])
                if "custom_metadata" in data and isinstance(data["custom_metadata"], dict):
                    r.custom_metadata.update(data["custom_metadata"])
                r.touch()
                proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def archive_relation(self, relation_id: str) -> Result[None, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        for r in proj.value.relations:
            if r.id == relation_id:
                r.canon_state = CanonState.ARCHIVADO
                r.touch()
                proj.value.touch()
                return Ok(None)
        return Error(f"Relation with id '{relation_id}' not found")

    def restore_relation(self, relation_id: str) -> Result[NarrativeRelation, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        for r in proj.value.relations:
            if r.id == relation_id:
                if r.canon_state != CanonState.ARCHIVADO:
                    return Error(
                        f"Relation '{relation_id}' is not archived"
                    )
                r.canon_state = CanonState.BORRADOR
                r.touch()
                proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def controlled_delete_relation(self, relation_id: str) -> Result[None, str]:
        return self.archive_relation(relation_id)

    def get_by_id(self, relation_id: str) -> Result[NarrativeRelation, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        for r in proj.value.relations:
            if r.id == relation_id:
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    # ------------------------------------------------------------------
    # Queries (§4.4 #9–#15)
    # ------------------------------------------------------------------

    def get_incoming(self, entity_id: str) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([r for r in proj.value.relations if r.target_id == entity_id])

    def get_outgoing(self, entity_id: str) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([r for r in proj.value.relations if r.source_id == entity_id])

    def get_between(
        self, entity_a_id: str, entity_b_id: str
    ) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([
            r for r in proj.value.relations
            if (r.source_id == entity_a_id and r.target_id == entity_b_id)
            or (r.source_id == entity_b_id and r.target_id == entity_a_id)
        ])

    def get_neighborhood(
        self, entity_id: str
    ) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([
            r for r in proj.value.relations
            if r.source_id == entity_id or r.target_id == entity_id
        ])

    def find_simple_paths(
        self,
        entity_a_id: str,
        entity_b_id: str,
        max_depth: int = 3,
    ) -> Result[list[list[NarrativeRelation]], str]:
        """BFS-based simple path finding between two entities.

        Returns all paths up to *max_depth* hops (default 3, max 5).
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        max_depth = min(max_depth, 5)

        # Build adjacency: entity_id -> list of (relation, neighbor_id)
        adj: dict[str, list[tuple[NarrativeRelation, str]]] = {}
        for r in proj.value.relations:
            adj.setdefault(r.source_id, []).append((r, r.target_id))
            adj.setdefault(r.target_id, []).append((r, r.source_id))

        if entity_a_id not in adj or entity_b_id not in adj:
            return Ok([])

        paths: list[list[NarrativeRelation]] = []
        # BFS: (current_node, path_so_far)
        queue: deque[tuple[str, list[NarrativeRelation]]] = deque()
        queue.append((entity_a_id, []))

        while queue:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for rel, neighbor in adj.get(current, []):
                if neighbor == entity_b_id:
                    paths.append(path + [rel])
                else:
                    # Avoid cycles — don't revisit nodes in the current path
                    visited = {r.source_id for r in path} | {r.target_id for r in path}
                    if neighbor not in visited and neighbor != entity_a_id:
                        queue.append((neighbor, path + [rel]))

        return Ok(paths)

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def list_all(self) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok(list(proj.value.relations))

    def filter_by_relation_type(
        self, rtype: RelationType | str
    ) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        if isinstance(rtype, str):
            rtype = RelationType(rtype)
        return Ok([r for r in proj.value.relations if r.relation_type == rtype])

    def filter_by_canon_state(
        self, state: CanonState | str
    ) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        if isinstance(state, str):
            state = CanonState(state)
        return Ok([r for r in proj.value.relations if r.canon_state == state])

    def filter_by_visibility_state(
        self, state: VisibilityState | str
    ) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        if isinstance(state, str):
            state = VisibilityState(state)
        return Ok([r for r in proj.value.relations if r.visibility_state == state])

    def filter_by_active_entities(
        self,
    ) -> Result[list[NarrativeRelation], str]:
        """Return relations where both entities are active (not archived)."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        active_ids = {
            e.id for e in proj.value.entities
            if e.canon_state != CanonState.ARCHIVADO
        }
        return Ok([
            r for r in proj.value.relations
            if r.source_id in active_ids and r.target_id in active_ids
        ])

    # ------------------------------------------------------------------
    # Broken / inactive (§4.4 #17)
    # ------------------------------------------------------------------

    def get_broken_relations(
        self,
    ) -> Result[list[NarrativeRelation], str]:
        """Relations where source or target entity does NOT exist."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        entity_ids = {e.id for e in proj.value.entities}
        result = []
        for r in proj.value.relations:
            if r.source_id not in entity_ids or r.target_id not in entity_ids:
                result.append(r)
        return Ok(result)

    def get_inactive_relations(
        self,
    ) -> Result[list[NarrativeRelation], str]:
        """Relations where source or target entity exists but is archived."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        result = []
        for r in proj.value.relations:
            for e in proj.value.entities:
                if e.id in (r.source_id, r.target_id) and e.canon_state == CanonState.ARCHIVADO:
                    result.append(r)
                    break
        return Ok(result)

    # ------------------------------------------------------------------
    # State mutations
    # ------------------------------------------------------------------

    def change_canon_state(
        self, relation_id: str, new_state: CanonState | str
    ) -> Result[NarrativeRelation, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        if isinstance(new_state, str):
            try:
                new_state = CanonState(new_state)
            except ValueError:
                return Error(f"Invalid canon state: '{new_state}'")

        for r in proj.value.relations:
            if r.id == relation_id:
                r.canon_state = new_state
                r.touch()
                proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def change_visibility_state(
        self, relation_id: str, new_state: VisibilityState | str
    ) -> Result[NarrativeRelation, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        if isinstance(new_state, str):
            try:
                new_state = VisibilityState(new_state)
            except ValueError:
                return Error(f"Invalid visibility state: '{new_state}'")

        for r in proj.value.relations:
            if r.id == relation_id:
                r.visibility_state = new_state
                r.touch()
                proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def add_tag(self, relation_id: str, tag: str) -> Result[NarrativeRelation, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        for r in proj.value.relations:
            if r.id == relation_id:
                if tag not in r.tags:
                    r.tags.append(tag)
                    r.touch()
                    proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def remove_tag(self, relation_id: str, tag: str) -> Result[NarrativeRelation, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        for r in proj.value.relations:
            if r.id == relation_id:
                if tag in r.tags:
                    r.tags.remove(tag)
                    r.touch()
                    proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")


__all__ = ["RelationService"]
