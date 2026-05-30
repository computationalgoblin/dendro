"""
Narrative Framework — domain model (Bloque 13).

Provides FrameworkType, FrameworkGapSeverity, FrameworkComponent
and NarrativeFramework dataclasses with to_dict/from_dict.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FrameworkType(str, Enum):
    """14 tipos de marco narrativo."""
    HISTORIA = 'historia'
    ARCO_PERSONAJE = 'arco_personaje'
    CAMPANA = 'campana'
    MISTERIO = 'misterio'
    INVESTIGACION = 'investigacion'
    HORROR = 'horror'
    TRAGEDIA = 'tragedia'
    AVENTURA = 'aventura'
    SANDBOX = 'sandbox'
    FACCIONES = 'facciones'
    EPISODICA = 'episodica'
    REVELACION = 'revelacion'
    CONSPIRACION = 'conspiracion'
    PERSONALIZADA = 'personalizada'


class FrameworkGapSeverity(str, Enum):
    BAJA = 'baja'
    MEDIA = 'media'
    ALTA = 'alta'


def _new_id():
    return uuid.uuid4().hex[:12]


def _parse_enum(enum_cls, value, default):
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    return default


def _parse_list(value):
    if isinstance(value, list):
        return list(value)
    return []


@dataclass
class FrameworkComponent:
    id: str = field(default_factory=_new_id)
    name: str = ''
    description: str = ''
    expected_entity_types: list = field(default_factory=list)
    expected_relation_types: list = field(default_factory=list)
    is_optional: bool = False
    associated_entity_ids: list = field(default_factory=list)
    associated_relation_ids: list = field(default_factory=list)
    absence_deliberate: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'description': self.description,
            'expected_entity_types': list(self.expected_entity_types),
            'expected_relation_types': list(self.expected_relation_types),
            'is_optional': self.is_optional,
            'associated_entity_ids': list(self.associated_entity_ids),
            'associated_relation_ids': list(self.associated_relation_ids),
            'absence_deliberate': self.absence_deliberate,
            'metadata': dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get('id') or _new_id(),
            name=data.get('name', ''), description=data.get('description', ''),
            expected_entity_types=_parse_list(data.get('expected_entity_types')),
            expected_relation_types=_parse_list(data.get('expected_relation_types')),
            is_optional=data.get('is_optional', False),
            associated_entity_ids=_parse_list(data.get('associated_entity_ids')),
            associated_relation_ids=_parse_list(data.get('associated_relation_ids')),
            absence_deliberate=data.get('absence_deliberate', False),
            metadata=dict(data.get('metadata', {})),
        )


@dataclass
class NarrativeFramework:
    id: str = field(default_factory=_new_id)
    name: str = ''
    description: str = ''
    framework_type: FrameworkType = FrameworkType.PERSONALIZADA
    components: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    expected_fields: list = field(default_factory=list)
    suggested_relations: list = field(default_factory=list)
    domain_id: str | None = None
    layer_ids: list = field(default_factory=list)
    is_active: bool = False
    gap_severity: FrameworkGapSeverity = FrameworkGapSeverity.MEDIA
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'description': self.description,
            'framework_type': self.framework_type.value,
            'components': [c.to_dict() for c in self.components],
            'rules': list(self.rules),
            'expected_fields': list(self.expected_fields),
            'suggested_relations': list(self.suggested_relations),
            'domain_id': self.domain_id, 'layer_ids': list(self.layer_ids),
            'is_active': self.is_active,
            'gap_severity': self.gap_severity.value,
            'metadata': dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get('id') or _new_id(),
            name=data.get('name', ''), description=data.get('description', ''),
            framework_type=_parse_enum(FrameworkType, data.get('framework_type'), FrameworkType.PERSONALIZADA),
            components=[FrameworkComponent.from_dict(c) for c in _parse_list(data.get('components'))],
            rules=_parse_list(data.get('rules')),
            expected_fields=_parse_list(data.get('expected_fields')),
            suggested_relations=_parse_list(data.get('suggested_relations')),
            domain_id=data.get('domain_id'),
            layer_ids=_parse_list(data.get('layer_ids')),
            is_active=data.get('is_active', False),
            gap_severity=_parse_enum(FrameworkGapSeverity, data.get('gap_severity'), FrameworkGapSeverity.MEDIA),
            metadata=dict(data.get('metadata', {})),
        )


__all__ = ['FrameworkType', 'FrameworkGapSeverity', 'FrameworkComponent', 'NarrativeFramework']
