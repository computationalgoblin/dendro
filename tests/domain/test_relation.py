"""Tests for B04-T01: NarrativeRelation domain model."""

from datetime import datetime, timezone

from packages.domain.entity import CanonState, CertaintyLevel, VisibilityState
from packages.domain.relation import (
    Direction,
    IntensityLevel,
    NarrativeRelation,
    RelationType,
    validate_relation,
)


# -----------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------


class TestRelationType:
    def test_has_27_values(self):
        assert len(RelationType) == 27

    def test_known_values(self):
        assert RelationType.PERTENECE_A.value == "pertenece_a"
        assert RelationType.ES_ENEMIGO_DE.value == "es_enemigo_de"
        assert RelationType.ESTA_RELACIONADO_CON.value == "esta_relacionado_con"


class TestDirection:
    def test_has_2_values(self):
        assert len(Direction) == 2


class TestIntensityLevel:
    def test_has_6_values(self):
        assert len(IntensityLevel) == 6


# -----------------------------------------------------------------------
# Entity creation
# -----------------------------------------------------------------------


class TestRelationCreation:
    def test_defaults(self):
        r = NarrativeRelation()
        assert r.source_id == ""
        assert r.target_id == ""
        assert r.relation_type == RelationType.ESTA_RELACIONADO_CON
        assert r.direction == Direction.UNIDIRECCIONAL
        assert r.intensity == IntensityLevel.MEDIA
        assert r.canon_state == CanonState.BORRADOR
        assert r.visibility_state == VisibilityState.VISIBLE_USUARIO
        assert r.certainty_level == CertaintyLevel.PROBABLE
        assert isinstance(r.created_at, datetime)

    def test_id_is_unique(self):
        r1 = NarrativeRelation()
        r2 = NarrativeRelation()
        assert r1.id != r2.id

    def test_17_fields(self):
        r = NarrativeRelation(source_id="a", target_id="b")
        d = r.to_dict()
        assert len(d) == 17, f"Expected 17, got {len(d)}: {list(d.keys())}"

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        r = NarrativeRelation(
            id="r1",
            source_id="e1",
            target_id="e2",
            relation_type=RelationType.ES_ALIADO_DE,
            direction=Direction.BIDIRECCIONAL,
            description="Strong alliance",
            intensity=IntensityLevel.ALTA,
            temporality="ancient",
            causality="treaty",
            canon_state=CanonState.CANONICO,
            visibility_state=VisibilityState.VISIBLE_JUGADORES,
            certainty_level=CertaintyLevel.CONFIRMADO,
            source="Manual",
            created_at=now,
            updated_at=now,
            conditions="while the treaty holds",
            custom_metadata={"key": "val"},
        )
        assert r.relation_type == RelationType.ES_ALIADO_DE
        assert r.temporality == "ancient"


# -----------------------------------------------------------------------
# Serialisation
# -----------------------------------------------------------------------


class TestSerialisation:
    def test_roundtrip_full(self):
        r1 = NarrativeRelation(
            source_id="e1",
            target_id="e2",
            relation_type=RelationType.CONTROLA,
            direction=Direction.UNIDIRECCIONAL,
            description="Mind control",
            intensity=IntensityLevel.ALTA,
            temporality="recent",
            causality="spell",
            canon_state=CanonState.CANONICO,
            source="Written by DM",
            conditions="breaks at dawn",
            custom_metadata={"notes": "important"},
        )
        d = r1.to_dict()
        r2 = NarrativeRelation.from_dict(d)
        assert r2.source_id == r1.source_id
        assert r2.target_id == r1.target_id
        assert r2.relation_type == r1.relation_type
        assert r2.direction == r1.direction
        assert r2.intensity == r1.intensity
        assert r2.canon_state == r1.canon_state
        assert r2.custom_metadata == r1.custom_metadata

    def test_from_dict_partial(self):
        d = {"source_id": "a", "target_id": "b", "relation_type": "es_enemigo_de"}
        r = NarrativeRelation.from_dict(d)
        assert r.source_id == "a"
        assert r.relation_type == RelationType.ES_ENEMIGO_DE
        assert r.description == ""

    def test_from_dict_empty(self):
        r = NarrativeRelation.from_dict({})
        assert r.id != ""
        assert r.source_id == ""

    def test_from_dict_invalid_enum(self):
        r = NarrativeRelation.from_dict({"relation_type": "nonexistent"})
        assert r.relation_type == RelationType.ESTA_RELACIONADO_CON

    def test_reuses_entity_enums(self):
        r = NarrativeRelation(canon_state=CanonState.CANONICO)
        assert r.canon_state == CanonState.CANONICO
        r2 = NarrativeRelation.from_dict(
            {"canon_state": "secreto_canonico", "visibility_state": "revelado"}
        )
        assert r2.canon_state == CanonState.SECRETO_CANONICO
        assert r2.visibility_state == VisibilityState.REVELADO


# -----------------------------------------------------------------------
# touch
# -----------------------------------------------------------------------


class TestTouch:
    def test_updates_updated_at(self):
        import time

        r = NarrativeRelation()
        orig = r.updated_at
        time.sleep(0.01)
        r.touch()
        assert r.updated_at > orig


# -----------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------


class TestValidateRelation:
    def test_valid(self):
        r = NarrativeRelation(source_id="e1", target_id="e2")
        assert validate_relation(r) == []

    def test_empty_source_id(self):
        r = NarrativeRelation(target_id="e2")
        issues = validate_relation(r)
        assert any("source_id" in i.lower() for i in issues)

    def test_empty_target_id(self):
        r = NarrativeRelation(source_id="e1")
        issues = validate_relation(r)
        assert any("target_id" in i.lower() for i in issues)
