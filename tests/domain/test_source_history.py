"""Tests for B05-T01: Source and HistoryEntry domain models."""

from datetime import datetime, timezone

from packages.domain.source_history import (
    HistoryEntry,
    HistoryEventType,
    Source,
    SourceState,
    SourceType,
)


class TestSourceType:
    def test_has_10_values(self):
        assert len(SourceType) == 10


class TestSourceState:
    def test_has_2_values(self):
        assert len(SourceState) == 2
        assert SourceState.ACTIVA.value == "activa"
        assert SourceState.ARCHIVADA.value == "archivada"


class TestHistoryEventType:
    def test_has_20_values(self):
        # 16 originales (§5.4) + 4 del jardín BETA2-FOCO (riego/secado/cultivo/descarte fantasma).
        assert len(HistoryEventType) == 20


class TestSource:
    def test_defaults(self):
        s = Source()
        assert s.source_type == SourceType.ENTRADA_MANUAL
        assert s.state == SourceState.ACTIVA
        assert s.name == ""
        assert s.derived_entity_ids == []
        assert s.derived_relation_ids == []

    def test_id_unique(self):
        s1 = Source()
        s2 = Source()
        assert s1.id != s2.id

    def test_11_fields(self):
        s = Source(name="Test")
        d = s.to_dict()
        assert len(d) == 11, f"Expected 11, got {len(d)}: {list(d.keys())}"

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        s = Source(
            id="s1",
            source_type=SourceType.DOCUMENTO_IMPORTADO,
            name="LotR Appendix",
            description="Tolkien's notes",
            reference="lotr_appendix_v2.pdf",
            fragment="Chapter 3, page 42",
            incorporated_at=now,
            state=SourceState.ARCHIVADA,
            metadata={"import_date": "2026-01-01"},
            derived_entity_ids=["e1", "e2"],
            derived_relation_ids=["r1"],
        )
        assert s.source_type == SourceType.DOCUMENTO_IMPORTADO
        assert s.state == SourceState.ARCHIVADA
        assert s.derived_entity_ids == ["e1", "e2"]

    def test_roundtrip(self):
        s1 = Source(
            name="Test Source",
            source_type=SourceType.SESION_ROL,
            description="Created during game session",
            reference="session_42",
            derived_entity_ids=["e1"],
        )
        d = s1.to_dict()
        s2 = Source.from_dict(d)
        assert s2.name == s1.name
        assert s2.source_type == s1.source_type
        assert s2.derived_entity_ids == s1.derived_entity_ids

    def test_from_dict_partial(self):
        d = {"name": "Partial", "source_type": "generacion_ia"}
        s = Source.from_dict(d)
        assert s.name == "Partial"
        assert s.source_type == SourceType.GENERACION_IA
        assert s.description == ""
        assert s.state == SourceState.ACTIVA  # default

    def test_from_dict_invalid_enum(self):
        s = Source.from_dict({"source_type": "nonexistent"})
        assert s.source_type == SourceType.ENTRADA_MANUAL

    def test_from_dict_empty(self):
        s = Source.from_dict({})
        assert s.id != ""
        assert s.name == ""


class TestHistoryEntry:
    def test_defaults(self):
        h = HistoryEntry()
        assert h.event_type == HistoryEventType.CREACION_ENTIDAD
        assert h.affected_entity_id is None
        assert h.affected_relation_id is None
        assert h.reversible is False

    def test_id_unique(self):
        h1 = HistoryEntry()
        h2 = HistoryEntry()
        assert h1.id != h2.id

    def test_14_fields(self):
        h = HistoryEntry()
        d = h.to_dict()
        assert len(d) == 14, f"Expected 14, got {len(d)}: {list(d.keys())}"

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        h = HistoryEntry(
            id="h1",
            event_type=HistoryEventType.CAMBIO_CANON,
            timestamp=now,
            affected_entity_id="e1",
            previous_value="borrador",
            new_value="canonico",
            change_origin="EntityService.change_canon_state",
            reason="DM decision",
            operation="change_canon",
            responsible="DM",
            reversible=True,
            metadata={"session": "42"},
        )
        assert h.affected_entity_id == "e1"
        assert h.affected_relation_id is None
        assert h.affected_source_id is None
        assert h.previous_value == "borrador"

    def test_roundtrip(self):
        h1 = HistoryEntry(
            event_type=HistoryEventType.ARCHIVADO_ENTIDAD,
            affected_entity_id="e1",
            previous_value="borrador",
            new_value="archivado",
            change_origin="manual",
            reason="obsolete",
        )
        d = h1.to_dict()
        h2 = HistoryEntry.from_dict(d)
        assert h2.event_type == h1.event_type
        assert h2.affected_entity_id == h1.affected_entity_id
        assert h2.previous_value == "borrador"

    def test_previous_value_accepts_dict(self):
        h = HistoryEntry(
            previous_value={"canon": "borrador", "visibility": "visible_usuario"},
            new_value={"canon": "canonico"},
        )
        d = h.to_dict()
        h2 = HistoryEntry.from_dict(d)
        assert h2.previous_value == {"canon": "borrador", "visibility": "visible_usuario"}

    def test_previous_value_accepts_list(self):
        h = HistoryEntry(previous_value=["tag1", "tag2"], new_value=["tag1"])
        d = h.to_dict()
        h2 = HistoryEntry.from_dict(d)
        assert h2.previous_value == ["tag1", "tag2"]

    def test_from_dict_partial(self):
        d = {"event_type": "creacion_relacion", "affected_relation_id": "r1"}
        h = HistoryEntry.from_dict(d)
        assert h.event_type == HistoryEventType.CREACION_RELACION
        assert h.affected_relation_id == "r1"
        assert h.affected_entity_id is None

    def test_from_dict_empty(self):
        h = HistoryEntry.from_dict({})
        assert h.id != ""


class TestBackwardCompat:
    """Source objects coexist with origin/source strings in entities/relations."""

    def test_source_does_not_replace_entity_origin(self):
        from packages.domain.entity import NarrativeEntity
        e = NarrativeEntity(origin="Manual creation")
        assert isinstance(e.origin, str)
        assert e.origin == "Manual creation"
