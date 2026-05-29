"""
Tests for custom types and fields domain models (B08-T01).
"""

from __future__ import annotations

from packages.domain.custom_types import (
    CustomEntityType,
    CustomFieldDefinition,
    CustomFieldValue,
    CustomRelationType,
    FieldType,
)
from packages.domain.entity import EntityType, NarrativeEntity
from packages.domain.relation import NarrativeRelation

# ---------------------------------------------------------------------------
# FieldType
# ---------------------------------------------------------------------------


class TestFieldType:
    def test_all_15_values_exist(self) -> None:
        values = {e.value for e in FieldType}
        assert len(values) == 15
        assert "text_short" in values
        assert "number" in values
        assert "boolean" in values
        assert "single_select" in values
        assert "entity_ref" in values
        assert "url" in values
        assert "source_ref" in values

    def test_from_string(self) -> None:
        assert FieldType("number") == FieldType.NUMBER
        assert FieldType("boolean") == FieldType.BOOLEAN


# ---------------------------------------------------------------------------
# CustomEntityType
# ---------------------------------------------------------------------------


class TestCustomEntityType:
    def test_defaults(self) -> None:
        ct = CustomEntityType()
        assert ct.id
        assert ct.name == ""
        assert ct.is_active is True
        assert ct.participates_in_filters is True
        assert ct.custom_fields == []

    def test_full_construction(self) -> None:
        ct = CustomEntityType(
            name="nave_espacial",
            description="Naves del universo",
            base_category=EntityType.OBJETO,
            icon="🚀",
            color="#FF0000",
            custom_fields=["f1", "f2"],
            suggested_relations=["r1"],
            participates_in_filters=True,
            participates_in_export=False,
            participates_in_ai=True,
            participates_in_consistency=True,
            is_active=True,
        )
        assert ct.name == "nave_espacial"
        assert ct.base_category == EntityType.OBJETO
        assert ct.custom_fields == ["f1", "f2"]
        assert ct.participates_in_export is False

    def test_soft_delete(self) -> None:
        ct = CustomEntityType(name="test", is_active=False)
        assert ct.is_active is False

    def test_roundtrip_dict(self) -> None:
        ct = CustomEntityType(
            id="abc123",
            name="test_type",
            description="desc",
            base_category=EntityType.PERSONAJE,
            custom_fields=["f1"],
            suggested_relations=["r1"],
            is_active=True,
        )
        d = ct.to_dict()
        ct2 = CustomEntityType.from_dict(d)
        assert ct2.id == "abc123"
        assert ct2.name == "test_type"
        assert ct2.custom_fields == ["f1"]
        assert ct2.is_active is True

    def test_roundtrip_base_category_none(self) -> None:
        ct = CustomEntityType(name="freestyle")
        d = ct.to_dict()
        ct2 = CustomEntityType.from_dict(d)
        assert ct2.base_category is None


# ---------------------------------------------------------------------------
# CustomFieldDefinition
# ---------------------------------------------------------------------------


class TestCustomFieldDefinition:
    def test_defaults(self) -> None:
        fd = CustomFieldDefinition()
        assert fd.id
        assert fd.field_type == FieldType.TEXT_SHORT
        assert fd.is_active is True

    def test_number_field(self) -> None:
        fd = CustomFieldDefinition(
            name="potencia",
            field_type=FieldType.NUMBER,
            min_value=0,
            max_value=9000,
        )
        assert fd.field_type == FieldType.NUMBER
        assert fd.min_value == 0
        assert fd.max_value == 9000

    def test_single_select(self) -> None:
        fd = CustomFieldDefinition(
            name="color",
            field_type=FieldType.SINGLE_SELECT,
            options=["rojo", "azul", "verde"],
        )
        assert fd.options == ["rojo", "azul", "verde"]

    def test_entity_ref(self) -> None:
        fd = CustomFieldDefinition(
            name="owner",
            field_type=FieldType.ENTITY_REF,
            target_entity_types=["PERSONAJE", "FACCION"],
        )
        assert fd.target_entity_types == ["PERSONAJE", "FACCION"]

    def test_roundtrip_all_field_types(self) -> None:
        for ft in FieldType:
            has_options = ft in (FieldType.SINGLE_SELECT, FieldType.MULTI_SELECT)
            fd = CustomFieldDefinition(
                id=f"fd_{ft.value}",
                name=ft.value,
                field_type=ft,
                options=["a", "b"] if has_options else [],
            )
            d = fd.to_dict()
            fd2 = CustomFieldDefinition.from_dict(d)
            assert fd2.field_type == ft
            assert fd2.id == f"fd_{ft.value}"

    def test_soft_delete(self) -> None:
        fd = CustomFieldDefinition(name="old_field", is_active=False)
        assert fd.is_active is False


# ---------------------------------------------------------------------------
# CustomRelationType
# ---------------------------------------------------------------------------


class TestCustomRelationType:
    def test_defaults(self) -> None:
        crt = CustomRelationType()
        assert crt.id
        assert crt.default_direction == "unidireccional"
        assert crt.is_active is True

    def test_full_construction(self) -> None:
        crt = CustomRelationType(
            name="fue_discipulo_de",
            description="Relación maestro-aprendiz",
            default_direction="unidireccional",
            allowed_source_types=["PERSONAJE"],
            allowed_target_types=["PERSONAJE"],
            visual_representation="→",
            participates_in_consistency=True,
            participates_in_ai=True,
            custom_fields=["f1"],
            is_active=True,
        )
        assert crt.name == "fue_discipulo_de"
        assert crt.allowed_source_types == ["PERSONAJE"]

    def test_soft_delete(self) -> None:
        crt = CustomRelationType(name="obsolete", is_active=False)
        assert crt.is_active is False

    def test_roundtrip_dict(self) -> None:
        crt = CustomRelationType(
            id="crt1",
            name="forma_parte_de",
            allowed_source_types=["PERSONAJE"],
            custom_fields=["f1"],
        )
        d = crt.to_dict()
        crt2 = CustomRelationType.from_dict(d)
        assert crt2.id == "crt1"
        assert crt2.name == "forma_parte_de"
        assert crt2.allowed_source_types == ["PERSONAJE"]


# ---------------------------------------------------------------------------
# CustomFieldValue
# ---------------------------------------------------------------------------


class TestCustomFieldValue:
    def test_string_value(self) -> None:
        cfv = CustomFieldValue(field_id="f1", value="hello")
        assert cfv.field_id == "f1"
        assert cfv.value == "hello"

    def test_int_value(self) -> None:
        cfv = CustomFieldValue(field_id="f1", value=42)
        assert cfv.value == 42

    def test_bool_value(self) -> None:
        cfv = CustomFieldValue(field_id="f1", value=True)
        assert cfv.value is True

    def test_list_value(self) -> None:
        cfv = CustomFieldValue(field_id="f1", value=["a", "b"])
        assert cfv.value == ["a", "b"]

    def test_roundtrip_string(self) -> None:
        cfv = CustomFieldValue(field_id="f1", value="test")
        d = cfv.to_dict()
        cfv2 = CustomFieldValue.from_dict(d)
        assert cfv2.field_id == "f1"
        assert cfv2.value == "test"


# ---------------------------------------------------------------------------
# NarrativeEntity custom fields
# ---------------------------------------------------------------------------


class TestNarrativeEntityCustomFields:
    def test_defaults(self) -> None:
        e = NarrativeEntity(name="Test")
        assert e.custom_type_id is None
        assert e.custom_fields == []

    def test_set_custom_type_id(self) -> None:
        e = NarrativeEntity(name="Test", custom_type_id="type_123")
        assert e.custom_type_id == "type_123"

    def test_add_custom_field(self) -> None:
        e = NarrativeEntity(name="Test")
        cfv = CustomFieldValue(field_id="f1", value=42)
        e.custom_fields.append(cfv)
        assert len(e.custom_fields) == 1
        assert e.custom_fields[0].value == 42

    def test_roundtrip_via_dict(self) -> None:
        e = NarrativeEntity(
            name="Test",
            custom_type_id="type_X",
        )
        cfv = CustomFieldValue(field_id="f1", value="hello")
        e.custom_fields.append(cfv)

        d = e.to_dict()
        assert d["custom_type_id"] == "type_X"
        assert len(d["custom_fields"]) == 1
        assert d["custom_fields"][0]["field_id"] == "f1"

        e2 = NarrativeEntity.from_dict(d)
        assert e2.custom_type_id == "type_X"
        assert len(e2.custom_fields) == 1
        assert e2.custom_fields[0].field_id == "f1"
        assert e2.custom_fields[0].value == "hello"

    def test_entity_without_custom_type_roundtrip(self) -> None:
        """Existing entities without custom_type_id should survive roundtrip."""
        e = NarrativeEntity(name="Old")
        d = e.to_dict()
        e2 = NarrativeEntity.from_dict(d)
        assert e2.custom_type_id is None
        assert e2.custom_fields == []


# ---------------------------------------------------------------------------
# NarrativeRelation custom fields
# ---------------------------------------------------------------------------


class TestNarrativeRelationCustomFields:
    def test_defaults(self) -> None:
        r = NarrativeRelation(source_id="a", target_id="b")
        assert r.custom_relation_type_id is None
        assert r.custom_fields == []

    def test_set_custom_relation_type_id(self) -> None:
        r = NarrativeRelation(
            source_id="a", target_id="b",
            custom_relation_type_id="rel_type_1",
        )
        assert r.custom_relation_type_id == "rel_type_1"

    def test_roundtrip_via_dict(self) -> None:
        r = NarrativeRelation(
            source_id="a",
            target_id="b",
            custom_relation_type_id="crt_1",
        )
        cfv = CustomFieldValue(field_id="f1", value=True)
        r.custom_fields.append(cfv)

        d = r.to_dict()
        assert d["custom_relation_type_id"] == "crt_1"
        assert d["custom_fields"][0]["value"] is True

        r2 = NarrativeRelation.from_dict(d)
        assert r2.custom_relation_type_id == "crt_1"
        assert r2.custom_fields[0].value is True
