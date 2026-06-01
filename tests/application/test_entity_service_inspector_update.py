from __future__ import annotations

from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.persistence.store import ProjectStore
from packages.domain.entity import CanonState, EntityType, VisibilityState
from packages.domain.result import Ok


def test_update_entity_accepts_complete_inspector_fields():
    ps = ProjectService(store=ProjectStore())
    created = ps.create("InspectorTest")
    assert isinstance(created, Ok)
    service = EntityService(ps)
    entity_result = service.create_entity({"name": "Old", "entity_type": "personaje"})
    assert isinstance(entity_result, Ok)
    entity = entity_result.value

    result = service.update_entity(entity.id, {
        "name": "New",
        "aliases": ["A", "B"],
        "entity_type": "localizacion",
        "brief_description": "brief",
        "extended_description": "extended",
        "canon_state": "canonico",
        "visibility_state": "publico_mundo",
        "certainty_level": "confirmado",
        "tags": ["t1", "t2"],
        "domain": "world",
        "layers": ["politics"],
        "origin": "manual",
        "domain_ids": ["d1"],
        "layer_ids": ["l1"],
        "private_notes": "private",
        "exportable_notes": "public",
        "narrative_importance": "critico",
        "development_level": "completo",
        "custom_metadata": {"k": "v"},
        "custom_type_id": "ct1",
        "custom_fields": [{"field_id": "f1", "value": "v1"}],
    })

    assert isinstance(result, Ok)
    updated = result.value
    assert updated.name == "New"
    assert updated.aliases == ["A", "B"]
    assert updated.entity_type == EntityType.LOCALIZACION
    assert updated.canon_state == CanonState.CANONICO
    assert updated.visibility_state == VisibilityState.PUBLICO_MUNDO
    assert updated.tags == ["t1", "t2"]
    assert updated.layers == ["politics"]
    assert updated.domain_ids == ["d1"]
    assert updated.layer_ids == ["l1"]
    assert updated.custom_metadata == {"k": "v"}
    assert updated.custom_type_id == "ct1"
    assert [field.to_dict() if hasattr(field, "to_dict") else field for field in updated.custom_fields] == [{"field_id": "f1", "value": "v1"}]
