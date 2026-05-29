"""
Custom types, fields and taxonomies — domain models (stdlib-only).

Provides extendable entity types, field definitions, and relation types
that users can define without modifying code (§8.2, §8.3, §8.4).

Usage::

    from packages.domain.custom_types import (
        CustomEntityType,
        CustomFieldDefinition,
        CustomRelationType,
        CustomFieldValue,
        FieldType,
    )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# FieldType — 15 values (§8.3)
# ---------------------------------------------------------------------------


class FieldType(str, Enum):
    """Types of custom fields that can be defined on entities and relations."""

    TEXT_SHORT = "text_short"
    TEXT_LONG = "text_long"
    NUMBER = "number"
    DATE = "date"
    WORLD_DATE = "world_date"
    BOOLEAN = "boolean"
    SINGLE_SELECT = "single_select"
    MULTI_SELECT = "multi_select"
    ENTITY_REF = "entity_ref"
    SIMPLE_LIST = "simple_list"
    SCALE = "scale"
    TAG = "tag"
    STATE = "state"
    URL = "url"
    SOURCE_REF = "source_ref"


# ---------------------------------------------------------------------------
# CustomEntityType (§8.2)
# ---------------------------------------------------------------------------


@dataclass
class CustomEntityType:
    """A user-defined entity type that coexists with built-in ``EntityType``.

    Attributes:
        id: Unique identifier (UUID hex).
        name: Display name (e.g. ``"nave_espacial"``).
        description: Optional description.
        base_category: Optional built-in ``EntityType`` this custom type
            extends (e.g. ``EntityType.OBJETO`` for custom equipment).
        icon: Placeholder for future visual representation.
        color: Placeholder for future visual styling.
        custom_fields: IDs of ``CustomFieldDefinition`` associated with
            this type.
        suggested_relations: IDs of ``CustomRelationType`` suggested for
            entities of this type.
        participates_in_filters: Whether this type appears in filter UIs.
        participates_in_export: Whether entities of this type are included
            in exports.
        participates_in_ai: Whether AI assistants should consider this type.
        participates_in_consistency: Whether the consistency engine should
            validate entities of this type.
        is_active: Soft-delete flag. Inactive types are hidden from lists
            by default but still accessible by ID.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    base_category: Any | None = None  # EntityType | None (avoid circular import)
    icon: str = ""
    color: str = ""
    custom_fields: list[str] = field(default_factory=list)
    suggested_relations: list[str] = field(default_factory=list)
    participates_in_filters: bool = True
    participates_in_export: bool = True
    participates_in_ai: bool = True
    participates_in_consistency: bool = True
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for persistence."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "base_category": self.base_category.value
            if hasattr(self.base_category, "value") else self.base_category,
            "icon": self.icon,
            "color": self.color,
            "custom_fields": list(self.custom_fields),
            "suggested_relations": list(self.suggested_relations),
            "participates_in_filters": self.participates_in_filters,
            "participates_in_export": self.participates_in_export,
            "participates_in_ai": self.participates_in_ai,
            "participates_in_consistency": self.participates_in_consistency,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomEntityType:
        """Deserialize from a plain dict."""
        return cls(
            id=data.get("id") or uuid.uuid4().hex[:12],
            name=data.get("name", ""),
            description=data.get("description", ""),
            base_category=data.get("base_category"),
            icon=data.get("icon", ""),
            color=data.get("color", ""),
            custom_fields=data.get("custom_fields", []),
            suggested_relations=data.get("suggested_relations", []),
            participates_in_filters=data.get("participates_in_filters", True),
            participates_in_export=data.get("participates_in_export", True),
            participates_in_ai=data.get("participates_in_ai", True),
            participates_in_consistency=data.get("participates_in_consistency", True),
            is_active=data.get("is_active", True),
        )


# ---------------------------------------------------------------------------
# CustomFieldDefinition (§8.3)
# ---------------------------------------------------------------------------


@dataclass
class CustomFieldDefinition:
    """Defines a custom field that can be attached to entities or relations.

    Attributes:
        id: Unique identifier (UUID hex).
        name: Display name (e.g. ``"nivel_de_poder"``).
        field_type: The ``FieldType`` that determines validation and UI.
        description: Optional description.
        required: Whether this field must have a value.
        default_value: Default value if none is provided.
        options: Valid choices for ``SINGLE_SELECT`` / ``MULTI_SELECT``.
        min_value: Minimum allowed value for ``NUMBER`` / ``SCALE``.
        max_value: Maximum allowed value for ``NUMBER`` / ``SCALE``.
        target_entity_types: Allowed entity type IDs for ``ENTITY_REF``.
        order: Display order in UI.
        metadata: Extensible key-value metadata.
        is_active: Soft-delete flag.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    field_type: FieldType = FieldType.TEXT_SHORT
    description: str = ""
    required: bool = False
    default_value: Any = None
    options: list[str] = field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    target_entity_types: list[str] = field(default_factory=list)
    order: int = 0
    metadata: dict[str, str] = field(default_factory=dict)
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for persistence."""
        return {
            "id": self.id,
            "name": self.name,
            "field_type": self.field_type.value,
            "description": self.description,
            "required": self.required,
            "default_value": self.default_value,
            "options": list(self.options),
            "min_value": self.min_value,
            "max_value": self.max_value,
            "target_entity_types": list(self.target_entity_types),
            "order": self.order,
            "metadata": dict(self.metadata),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomFieldDefinition:
        """Deserialize from a plain dict."""
        ft_raw = data.get("field_type", "text_short")
        ft = FieldType(ft_raw) if isinstance(ft_raw, str) else ft_raw
        return cls(
            id=data.get("id") or uuid.uuid4().hex[:12],
            name=data.get("name", ""),
            field_type=ft,
            description=data.get("description", ""),
            required=data.get("required", False),
            default_value=data.get("default_value"),
            options=data.get("options", []),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            target_entity_types=data.get("target_entity_types", []),
            order=data.get("order", 0),
            metadata=data.get("metadata", {}),
            is_active=data.get("is_active", True),
        )


# ---------------------------------------------------------------------------
# CustomRelationType (§8.4)
# ---------------------------------------------------------------------------


@dataclass
class CustomRelationType:
    """A user-defined relation type that coexists with built-in ``RelationType``.

    Attributes:
        id: Unique identifier (UUID hex).
        name: Display name (e.g. ``"fue_discipulo_de"``).
        description: Optional description.
        default_direction: Default directionality.
        allowed_source_types: IDs of entity types allowed as source.
        allowed_target_types: IDs of entity types allowed as target.
        visual_representation: Placeholder for future visual styling.
        participates_in_consistency: Whether the consistency engine should
            validate relations of this type.
        participates_in_ai: Whether AI assistants should consider this type.
        custom_fields: IDs of ``CustomFieldDefinition`` associated with
            this relation type.
        is_active: Soft-delete flag.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    description: str = ""
    default_direction: str = "unidireccional"
    allowed_source_types: list[str] = field(default_factory=list)
    allowed_target_types: list[str] = field(default_factory=list)
    visual_representation: str = ""
    participates_in_consistency: bool = True
    participates_in_ai: bool = True
    custom_fields: list[str] = field(default_factory=list)
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for persistence."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "default_direction": self.default_direction,
            "allowed_source_types": list(self.allowed_source_types),
            "allowed_target_types": list(self.allowed_target_types),
            "visual_representation": self.visual_representation,
            "participates_in_consistency": self.participates_in_consistency,
            "participates_in_ai": self.participates_in_ai,
            "custom_fields": list(self.custom_fields),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomRelationType:
        """Deserialize from a plain dict."""
        return cls(
            id=data.get("id") or uuid.uuid4().hex[:12],
            name=data.get("name", ""),
            description=data.get("description", ""),
            default_direction=data.get("default_direction", "unidireccional"),
            allowed_source_types=data.get("allowed_source_types", []),
            allowed_target_types=data.get("allowed_target_types", []),
            visual_representation=data.get("visual_representation", ""),
            participates_in_consistency=data.get("participates_in_consistency", True),
            participates_in_ai=data.get("participates_in_ai", True),
            custom_fields=data.get("custom_fields", []),
            is_active=data.get("is_active", True),
        )


# ---------------------------------------------------------------------------
# CustomFieldValue
# ---------------------------------------------------------------------------


@dataclass
class CustomFieldValue:
    """A concrete value assigned to a custom field on an entity or relation.

    Attributes:
        field_id: ID of the ``CustomFieldDefinition`` this value belongs to.
        value: The actual value, typed according to the definition's
            ``FieldType``.
    """

    field_id: str = ""
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for persistence."""
        return {"field_id": self.field_id, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomFieldValue:
        """Deserialize from a plain dict."""
        return cls(
            field_id=data.get("field_id", ""),
            value=data.get("value"),
        )


__all__ = [
    "CustomEntityType",
    "CustomFieldDefinition",
    "CustomFieldValue",
    "CustomRelationType",
    "FieldType",
]
