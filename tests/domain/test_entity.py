"""Tests for B03-T01: NarrativeEntity domain model.

Covers:
- Enums (all 6, all values present)
- Entity creation with defaults
- Entity fields (20 fields)
- to_dict / from_dict roundtrip
- from_dict tolerance (missing keys)
- touch()
- validate_entity
- origin is a simple string
- No project_id attribute
"""

from datetime import datetime, timezone

from packages.domain.entity import (
    CanonState,
    CertaintyLevel,
    DevelopmentLevel,
    EntityType,
    NarrativeEntity,
    NarrativeImportance,
    VisibilityState,
    validate_entity,
)


# ═══════════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════════


class TestEntityType:
    def test_has_20_values(self):
        assert len(EntityType) == 21

    def test_known_values(self):
        assert EntityType.PERSONAJE.value == "personaje"
        assert EntityType.LOCALIZACION.value == "localizacion"
        assert EntityType.FACCION.value == "faccion"
        assert EntityType.NOTA.value == "nota"

    def test_from_string(self):
        assert EntityType("personaje") == EntityType.PERSONAJE


class TestCanonState:
    def test_has_14_values(self):
        # 13 originales (§3.4) + "fantasma" (BETA2-FOCO: nodos/relaciones fantasma).
        assert len(CanonState) == 14

    def test_archived_exists(self):
        assert CanonState.ARCHIVADO.value == "archivado"

    def test_fantasma_exists(self):
        assert CanonState.FANTASMA.value == "fantasma"

    def test_from_string(self):
        assert CanonState("borrador") == CanonState.BORRADOR


class TestVisibilityState:
    def test_has_14_values(self):
        assert len(VisibilityState) == 14

    def test_default_for_new_entities(self):
        e = NarrativeEntity()
        assert e.visibility_state == VisibilityState.VISIBLE_USUARIO


class TestCertaintyLevel:
    def test_has_5_values(self):
        assert len(CertaintyLevel) == 5


class TestNarrativeImportance:
    def test_has_5_values(self):
        assert len(NarrativeImportance) == 5


class TestDevelopmentLevel:
    def test_has_5_values(self):
        assert len(DevelopmentLevel) == 5


# ═══════════════════════════════════════════════════════════════════════
# Entity creation
# ═══════════════════════════════════════════════════════════════════════


class TestEntityCreation:
    def test_defaults(self):
        e = NarrativeEntity()
        assert e.name == ""
        assert e.aliases == []
        assert e.entity_type == EntityType.NOTA
        assert e.brief_description == ""
        assert e.extended_description == ""
        assert e.canon_state == CanonState.CANONICO
        assert e.visibility_state == VisibilityState.VISIBLE_USUARIO
        assert e.certainty_level == CertaintyLevel.PROBABLE
        assert e.tags == []
        assert e.domain == ""
        assert e.layers == []
        assert e.origin == ""
        assert isinstance(e.created_at, datetime)
        assert isinstance(e.updated_at, datetime)
        assert e.private_notes == ""
        assert e.exportable_notes == ""
        assert e.narrative_importance == NarrativeImportance.MEDIO
        assert e.development_level == DevelopmentLevel.SEMILLA
        assert e.custom_metadata == {}

    def test_id_is_unique_uuid4(self):
        e1 = NarrativeEntity()
        e2 = NarrativeEntity()
        assert e1.id != e2.id
        assert len(e1.id) == 36
        assert e1.id.count("-") == 4

    def test_20_fields(self):
        e = NarrativeEntity(name="Test")
        d = e.to_dict()
        # BETA1-J01: +life_span (lapso temporal rico). Guard reajustado al
        # conteo real (drift previo G02/G06 + life_span) → 27 campos.
        assert len(d) == 27, f"Expected 27 fields, got {len(d)}: {list(d.keys())}"

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        e = NarrativeEntity(
            id="abc-123",
            name="Eldrin",
            aliases=["The Wise"],
            entity_type=EntityType.PERSONAJE,
            brief_description="A powerful wizard",
            extended_description="Eldrin was born in...",
            canon_state=CanonState.CANONICO,
            visibility_state=VisibilityState.VISIBLE_USUARIO,
            certainty_level=CertaintyLevel.CONFIRMADO,
            tags=["wizard", "elder"],
            domain="fantasy",
            layers=["main", "backstory"],
            origin="Manual creation",
            created_at=now,
            updated_at=now,
            private_notes="Secret weakness: cats",
            exportable_notes="Public bio",
            narrative_importance=NarrativeImportance.ALTO,
            development_level=DevelopmentLevel.DESARROLLADO,
            custom_metadata={"wiki_page": "https://..."},
        )
        assert e.name == "Eldrin"
        assert e.canon_state == CanonState.CANONICO
        assert e.custom_metadata["wiki_page"] == "https://..."


# ═══════════════════════════════════════════════════════════════════════
# Serialisation
# ═══════════════════════════════════════════════════════════════════════


class TestSerialisation:
    def test_to_dict_uses_string_enums(self):
        e = NarrativeEntity(
            name="Test",
            entity_type=EntityType.PERSONAJE,
            canon_state=CanonState.CANONICO,
        )
        d = e.to_dict()
        assert d["entity_type"] == "personaje"
        assert d["canon_state"] == "canonico"

    def test_roundtrip_full(self):
        e1 = NarrativeEntity(
            name="Full Roundtrip",
            aliases=["FR", "Roundy"],
            entity_type=EntityType.LOCALIZACION,
            brief_description="A place",
            extended_description="A very detailed place",
            canon_state=CanonState.CANONICO,
            visibility_state=VisibilityState.VISIBLE_JUGADORES,
            certainty_level=CertaintyLevel.CONFIRMADO,
            tags=["geo", "important"],
            domain="sci-fi",
            layers=["surface", "underground", "orbit"],
            origin="Manual creation",
            private_notes="DM only",
            exportable_notes="Players can see this",
            narrative_importance=NarrativeImportance.CRITICO,
            development_level=DevelopmentLevel.COMPLETO,
            custom_metadata={"key": "value", "nested": {"a": 1}},
        )
        d = e1.to_dict()
        e2 = NarrativeEntity.from_dict(d)

        assert e2.name == e1.name
        assert e2.aliases == e1.aliases
        assert e2.entity_type == e1.entity_type
        assert e2.canon_state == e1.canon_state
        assert e2.visibility_state == e1.visibility_state
        assert e2.certainty_level == e1.certainty_level
        assert e2.tags == e1.tags
        assert e2.domain == e1.domain
        assert e2.layers == e1.layers
        assert e2.origin == e1.origin
        assert e2.private_notes == e1.private_notes
        assert e2.exportable_notes == e1.exportable_notes
        assert e2.narrative_importance == e1.narrative_importance
        assert e2.development_level == e1.development_level
        assert e2.custom_metadata == e1.custom_metadata

    def test_from_dict_partial(self):
        d = {"name": "Partial", "entity_type": "personaje"}
        e = NarrativeEntity.from_dict(d)
        assert e.name == "Partial"
        assert e.entity_type == EntityType.PERSONAJE
        assert e.brief_description == ""
        assert e.aliases == []
        assert e.canon_state == CanonState.CANONICO

    def test_from_dict_empty(self):
        e = NarrativeEntity.from_dict({})
        assert e.name == ""
        assert e.id != ""
        assert isinstance(e.created_at, datetime)

    def test_from_dict_invalid_enum(self):
        e = NarrativeEntity.from_dict({"entity_type": "nonexistent_type"})
        assert e.entity_type == EntityType.NOTA  # fallback

    def test_from_dict_invalid_list(self):
        e = NarrativeEntity.from_dict({"tags": "not_a_list"})
        assert e.tags == []

    def test_from_dict_invalid_dict(self):
        e = NarrativeEntity.from_dict({"custom_metadata": "not_a_dict"})
        assert e.custom_metadata == {}


# ═══════════════════════════════════════════════════════════════════════
# touch
# ═══════════════════════════════════════════════════════════════════════


class TestTouch:
    def test_touch_updates_updated_at(self):
        import time

        e = NarrativeEntity()
        original = e.updated_at
        time.sleep(0.01)
        e.touch()
        assert e.updated_at > original


# ═══════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════


class TestValidateEntity:
    def test_valid_entity_no_issues(self):
        e = NarrativeEntity(name="Valid Entity", entity_type=EntityType.LOCALIZACION)
        issues = validate_entity(e)
        assert issues == []

    def test_empty_name_detected(self):
        e = NarrativeEntity(name="")
        issues = validate_entity(e)
        assert len(issues) >= 1
        assert any("name" in iss.lower() for iss in issues)

    def test_whitespace_name_detected(self):
        e = NarrativeEntity(name="   ")
        issues = validate_entity(e)
        assert len(issues) >= 1

    def test_empty_id_detected(self):
        e = NarrativeEntity(id="")
        issues = validate_entity(e)
        assert any("id" in iss.lower() for iss in issues)


# ═══════════════════════════════════════════════════════════════════════
# Design constraints
# ═══════════════════════════════════════════════════════════════════════


class TestDesignConstraints:
    def test_origin_is_string(self):
        e = NarrativeEntity(origin="Manual entry")
        assert isinstance(e.origin, str)
        assert e.origin == "Manual entry"

    def test_origin_default_is_empty_string(self):
        e = NarrativeEntity()
        assert e.origin == ""

    def test_no_project_id_attribute(self):
        e = NarrativeEntity()
        assert not hasattr(e, "project_id"), (
            "NarrativeEntity must NOT have project_id; pertenencia is by containment"
        )

    def test_layers_is_list_of_strings(self):
        e = NarrativeEntity(layers=["main", "side"])
        assert isinstance(e.layers, list)
        assert all(isinstance(v, str) for v in e.layers)

    def test_tags_is_list_of_strings(self):
        e = NarrativeEntity(tags=["tag1", "tag2"])
        assert isinstance(e.tags, list)
        assert all(isinstance(v, str) for v in e.tags)

    def test_aliases_is_list_of_strings(self):
        e = NarrativeEntity(aliases=["alias1"])
        assert isinstance(e.aliases, list)
        assert all(isinstance(v, str) for v in e.aliases)

    def test_domain_is_string(self):
        e = NarrativeEntity(domain="fantasy")
        assert isinstance(e.domain, str)
