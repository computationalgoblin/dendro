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

from packages.application.temporal_dating import normalize_relation_dating
from packages.domain.custom_types import CustomFieldValue
from packages.domain.entity import CanonState, VisibilityState
from packages.domain.relation import (
    Direction,
    IntensityLevel,
    NarrativeRelation,
    RelationType,
    validate_relation,
)
from packages.domain.result import Error, Ok, Result
from packages.domain.temporal_span import TemporalSpan
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
        return proj.value.entity_by_id(entity_id) is not None  # BETA1-L01: O(1)

    def _find_entity(self, entity_id: str):
        proj = self._active_project()
        if isinstance(proj, Error):
            return None
        return proj.value.entity_by_id(entity_id)  # BETA1-L01: O(1)

    def _normalize_relation_enums(self, relation: NarrativeRelation) -> None:
        """Coerce UI payload strings into domain enums without creating parallel models."""
        enum_specs = (
            ("relation_type", RelationType, RelationType.ESTA_RELACIONADO_CON),
            ("direction", Direction, Direction.UNIDIRECCIONAL),
            ("intensity", IntensityLevel, IntensityLevel.MEDIA),
            ("canon_state", CanonState, CanonState.CANONICO),
            ("visibility_state", VisibilityState, VisibilityState.VISIBLE_USUARIO),
        )
        for attr, enum_cls, default in enum_specs:
            value = getattr(relation, attr, default)
            if isinstance(value, enum_cls):
                continue
            try:
                setattr(relation, attr, enum_cls(value))
            except Exception:
                setattr(relation, attr, default)

    def _relation_signature(
        self,
        relation: NarrativeRelation,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: RelationType | str | None = None,
        direction: Direction | str | None = None,
    ) -> tuple[str, str, str, str]:
        rtype = relation_type if relation_type is not None else getattr(relation, "relation_type", RelationType.ESTA_RELACIONADO_CON)
        direction_value = direction if direction is not None else getattr(relation, "direction", Direction.UNIDIRECCIONAL)
        if isinstance(rtype, RelationType):
            rtype = rtype.value
        if isinstance(direction_value, Direction):
            direction_value = direction_value.value
        return (
            source_id if source_id is not None else getattr(relation, "source_id", ""),
            target_id if target_id is not None else getattr(relation, "target_id", ""),
            str(rtype or RelationType.ESTA_RELACIONADO_CON.value),
            str(direction_value or Direction.UNIDIRECCIONAL.value),
        )

    def _has_duplicate_relation(self, relation: NarrativeRelation, relations: list[NarrativeRelation]) -> bool:
        signature = self._relation_signature(relation)
        for other in relations:
            if getattr(other, "id", "") == getattr(relation, "id", ""):
                continue
            if self._relation_signature(other) == signature:
                return True
        return False

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_relation(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: RelationType | str | None = None,
        data: dict[str, Any] | None = None,
        history_service: Any = None,
        *,
        enforce_dating: bool = False,
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

        if isinstance(data, dict) and data:
            scalar_fields = (
                "description", "temporality", "causality", "conditions", "source",
                "direction", "intensity", "canon_state", "visibility_state",
                "validity_conditions", "tags", "source_id", "target_id", "layer_ids",
                "custom_relation_type_id",
                "birth_year", "death_year",  # BETA1-J04: intervalo temporal
            )
            for key in scalar_fields:
                if key in data:
                    setattr(relation, key, data[key])
            if "relation_type" in data:
                relation.relation_type = data["relation_type"]
            if isinstance(data.get("life_span"), dict):
                relation.life_span = TemporalSpan.from_dict(data["life_span"])
            self._normalize_relation_enums(relation)
            if "custom_metadata" in data and isinstance(data["custom_metadata"], dict):
                relation.custom_metadata.update(data["custom_metadata"])

        # BETA1-J04: lapso coherente con el espejo entero; sin fecha → pendiente.
        normalize_relation_dating(relation)
        if enforce_dating and not relation.as_temporal_span().is_dated():
            return Error(
                "La relación requiere una fecha de inicio antes de guardar "
                "(un año concreto o una precisión explícita)."
            )

        issues = validate_relation(relation)
        if issues:
            return Error(f"Relation validation failed: {'; '.join(issues)}")
        # BETA1-L01: un duplicado comparte source_id (parte de la firma), así que
        # basta comprobar la adyacencia de ese origen — O(grado) en vez de O(M).
        # Hace la importación masiva O(N) en vez de O(N²).
        if self._has_duplicate_relation(relation, proj.value.relations_for(relation.source_id)):
            return Error("Ya existe una relación con el mismo origen, destino, tipo y dirección")

        proj.value.relations.append(relation)
        proj.value.touch()
        if history_service is not None:
            from packages.domain.source_history import HistoryEventType
            entry = history_service.make_entry(
                HistoryEventType.CREACION_RELACION,
                affected_relation_id=relation.id,
                new_value=f"{relation.source_id} -> {relation.target_id}",
                change_origin="RelationService.create_relation",
                operation="create_relation",
            )
            history_service.record(entry)
        return Ok(relation)

    def update_relation(
        self, relation_id: str, data: dict[str, Any],
        history_service: Any = None,
    ) -> Result[NarrativeRelation, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for r in proj.value.relations:
            if r.id == relation_id:
                previous = {
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "relation_type": r.relation_type,
                    "description": getattr(r, "description", ""),
                    "temporality": getattr(r, "temporality", ""),
                    "causality": getattr(r, "causality", ""),
                    "conditions": getattr(r, "conditions", ""),
                    "source": getattr(r, "source", ""),
                    "direction": getattr(r, "direction", Direction.UNIDIRECCIONAL),
                    "intensity": getattr(r, "intensity", IntensityLevel.MEDIA),
                    "canon_state": getattr(r, "canon_state", CanonState.CANONICO),
                    "visibility_state": getattr(r, "visibility_state", VisibilityState.VISIBLE_USUARIO),
                    "validity_conditions": list(getattr(r, "validity_conditions", []) or []),
                    "tags": list(getattr(r, "tags", []) or []),
                    "layer_ids": list(getattr(r, "layer_ids", []) or []),
                    "custom_relation_type_id": getattr(r, "custom_relation_type_id", None),
                    "custom_metadata": dict(getattr(r, "custom_metadata", {}) or {}),
                }
                scalar_fields = (
                    "source_id", "target_id", "description", "temporality", "causality",
                    "conditions", "source", "direction", "intensity", "canon_state",
                    "visibility_state", "validity_conditions", "tags", "layer_ids",
                    "custom_relation_type_id",
                    "birth_year", "death_year",  # BETA1-G06: relation temporal interval
                )
                for key in scalar_fields:
                    if key in data:
                        setattr(r, key, data[key])
                if "relation_type" in data:
                    setattr(r, "relation_type", data["relation_type"])
                self._normalize_relation_enums(r)
                if "custom_metadata" in data and isinstance(data["custom_metadata"], dict):
                    r.custom_metadata = dict(data["custom_metadata"])
                issues = validate_relation(r)
                if issues:
                    for key, value in previous.items():
                        setattr(r, key, value)
                    return Error(f"Relation validation failed: {'; '.join(issues)}")
                # BETA1-L01: duplicados solo entre la adyacencia del origen (O(grado)).
                if self._has_duplicate_relation(r, proj.value.relations_for(r.source_id)):
                    for key, value in previous.items():
                        setattr(r, key, value)
                    return Error("Ya existe una relación con el mismo origen, destino, tipo y dirección")
                r.touch()
                proj.value.touch()
                if history_service is not None:
                    from packages.domain.source_history import HistoryEventType
                    entry = history_service.make_entry(
                        HistoryEventType.EDICION_RELACION,
                        affected_relation_id=r.id,
                        change_origin="RelationService.update_relation",
                        operation="update_relation",
                    )
                    history_service.record(entry)
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def archive_relation(self, relation_id: str, history_service: Any = None) -> Result[None, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        for r in proj.value.relations:
            if r.id == relation_id:
                prev = r.canon_state.value
                r.canon_state = CanonState.ARCHIVADO
                r.touch()
                proj.value.touch()
                if history_service is not None:
                    from packages.domain.source_history import HistoryEventType
                    entry = history_service.make_entry(
                        HistoryEventType.ARCHIVADO_RELACION,
                        affected_relation_id=r.id,
                        previous_value=prev,
                        new_value=r.canon_state.value,
                        change_origin="RelationService.archive_relation",
                        operation="archive_relation",
                    )
                    history_service.record(entry)
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
                r.canon_state = CanonState.CANONICO
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
        relation = proj.value.relation_by_id(relation_id)  # BETA1-L01: O(1)
        if relation is not None:
            return Ok(relation)
        return Error(f"Relation with id '{relation_id}' not found")

    # ------------------------------------------------------------------
    # Queries (§4.4 #9–#15)
    # ------------------------------------------------------------------

    def get_incoming(self, entity_id: str) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        # BETA1-L01: adyacencia O(grado) en vez de escaneo O(M).
        return Ok([r for r in proj.value.relations_for(entity_id) if r.target_id == entity_id])

    def get_outgoing(self, entity_id: str) -> Result[list[NarrativeRelation], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        # BETA1-L01: adyacencia O(grado) en vez de escaneo O(M).
        return Ok([r for r in proj.value.relations_for(entity_id) if r.source_id == entity_id])

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
        # BETA1-L01: vecindario directo desde el índice de adyacencia (O(grado)).
        return Ok(proj.value.relations_for(entity_id))

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
        self, relation_id: str, new_state: CanonState | str,
        history_service: Any = None,
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

    # ------------------------------------------------------------------
    # Custom fields (Bloque 8)
    # ------------------------------------------------------------------

    def set_custom_field(
        self, relation_id: str, field_id: str, value: Any,
        custom_type_service: Any = None,
    ) -> Result[NarrativeRelation, str]:
        """Assign a custom field value to a relation."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        if custom_type_service is not None:
            fd_result = custom_type_service.get_field_definition(field_id)
            if isinstance(fd_result, Error):
                return Error(fd_result.error)
            fd = fd_result.value
            if not fd.is_active:
                return Error(f"Field definition '{field_id}' is inactive")
            validation = custom_type_service._validate_field_value(fd, value)
            if isinstance(validation, Error):
                return Error(validation.error)

        for r in proj.value.relations:
            if r.id == relation_id:
                cfv = CustomFieldValue(field_id=field_id, value=value)
                r.custom_fields = [
                    f for f in r.custom_fields if f.field_id != field_id
                ]
                r.custom_fields.append(cfv)
                r.touch()
                proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def remove_custom_field(
        self, relation_id: str, field_id: str,
    ) -> Result[NarrativeRelation, str]:
        """Remove a custom field value from a relation."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for r in proj.value.relations:
            if r.id == relation_id:
                r.custom_fields = [
                    f for f in r.custom_fields if f.field_id != field_id
                ]
                r.touch()
                proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def get_custom_fields(
        self, relation_id: str,
    ) -> Result[list[CustomFieldValue], str]:
        """Get all custom field values for a relation."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for r in proj.value.relations:
            if r.id == relation_id:
                return Ok(list(r.custom_fields))
        return Error(f"Relation with id '{relation_id}' not found")

    # ------------------------------------------------------------------
    # Layers (Bloque 10)
    # ------------------------------------------------------------------

    def assign_layer(
        self, relation_id: str, layer_id: str,
    ) -> Result[NarrativeRelation, str]:
        """Assign a world layer to a relation.

        Validates that *layer_id* exists and is visible.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        # Validate layer exists and is visible
        layer = None
        for wl in proj.value.world_layers:
            if wl.id == layer_id:
                layer = wl
                break
        if layer is None:
            return Error(f"World layer '{layer_id}' not found")
        if not layer.is_visible:
            return Error(f"World layer '{layer_id}' is hidden")

        for r in proj.value.relations:
            if r.id == relation_id:
                if layer_id not in r.layer_ids:
                    r.layer_ids.append(layer_id)
                    r.touch()
                    proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def remove_layer(
        self, relation_id: str, layer_id: str,
    ) -> Result[NarrativeRelation, str]:
        """Remove a world layer from a relation. Idempotent."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for r in proj.value.relations:
            if r.id == relation_id:
                if layer_id in r.layer_ids:
                    r.layer_ids.remove(layer_id)
                    r.touch()
                    proj.value.touch()
                return Ok(r)
        return Error(f"Relation with id '{relation_id}' not found")

    def get_by_layer(
        self, layer_id: str,
    ) -> Result[list[NarrativeRelation], str]:
        """Return all relations assigned to a given world layer."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([r for r in proj.value.relations if layer_id in r.layer_ids])

    def delete_relation(self, relation_id: str) -> Result[None, str]:
        """Delete a relation by id."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        before = len(proj.value.relations)
        proj.value.relations = [r for r in proj.value.relations if r.id != relation_id]
        if len(proj.value.relations) == before:
            return Error(f"Relation '{relation_id}' not found")
        proj.value.touch()
        return Ok(None)


__all__ = ["RelationService"]
