"""Tests for HistoryService + RelationType extend (B25-T00)."""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from packages.application.history_service import HistoryService, HistoryEntry
from packages.application.project_service import ProjectService
from packages.domain.project import Project
from packages.domain.relation import RelationType
from packages.domain.result import Ok

class TestHistoryService:
    def test_record_and_get(self):
        p = Project(name="Test"); ps = MagicMock(spec=ProjectService); ps.active_project = p
        hs = HistoryService(project_service=ps)
        hs.record("test", "hello", affected_entity_ids=["e1"], metadata={"k":"v"})
        entries = hs.get_history(entity_id="e1")
        assert len(entries) == 1; assert entries[0].description == "hello"
    def test_get_by_object(self):
        p = Project(name="Test"); ps = MagicMock(spec=ProjectService); ps.active_project = p
        hs = HistoryService(project_service=ps)
        hs.record("campaign_created", "C", metadata={"object_type":"campaign","object_id":"c1"})
        assert len(hs.get_history(object_type="campaign")) == 1
        assert len(hs.get_history(object_id="c1")) == 1
    def test_no_duplicate_collection(self):
        p = Project(name="Test"); ps = MagicMock(spec=ProjectService); ps.active_project = p
        hs = HistoryService(project_service=ps)
        hs.record("test", "x")
        # history_entries is added to project without schema bump
        assert hasattr(p, 'history_entries')
        assert isinstance(p.history_entries, list)

    def test_observation_recorrido_round_trips(self):
        """PLAY-18: el tipo nuevo se graba, filtra y round-trippea sin migración."""
        from packages.domain.source_history import HistoryEntry as DomainEntry
        from packages.domain.source_history import HistoryEventType

        p = Project(name="Test"); ps = MagicMock(spec=ProjectService); ps.active_project = p
        hs = HistoryService(project_service=ps)
        hs.record(
            HistoryEventType.OBSERVACION_RECORRIDO,
            "Lectura del hito",
            affected_entity_ids=["e1"],
            change_origin="recorrido_cronologico",
            metadata={"milestone_id": "h1"},
        )
        entries = hs.get_history(
            entity_id="e1", event_type=HistoryEventType.OBSERVACION_RECORRIDO
        )
        assert len(entries) == 1
        revived = DomainEntry.from_dict(entries[0].to_dict())
        assert revived.event_type is HistoryEventType.OBSERVACION_RECORRIDO
        assert revived.change_origin == "recorrido_cronologico"

    def test_unknown_event_type_falls_back_without_error(self):
        """PLAY-18: un dict con event_type desconocido (proyecto viejo) no explota."""
        from packages.domain.source_history import HistoryEntry as DomainEntry
        from packages.domain.source_history import HistoryEventType

        revived = DomainEntry.from_dict({"event_type": "tipo_futuro_desconocido"})
        assert revived.event_type is HistoryEventType.CREACION_ENTIDAD  # fallback tolerante

class TestRelationTypeExtended:
    def test_11_new_values(self):
        values = RelationType._value2member_map_
        assert "sabe" in values
        assert "cree" in values
        assert "ignora" in values
        assert "malinterpreta" in values
        assert "ha_oido" in values
        assert "ha_visto" in values
        assert "ha_recibido_pista" in values
        assert "conoce_parcialmente" in values
        assert "conoce_falsamente" in values
        assert "posee_conocimiento" in values
        assert "revela_conocimiento" in values
