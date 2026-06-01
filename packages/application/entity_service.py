"""
Entity service — application-layer lifecycle for narrative entities.

Provides ``EntityService``, a stateful service that orchestrates CRUD
operations on ``NarrativeEntity`` objects within the active project,
using domain filters and the persistence layer.

Usage::

    from packages.application.project_service import ProjectService
    from packages.application.entity_service import EntityService

    ps = ProjectService()
    ps.create("My World")
    svc = EntityService(ps, ps.store)
    result = svc.create_entity({"name": "Eldrin", "entity_type": "personaje"})
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packages.domain.custom_types import CustomFieldValue
from packages.domain.entity import (
    CanonState,
    EntityType,
    NarrativeEntity,
    VisibilityState,
    validate_entity,
)
from packages.domain.result import Error, Ok, Result
from packages.persistence.store import ProjectStore


@dataclass
class EntityService:
    """Application service for NarrativeEntity lifecycle.

    Delegates persistence to ``store`` and derives the active project
    from ``project_service``.  All mutating methods persist via
    ``store.save()`` using the project's current path.

    Attributes:
        project_service: The active ``ProjectService`` (stateful).
        store: The ``ProjectStore`` used for all persistence operations.
        _current_path: Path last used for persistence (set on save).
    """

    project_service: Any  # ProjectService (avoid circular import)
    store: ProjectStore = field(default_factory=ProjectStore)
    _current_path: Path | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_project(self):
        """Return Ok(Project) or Error if no active project."""
        ps = self.project_service
        if ps.active_project is None:
            return Error("No active project")
        return Ok(ps.active_project)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_entity(self, data: dict[str, Any], history_service: Any = None) -> Result[NarrativeEntity, str]:
        """Create a new entity, add it to the active project, and persist.

        Args:
            data: Dict with at least ``name`` and ``entity_type`` keys.

        Returns:
            Ok(NarrativeEntity) on success.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        name = str(data.get("name", "")).strip()
        if not name:
            return Error("Entity name cannot be empty")

        entity = NarrativeEntity.from_dict(data)
        entity.name = name

        issues = validate_entity(entity)
        if issues:
            return Error(f"Entity validation failed: {'; '.join(issues)}")

        proj.value.entities.append(entity)
        proj.value.touch()
        if history_service is not None:
            from packages.domain.source_history import HistoryEventType
            entry = history_service.make_entry(
                HistoryEventType.CREACION_ENTIDAD,
                affected_entity_id=entity.id,
                new_value=entity.name,
                change_origin="EntityService.create_entity",
                operation="create_entity",
            )
            history_service.record(entry)
        return Ok(entity)

    def update_entity(
        self, entity_id: str, data: dict[str, Any],
        history_service: Any = None,
    ) -> Result[NarrativeEntity, str]:
        """Modify an existing entity and persist.

        Args:
            entity_id: The entity to modify.
            data: Dict of fields to update (merged into existing entity).

        Returns:
            Ok(updated NarrativeEntity) on success.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        found = None
        for e in proj.value.entities:
            if e.id == entity_id:
                found = e
                break

        if found is None:
            return Error(f"Entity with id '{entity_id}' not found")

        # Merge all editable NarrativeEntity fields used by the B27.4 inspector.
        # Use the domain parser instead of ad-hoc UI parsing so enums/lists stay
        # aligned with the core model and invalid values fall back safely.
        editable_fields = {
            "name", "aliases", "entity_type", "brief_description",
            "extended_description", "canon_state", "visibility_state",
            "certainty_level", "tags", "domain", "layers", "origin",
            "domain_ids", "layer_ids", "private_notes", "exportable_notes",
            "narrative_importance", "development_level", "custom_metadata",
            "custom_type_id", "custom_fields",
        }
        merged = found.to_dict()
        for key in editable_fields:
            if key in data:
                merged[key] = data[key]
        updated = NarrativeEntity.from_dict(merged)
        issues = validate_entity(updated)
        if issues:
            return Error(f"Entity validation failed: {'; '.join(issues)}")
        for key in editable_fields:
            setattr(found, key, getattr(updated, key))

        found.touch()
        proj.value.touch()
        if history_service is not None:
            from packages.domain.source_history import HistoryEventType
            entry = history_service.make_entry(
                HistoryEventType.EDICION_ENTIDAD,
                affected_entity_id=found.id,
                change_origin="EntityService.update_entity",
                operation="update_entity",
            )
            history_service.record(entry)
        return Ok(found)

    def archive_entity(self, entity_id: str, history_service: Any = None) -> Result[None, str]:
        """Soft-delete an entity (canon_state → ARCHIVADO).

        The entity stays in the project for traceability.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                prev = e.canon_state.value
                e.canon_state = CanonState.ARCHIVADO
                e.touch()
                proj.value.touch()
                if history_service is not None:
                    from packages.domain.source_history import HistoryEventType
                    entry = history_service.make_entry(
                        HistoryEventType.ARCHIVADO_ENTIDAD,
                        affected_entity_id=e.id,
                        previous_value=prev,
                        new_value=e.canon_state.value,
                        change_origin="EntityService.archive_entity",
                        operation="archive_entity",
                    )
                    history_service.record(entry)
                return Ok(None)
        return Error(f"Entity with id '{entity_id}' not found")

    def restore_entity(self, entity_id: str, history_service: Any = None) -> Result[NarrativeEntity, str]:
        """Restore an archived entity to BORRADOR state."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                if e.canon_state != CanonState.ARCHIVADO:
                    return Error(
                        f"Entity '{entity_id}' is not archived "
                        f"(current: {e.canon_state.value})"
                    )
                e.canon_state = CanonState.BORRADOR
                e.touch()
                proj.value.touch()
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def controlled_delete_entity(self, entity_id: str) -> Result[None, str]:
        """Alias for archive_entity with existence validation."""
        return self.archive_entity(entity_id)

    def get_by_id(self, entity_id: str) -> Result[NarrativeEntity, str]:
        """Retrieve an entity by id from the active project."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    # ------------------------------------------------------------------
    # Filters — §3.6
    # ------------------------------------------------------------------

    def list_all(self) -> Result[list[NarrativeEntity], str]:
        """Return all entities in the active project."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok(list(proj.value.entities))

    def filter_by_type(
        self, entity_type: EntityType | str
    ) -> Result[list[NarrativeEntity], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        if isinstance(entity_type, str):
            entity_type = EntityType(entity_type)
        return Ok([e for e in proj.value.entities if e.entity_type == entity_type])

    def filter_by_canon_state(
        self, canon_state: CanonState | str
    ) -> Result[list[NarrativeEntity], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        if isinstance(canon_state, str):
            canon_state = CanonState(canon_state)
        return Ok([e for e in proj.value.entities if e.canon_state == canon_state])

    def filter_by_visibility_state(
        self, visibility: VisibilityState | str
    ) -> Result[list[NarrativeEntity], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        if isinstance(visibility, str):
            visibility = VisibilityState(visibility)
        return Ok([e for e in proj.value.entities if e.visibility_state == visibility])

    def filter_by_tag(self, tag: str) -> Result[list[NarrativeEntity], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([e for e in proj.value.entities if tag in e.tags])

    def filter_by_domain(self, domain: str) -> Result[list[NarrativeEntity], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([e for e in proj.value.entities if e.domain == domain])

    def filter_by_layer(self, layer: str) -> Result[list[NarrativeEntity], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([e for e in proj.value.entities if layer in e.layers])

    def filter_by_archived(
        self, archived: bool = True
    ) -> Result[list[NarrativeEntity], str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        if archived:
            return Ok([e for e in proj.value.entities
                       if e.canon_state == CanonState.ARCHIVADO])
        return Ok([e for e in proj.value.entities
                   if e.canon_state != CanonState.ARCHIVADO])

    # ------------------------------------------------------------------
    # Search — §3.6
    # ------------------------------------------------------------------

    def search_by_name(self, query: str) -> Result[list[NarrativeEntity], str]:
        """Case-insensitive contains search on entity name."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        q = query.lower()
        return Ok([e for e in proj.value.entities if q in e.name.lower()])

    def search_by_alias(self, query: str) -> Result[list[NarrativeEntity], str]:
        """Case-insensitive contains search on aliases."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        q = query.lower()
        return Ok([
            e for e in proj.value.entities
            if any(q in a.lower() for a in e.aliases)
        ])

    def search(self, query: str) -> Result[list[NarrativeEntity], str]:
        """Combined search: name OR alias."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        q = query.lower()
        results = []
        for e in proj.value.entities:
            if q in e.name.lower() or any(q in a.lower() for a in e.aliases):
                results.append(e)
        return Ok(results)

    # ------------------------------------------------------------------
    # Sorting — §3.6
    # ------------------------------------------------------------------

    @staticmethod
    def sort_by_name(entities: list[NarrativeEntity]) -> list[NarrativeEntity]:
        return sorted(entities, key=lambda e: e.name.lower())

    @staticmethod
    def sort_by_updated_at(
        entities: list[NarrativeEntity],
    ) -> list[NarrativeEntity]:
        return sorted(entities, key=lambda e: e.updated_at, reverse=True)

    # ------------------------------------------------------------------
    # State operations — §3.6
    # ------------------------------------------------------------------

    def change_canon_state(
        self, entity_id: str, new_state: CanonState | str,
        history_service: Any = None,
    ) -> Result[NarrativeEntity, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        if isinstance(new_state, str):
            try:
                new_state = CanonState(new_state)
            except ValueError:
                return Error(f"Invalid canon state: '{new_state}'")

        for e in proj.value.entities:
            if e.id == entity_id:
                prev = e.canon_state.value
                e.canon_state = new_state
                e.touch()
                proj.value.touch()
                if history_service is not None:
                    from packages.domain.source_history import HistoryEventType
                    entry = history_service.make_entry(
                        HistoryEventType.CAMBIO_CANON,
                        affected_entity_id=e.id,
                        previous_value=prev,
                        new_value=new_state.value,
                        change_origin="EntityService.change_canon_state",
                        operation="change_canon_state",
                    )
                    history_service.record(entry)
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def change_visibility_state(
        self, entity_id: str, new_state: VisibilityState | str,
        history_service: Any = None,
    ) -> Result[NarrativeEntity, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        if isinstance(new_state, str):
            try:
                new_state = VisibilityState(new_state)
            except ValueError:
                return Error(f"Invalid visibility state: '{new_state}'")

        for e in proj.value.entities:
            if e.id == entity_id:
                prev = e.visibility_state.value
                e.visibility_state = new_state
                e.touch()
                proj.value.touch()
                if history_service is not None:
                    from packages.domain.source_history import HistoryEventType
                    entry = history_service.make_entry(
                        HistoryEventType.CAMBIO_VISIBILIDAD,
                        affected_entity_id=e.id,
                        previous_value=prev,
                        new_value=new_state.value,
                        change_origin="EntityService.change_visibility_state",
                        operation="change_visibility_state",
                    )
                    history_service.record(entry)
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def add_tag(self, entity_id: str, tag: str) -> Result[NarrativeEntity, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                if tag not in e.tags:
                    e.tags.append(tag)
                    e.touch()
                    proj.value.touch()
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def remove_tag(self, entity_id: str, tag: str) -> Result[NarrativeEntity, str]:
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                if tag in e.tags:
                    e.tags.remove(tag)
                    e.touch()
                    proj.value.touch()
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    # ------------------------------------------------------------------
    # Custom fields (Bloque 8)
    # ------------------------------------------------------------------

    def set_custom_field(
        self, entity_id: str, field_id: str, value: Any,
        custom_type_service: Any = None,
    ) -> Result[NarrativeEntity, str]:
        """Assign a custom field value to an entity.

        Validates the value against the field definition if
        *custom_type_service* is provided.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        # Validate field definition exists
        if custom_type_service is not None:
            fd_result = custom_type_service.get_field_definition(field_id)
            if isinstance(fd_result, Error):
                return Error(fd_result.error)
            fd = fd_result.value
            if not fd.is_active:
                return Error(f"Field definition '{field_id}' is inactive")
            validation = custom_type_service._validate_field_value(
                fd, value, self,
            )
            if isinstance(validation, Error):
                return Error(validation.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                cfv = CustomFieldValue(field_id=field_id, value=value)
                # Replace existing value for same field_id
                e.custom_fields = [
                    f for f in e.custom_fields if f.field_id != field_id
                ]
                e.custom_fields.append(cfv)
                e.touch()
                proj.value.touch()
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def remove_custom_field(
        self, entity_id: str, field_id: str,
    ) -> Result[NarrativeEntity, str]:
        """Remove a custom field value from an entity."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                e.custom_fields = [
                    f for f in e.custom_fields if f.field_id != field_id
                ]
                e.touch()
                proj.value.touch()
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def get_custom_fields(
        self, entity_id: str,
    ) -> Result[list[CustomFieldValue], str]:
        """Get all custom field values for an entity."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                return Ok(list(e.custom_fields))
        return Error(f"Entity with id '{entity_id}' not found")

    # ------------------------------------------------------------------
    # Domains & Layers (Bloque 10)
    # ------------------------------------------------------------------

    def assign_domain(self, entity_id: str, domain: str) -> Result[NarrativeEntity, str]:
        """Assign a narrative domain to an entity.

        Validates that *domain* exists in ``project.domains``.
        """
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        if domain not in proj.value.domains:
            return Error(
                f"Invalid domain '{domain}'. "
                f"Valid domains: {', '.join(proj.value.domains)}"
            )

        for e in proj.value.entities:
            if e.id == entity_id:
                if domain not in e.domain_ids:
                    e.domain_ids.append(domain)
                    e.touch()
                    proj.value.touch()
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def remove_domain(
        self, entity_id: str, domain: str,
    ) -> Result[NarrativeEntity, str]:
        """Remove a domain from an entity. Idempotent."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                if domain in e.domain_ids:
                    e.domain_ids.remove(domain)
                    e.touch()
                    proj.value.touch()
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def get_by_domain(
        self, domain: str,
    ) -> Result[list[NarrativeEntity], str]:
        """Return all entities assigned to a given domain."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([e for e in proj.value.entities if domain in e.domain_ids])

    def assign_layer(
        self, entity_id: str, layer_id: str,
    ) -> Result[NarrativeEntity, str]:
        """Assign a world layer to an entity.

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

        for e in proj.value.entities:
            if e.id == entity_id:
                if layer_id not in e.layer_ids:
                    e.layer_ids.append(layer_id)
                    e.touch()
                    proj.value.touch()
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def remove_layer(
        self, entity_id: str, layer_id: str,
    ) -> Result[NarrativeEntity, str]:
        """Remove a world layer from an entity. Idempotent."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for e in proj.value.entities:
            if e.id == entity_id:
                if layer_id in e.layer_ids:
                    e.layer_ids.remove(layer_id)
                    e.touch()
                    proj.value.touch()
                return Ok(e)
        return Error(f"Entity with id '{entity_id}' not found")

    def get_by_layer(
        self, layer_id: str,
    ) -> Result[list[NarrativeEntity], str]:
        """Return all entities assigned to a given world layer."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)
        return Ok([e for e in proj.value.entities if layer_id in e.layer_ids])


__all__ = ["EntityService"]
