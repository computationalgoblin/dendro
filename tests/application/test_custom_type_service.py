"""
Tests for custom type application services (B08-T03) — CustomTypeService CRUD,
entity/relation custom field assignment, and field value validation.
"""

from __future__ import annotations

from pathlib import Path

from packages.application.custom_type_service import CustomTypeService
from packages.application.entity_service import EntityService
from packages.application.project_service import ProjectService
from packages.application.relation_service import RelationService
from packages.domain.custom_types import (
    FieldType,
)
from packages.domain.result import Error, Ok
from packages.persistence.store import ProjectStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _setup_services():
    """Create ProjectService, EntityService, RelationService, CustomTypeService."""
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Test")
    es = EntityService(project_service=ps, store=store)
    rs = RelationService(project_service=ps, store=store)
    cts = CustomTypeService(project_service=ps)
    return ps, es, rs, cts


# ---------------------------------------------------------------------------
# CustomEntityType CRUD
# ---------------------------------------------------------------------------


class TestCustomEntityTypeCRUD:
    def test_create_and_list(self) -> None:
        _, _, _, cts = _setup_services()
        result = cts.create_entity_type({"name": "Starship"})
        assert isinstance(result, Ok)
        assert result.value.name == "Starship"

        types = cts.list_entity_types()
        assert isinstance(types, Ok)
        assert len(types.value) == 1

    def test_create_empty_name(self) -> None:
        _, _, _, cts = _setup_services()
        result = cts.create_entity_type({"name": "  "})
        assert isinstance(result, Error)

    def test_update(self) -> None:
        _, _, _, cts = _setup_services()
        created = cts.create_entity_type({"name": "Old"})
        tid = created.value.id

        updated = cts.update_entity_type(tid, {"name": "New"})
        assert isinstance(updated, Ok)
        assert updated.value.name == "New"

    def test_delete_soft(self) -> None:
        _, _, _, cts = _setup_services()
        created = cts.create_entity_type({"name": "Gone"})
        tid = created.value.id

        cts.delete_entity_type(tid)

        # Not in active list
        types = cts.list_entity_types()
        assert len(types.value) == 0

        # But still accessible by ID
        found = cts.get_entity_type(tid)
        assert isinstance(found, Ok)
        assert found.value.is_active is False

    def test_list_include_inactive(self) -> None:
        _, _, _, cts = _setup_services()
        cts.create_entity_type({"name": "Active"})
        created = cts.create_entity_type({"name": "Inactive"})
        cts.delete_entity_type(created.value.id)

        all_types = cts.list_entity_types(include_inactive=True)
        assert len(all_types.value) == 2


# ---------------------------------------------------------------------------
# CustomFieldDefinition CRUD
# ---------------------------------------------------------------------------


class TestCustomFieldDefinitionCRUD:
    def test_create_number_field(self) -> None:
        _, _, _, cts = _setup_services()
        result = cts.create_field_definition({
            "name": "power", "field_type": FieldType.NUMBER,
            "min_value": 0, "max_value": 9999,
        })
        assert isinstance(result, Ok)
        assert result.value.field_type == FieldType.NUMBER

    def test_create_select_field(self) -> None:
        _, _, _, cts = _setup_services()
        result = cts.create_field_definition({
            "name": "color", "field_type": FieldType.SINGLE_SELECT,
            "options": ["red", "blue"],
        })
        assert result.value.options == ["red", "blue"]

    def test_delete_soft(self) -> None:
        _, _, _, cts = _setup_services()
        created = cts.create_field_definition({
            "name": "obsolete", "field_type": FieldType.TEXT_SHORT,
        })
        cts.delete_field_definition(created.value.id)

        active = cts.list_field_definitions()
        assert len(active.value) == 0

    def test_list_filtered_by_entity_type(self) -> None:
        _, _, _, cts = _setup_services()
        ct = cts.create_entity_type({"name": "Spaceship"}).value
        fd = cts.create_field_definition({
            "name": "speed", "field_type": FieldType.NUMBER,
        }).value

        # Associate field with entity type
        cts.update_entity_type(ct.id, {"custom_fields": [fd.id]})

        result = cts.list_field_definitions(entity_type_id=ct.id)
        assert len(result.value) == 1
        assert result.value[0].name == "speed"


# ---------------------------------------------------------------------------
# CustomRelationType CRUD
# ---------------------------------------------------------------------------


class TestCustomRelationTypeCRUD:
    def test_create_and_list(self) -> None:
        _, _, _, cts = _setup_services()
        result = cts.create_relation_type({
            "name": "docks_at",
            "allowed_source_types": ["Starship"],
        })
        assert isinstance(result, Ok)

        types = cts.list_relation_types()
        assert len(types.value) == 1

    def test_delete_soft(self) -> None:
        _, _, _, cts = _setup_services()
        created = cts.create_relation_type({"name": "obsolete"})
        cts.delete_relation_type(created.value.id)

        active = cts.list_relation_types()
        assert len(active.value) == 0

        all_types = cts.list_relation_types(include_inactive=True)
        assert len(all_types.value) == 1


# ---------------------------------------------------------------------------
# Entity custom field assignment
# ---------------------------------------------------------------------------


class TestEntityCustomFields:
    def test_set_and_get_custom_field(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "power", "field_type": FieldType.NUMBER,
        }).value
        entity = es.create_entity({"name": "Hero", "entity_type": "personaje"}).value

        result = es.set_custom_field(
            entity.id, fd.id, 9000, custom_type_service=cts,
        )
        assert isinstance(result, Ok)

        fields = es.get_custom_fields(entity.id)
        assert isinstance(fields, Ok)
        assert len(fields.value) == 1
        assert fields.value[0].field_id == fd.id
        assert fields.value[0].value == 9000

    def test_set_field_overwrites(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "x", "field_type": FieldType.NUMBER,
        }).value
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        es.set_custom_field(entity.id, fd.id, 1, custom_type_service=cts)
        es.set_custom_field(entity.id, fd.id, 2, custom_type_service=cts)

        fields = es.get_custom_fields(entity.id)
        assert len(fields.value) == 1
        assert fields.value[0].value == 2

    def test_remove_custom_field(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "temp", "field_type": FieldType.TEXT_SHORT,
        }).value
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        es.set_custom_field(entity.id, fd.id, "hello", custom_type_service=cts)
        es.remove_custom_field(entity.id, fd.id)

        fields = es.get_custom_fields(entity.id)
        assert len(fields.value) == 0

    def test_multiple_fields(self) -> None:
        ps, es, _, cts = _setup_services()
        fd1 = cts.create_field_definition({
            "name": "a", "field_type": FieldType.NUMBER,
        }).value
        fd2 = cts.create_field_definition({
            "name": "b", "field_type": FieldType.BOOLEAN,
        }).value
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        es.set_custom_field(entity.id, fd1.id, 42, custom_type_service=cts)
        es.set_custom_field(entity.id, fd2.id, True, custom_type_service=cts)

        fields = es.get_custom_fields(entity.id)
        assert len(fields.value) == 2


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestFieldValidation:
    def test_number_rejects_string(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "n", "field_type": FieldType.NUMBER,
        }).value
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        result = es.set_custom_field(
            entity.id, fd.id, "not-a-number", custom_type_service=cts,
        )
        assert isinstance(result, Error)

    def test_boolean_rejects_string(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "flag", "field_type": FieldType.BOOLEAN,
        }).value
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        result = es.set_custom_field(
            entity.id, fd.id, "not-bool", custom_type_service=cts,
        )
        assert isinstance(result, Error)

    def test_single_select_rejects_invalid(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "color", "field_type": FieldType.SINGLE_SELECT,
            "options": ["red", "blue"],
        }).value
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        result = es.set_custom_field(
            entity.id, fd.id, "green", custom_type_service=cts,
        )
        assert isinstance(result, Error)

    def test_multi_select_rejects_invalid_element(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "colors", "field_type": FieldType.MULTI_SELECT,
            "options": ["red", "blue"],
        }).value
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        result = es.set_custom_field(
            entity.id, fd.id, ["red", "green"], custom_type_service=cts,
        )
        assert isinstance(result, Error)

    def test_entity_ref_rejects_nonexistent(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "owner", "field_type": FieldType.ENTITY_REF,
        }).value
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        result = es.set_custom_field(
            entity.id, fd.id, "does-not-exist", custom_type_service=cts,
        )
        assert isinstance(result, Error)

    def test_text_short_accepts_any_string(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "note", "field_type": FieldType.TEXT_SHORT,
        }).value
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        result = es.set_custom_field(
            entity.id, fd.id, "anything goes", custom_type_service=cts,
        )
        assert isinstance(result, Ok)

    def test_inactive_field_definition_rejected(self) -> None:
        ps, es, _, cts = _setup_services()
        fd = cts.create_field_definition({
            "name": "old", "field_type": FieldType.TEXT_SHORT,
        }).value
        cts.delete_field_definition(fd.id)
        entity = es.create_entity({"name": "E", "entity_type": "personaje"}).value

        result = es.set_custom_field(
            entity.id, fd.id, "test", custom_type_service=cts,
        )
        assert isinstance(result, Error)


# ---------------------------------------------------------------------------
# Relation custom field assignment
# ---------------------------------------------------------------------------


class TestRelationCustomFields:
    def test_set_and_get(self) -> None:
        ps, es, rs, cts = _setup_services()
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        rel = rs.create_relation(
            source_id=e1.id, target_id=e2.id,
            relation_type="es_aliado_de",
        ).value
        fd = cts.create_field_definition({
            "name": "strength", "field_type": FieldType.NUMBER,
        }).value

        result = rs.set_custom_field(rel.id, fd.id, 5, custom_type_service=cts)
        assert isinstance(result, Ok)

        fields = rs.get_custom_fields(rel.id)
        assert len(fields.value) == 1
        assert fields.value[0].value == 5

    def test_remove(self) -> None:
        ps, es, rs, cts = _setup_services()
        e1 = es.create_entity({"name": "A", "entity_type": "personaje"}).value
        e2 = es.create_entity({"name": "B", "entity_type": "personaje"}).value
        rel = rs.create_relation(
            source_id=e1.id, target_id=e2.id,
            relation_type="es_aliado_de",
        ).value
        fd = cts.create_field_definition({
            "name": "temp", "field_type": FieldType.TEXT_SHORT,
        }).value

        rs.set_custom_field(rel.id, fd.id, "x", custom_type_service=cts)
        rs.remove_custom_field(rel.id, fd.id)

        fields = rs.get_custom_fields(rel.id)
        assert len(fields.value) == 0


# ---------------------------------------------------------------------------
# Persistence integration
# ---------------------------------------------------------------------------


def test_custom_fields_survive_save_load(tmp_path: Path) -> None:
    """Entity with custom fields survives project save + reload."""
    store = ProjectStore()
    ps = ProjectService(store=store)
    ps.create(name="Test")
    es = EntityService(project_service=ps, store=store)
    cts = CustomTypeService(project_service=ps)

    fd = cts.create_field_definition({
        "name": "speed", "field_type": FieldType.NUMBER,
    }).value
    entity = es.create_entity({"name": "Ship", "entity_type": "personaje"}).value
    es.set_custom_field(entity.id, fd.id, 9000, custom_type_service=cts)

    # Save and reload
    path = tmp_path / "test.json"
    ps.save(path)
    ps.close()

    ps2 = ProjectService(store=store)
    ps2.open(path)
    es2 = EntityService(project_service=ps2, store=store)

    fields = es2.get_custom_fields(entity.id)
    assert len(fields.value) == 1
    assert fields.value[0].value == 9000
