"""
Tests for NarrativeFramework domain model (B13-T01).
"""

from packages.domain.narrative_framework import (
    FrameworkComponent,
    FrameworkGapSeverity,
    FrameworkType,
    NarrativeFramework,
)


class TestFrameworkType:
    def test_14_values(self) -> None:
        assert len(list(FrameworkType)) == 14

    def test_values_are_strings(self) -> None:
        for t in FrameworkType:
            assert isinstance(t.value, str)

    def test_personalizada_exists(self) -> None:
        assert FrameworkType.PERSONALIZADA.value == "personalizada"


class TestFrameworkGapSeverity:
    def test_3_levels(self) -> None:
        assert len(list(FrameworkGapSeverity)) == 3


class TestFrameworkComponent:
    def test_defaults(self) -> None:
        c = FrameworkComponent(name="Acto I")
        assert c.id != ""
        assert c.name == "Acto I"
        assert not c.is_optional
        assert not c.absence_deliberate
        assert c.associated_entity_ids == []
        assert c.metadata == {}

    def test_10_fields(self) -> None:
        c = FrameworkComponent(
            name="Acto I",
            description="Presentación del héroe",
            expected_entity_types=["personaje"],
            expected_relation_types=["es_aliado_de"],
            is_optional=False,
            associated_entity_ids=["e1"],
            associated_relation_ids=["r1"],
            absence_deliberate=False,
            metadata={"order": "1"},
        )
        d = c.to_dict()
        assert len(d) == 10
        assert d["name"] == "Acto I"
        assert d["metadata"]["order"] == "1"

    def test_to_dict_roundtrip(self) -> None:
        c = FrameworkComponent(
            name="Acto I",
            expected_entity_types=["personaje", "objeto"],
            is_optional=True,
            associated_entity_ids=["e1", "e2"],
            absence_deliberate=False,
            metadata={"source": "template"},
        )
        d = c.to_dict()
        c2 = FrameworkComponent.from_dict(d)
        assert c2.id == c.id
        assert c2.name == c.name
        assert c2.expected_entity_types == c.expected_entity_types
        assert c2.is_optional == c.is_optional
        assert c2.associated_entity_ids == c.associated_entity_ids
        assert c2.absence_deliberate == c.absence_deliberate
        assert c2.metadata == c.metadata

    def test_absence_deliberate_preserved(self) -> None:
        c = FrameworkComponent(name="Epílogo", absence_deliberate=True)
        d = c.to_dict()
        c2 = FrameworkComponent.from_dict(d)
        assert c2.absence_deliberate is True


class TestNarrativeFramework:
    def test_defaults(self) -> None:
        fw = NarrativeFramework(name="Viaje")
        assert fw.id != ""
        assert fw.name == "Viaje"
        assert fw.framework_type == FrameworkType.PERSONALIZADA
        assert fw.is_active is False
        assert fw.gap_severity == FrameworkGapSeverity.MEDIA
        assert fw.components == []

    def test_to_dict_roundtrip(self) -> None:
        fw = NarrativeFramework(
            name="El Viaje del Héroe",
            description="",
            framework_type=FrameworkType.HISTORIA,
            components=[
                FrameworkComponent(name="Acto I"),
                FrameworkComponent(name="Acto II"),
            ],
            rules=["tres actos"],
            expected_fields=["protagonista"],
            suggested_relations=["es_aliado_de"],
            domain_id="mundo",
            layer_ids=["layer_historia"],
            is_active=True,
            gap_severity=FrameworkGapSeverity.ALTA,
            metadata={"version": 1},
        )
        d = fw.to_dict()
        fw2 = NarrativeFramework.from_dict(d)
        assert fw2.id == fw.id
        assert fw2.name == fw.name
        assert fw2.framework_type == fw.framework_type
        assert len(fw2.components) == 2
        assert fw2.components[0].name == "Acto I"
        assert fw2.rules == ["tres actos"]
        assert fw2.is_active is True
        assert fw2.gap_severity == FrameworkGapSeverity.ALTA
        assert fw2.metadata == {"version": 1}

    def test_from_dict_tolerates_empty(self) -> None:
        fw = NarrativeFramework.from_dict({})
        assert fw.id != ""
        assert fw.name == ""
        assert fw.framework_type == FrameworkType.PERSONALIZADA
        assert fw.components == []

    def test_components_nested(self) -> None:
        fw = NarrativeFramework(
            components=[
                FrameworkComponent(
                    name="C1",
                    expected_entity_types=["personaje"],
                    metadata={"order": "1"},
                ),
            ],
        )
        d = fw.to_dict()
        fw2 = NarrativeFramework.from_dict(d)
        assert fw2.components[0].name == "C1"
        assert fw2.components[0].expected_entity_types == ["personaje"]
        assert fw2.components[0].metadata == {"order": "1"}
