"""
Custom Type Service — application-layer CRUD for custom entity types,
field definitions, and relation types (Bloque 8).

Provides ``CustomTypeService``, a stateful service that manages
user-defined types within the active project.  All methods mutate
the project collections in memory; persistence is the caller's
responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.domain.custom_types import (
    CustomEntityType,
    CustomFieldDefinition,
    CustomRelationType,
    FieldType,
)
from packages.domain.result import Error, Ok, Result


@dataclass
class CustomTypeService:
    """Stateful service for custom type lifecycle.

    Linked to the active project via ``project_service``.  All
    mutations write to ``project.custom_entity_types``,
    ``project.custom_field_definitions``, or
    ``project.custom_relation_types`` in memory.
    """

    project_service: Any  # ProjectService (avoid circular import)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_project(self):
        ps = self.project_service
        if ps.active_project is None:
            return Error("No active project")
        return Ok(ps.active_project)

    # ------------------------------------------------------------------
    # CustomEntityType CRUD
    # ------------------------------------------------------------------

    def create_entity_type(self, data: dict[str, Any]) -> Result[CustomEntityType, str]:
        """Create a new CustomEntityType and add it to the project."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        ct = CustomEntityType.from_dict(data)
        if not ct.name.strip():
            return Error("Custom entity type name cannot be empty")

        proj.value.custom_entity_types.append(ct)
        proj.value.touch()
        return Ok(ct)

    def update_entity_type(
        self, type_id: str, data: dict[str, Any]
    ) -> Result[CustomEntityType, str]:
        """Update an existing CustomEntityType by ID."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for i, ct in enumerate(proj.value.custom_entity_types):
            if ct.id == type_id:
                updated = CustomEntityType.from_dict({**ct.to_dict(), **data})
                updated.id = type_id  # Preserve ID
                proj.value.custom_entity_types[i] = updated
                proj.value.touch()
                return Ok(updated)

        return Error(f"CustomEntityType '{type_id}' not found")

    def delete_entity_type(self, type_id: str) -> Result[None, str]:
        """Soft-delete: set is_active=False."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for ct in proj.value.custom_entity_types:
            if ct.id == type_id:
                ct.is_active = False
                proj.value.touch()
                return Ok(None)

        return Error(f"CustomEntityType '{type_id}' not found")

    def get_entity_type(self, type_id: str) -> Result[CustomEntityType, str]:
        """Get by ID (active or inactive)."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for ct in proj.value.custom_entity_types:
            if ct.id == type_id:
                return Ok(ct)

        return Error(f"CustomEntityType '{type_id}' not found")

    def list_entity_types(
        self, include_inactive: bool = False
    ) -> Result[list[CustomEntityType], str]:
        """List all custom entity types (active only by default)."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        if include_inactive:
            return Ok(list(proj.value.custom_entity_types))
        return Ok([ct for ct in proj.value.custom_entity_types if ct.is_active])

    # ------------------------------------------------------------------
    # CustomFieldDefinition CRUD
    # ------------------------------------------------------------------

    def create_field_definition(
        self, data: dict[str, Any]
    ) -> Result[CustomFieldDefinition, str]:
        """Create a new CustomFieldDefinition."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        fd = CustomFieldDefinition.from_dict(data)
        if not fd.name.strip():
            return Error("Field definition name cannot be empty")

        proj.value.custom_field_definitions.append(fd)
        proj.value.touch()
        return Ok(fd)

    def update_field_definition(
        self, field_id: str, data: dict[str, Any]
    ) -> Result[CustomFieldDefinition, str]:
        """Update an existing CustomFieldDefinition by ID."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for i, fd in enumerate(proj.value.custom_field_definitions):
            if fd.id == field_id:
                current = fd.to_dict()
                current.update(data)
                updated = CustomFieldDefinition.from_dict(current)
                updated.id = field_id
                proj.value.custom_field_definitions[i] = updated
                proj.value.touch()
                return Ok(updated)

        return Error(f"CustomFieldDefinition '{field_id}' not found")

    def delete_field_definition(self, field_id: str) -> Result[None, str]:
        """Soft-delete: set is_active=False."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for fd in proj.value.custom_field_definitions:
            if fd.id == field_id:
                fd.is_active = False
                proj.value.touch()
                return Ok(None)

        return Error(f"CustomFieldDefinition '{field_id}' not found")

    def get_field_definition(
        self, field_id: str
    ) -> Result[CustomFieldDefinition, str]:
        """Get by ID (active or inactive)."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for fd in proj.value.custom_field_definitions:
            if fd.id == field_id:
                return Ok(fd)

        return Error(f"CustomFieldDefinition '{field_id}' not found")

    def list_field_definitions(
        self, include_inactive: bool = False, entity_type_id: str | None = None,
    ) -> Result[list[CustomFieldDefinition], str]:
        """List field definitions, optionally filtered by entity type ID."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        results = list(proj.value.custom_field_definitions)

        if not include_inactive:
            results = [fd for fd in results if fd.is_active]

        if entity_type_id is not None:
            # Filter fields associated with a specific entity type
            entity_types = proj.value.custom_entity_types
            matching_ct = next(
                (ct for ct in entity_types if ct.id == entity_type_id), None
            )
            if matching_ct is not None:
                field_ids = set(matching_ct.custom_fields)
                results = [fd for fd in results if fd.id in field_ids]
            else:
                results = []

        return Ok(results)

    # ------------------------------------------------------------------
    # CustomRelationType CRUD
    # ------------------------------------------------------------------

    def create_relation_type(
        self, data: dict[str, Any]
    ) -> Result[CustomRelationType, str]:
        """Create a new CustomRelationType."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        crt = CustomRelationType.from_dict(data)
        if not crt.name.strip():
            return Error("Custom relation type name cannot be empty")

        proj.value.custom_relation_types.append(crt)
        proj.value.touch()
        return Ok(crt)

    def update_relation_type(
        self, type_id: str, data: dict[str, Any]
    ) -> Result[CustomRelationType, str]:
        """Update an existing CustomRelationType by ID."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for i, crt in enumerate(proj.value.custom_relation_types):
            if crt.id == type_id:
                current = crt.to_dict()
                current.update(data)
                updated = CustomRelationType.from_dict(current)
                updated.id = type_id
                proj.value.custom_relation_types[i] = updated
                proj.value.touch()
                return Ok(updated)

        return Error(f"CustomRelationType '{type_id}' not found")

    def delete_relation_type(self, type_id: str) -> Result[None, str]:
        """Soft-delete: set is_active=False."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for crt in proj.value.custom_relation_types:
            if crt.id == type_id:
                crt.is_active = False
                proj.value.touch()
                return Ok(None)

        return Error(f"CustomRelationType '{type_id}' not found")

    def get_relation_type(
        self, type_id: str
    ) -> Result[CustomRelationType, str]:
        """Get by ID (active or inactive)."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        for crt in proj.value.custom_relation_types:
            if crt.id == type_id:
                return Ok(crt)

        return Error(f"CustomRelationType '{type_id}' not found")

    def list_relation_types(
        self, include_inactive: bool = False
    ) -> Result[list[CustomRelationType], str]:
        """List all custom relation types (active only by default)."""
        proj = self._active_project()
        if isinstance(proj, Error):
            return Error(proj.error)

        if include_inactive:
            return Ok(list(proj.value.custom_relation_types))
        return Ok([crt for crt in proj.value.custom_relation_types if crt.is_active])

    # ------------------------------------------------------------------
    # Field value validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_field_value(
        definition: CustomFieldDefinition, value: Any,
        entity_service: Any = None,
    ) -> Result[None, str]:
        """Validate *value* against *definition*.

        Strict validation for NUMBER, BOOLEAN, SINGLE_SELECT,
        MULTI_SELECT, and ENTITY_REF.  Other types pass through.
        """
        ft = definition.field_type

        if ft == FieldType.NUMBER:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return Error(f"Field '{definition.name}' expects a number")

        elif ft == FieldType.BOOLEAN:
            if not isinstance(value, bool):
                return Error(f"Field '{definition.name}' expects true/false")

        elif ft == FieldType.SINGLE_SELECT:
            if not isinstance(value, str) or value not in definition.options:
                valid = ", ".join(definition.options)
                return Error(
                    f"Field '{definition.name}' value must be one of: {valid}"
                )

        elif ft == FieldType.MULTI_SELECT:
            if not isinstance(value, list):
                return Error(
                    f"Field '{definition.name}' expects a list of values"
                )
            for v in value:
                if v not in definition.options:
                    valid = ", ".join(definition.options)
                    return Error(
                        f"Field '{definition.name}': '{v}' not in valid options: {valid}"
                    )

        elif ft == FieldType.ENTITY_REF:
            if entity_service is not None and isinstance(value, str):
                result = entity_service.get_by_id(value)
                if isinstance(result, Error):
                    return Error(
                        f"Field '{definition.name}': referenced entity '{value}' not found"
                    )

        return Ok(None)


__all__ = ["CustomTypeService"]
