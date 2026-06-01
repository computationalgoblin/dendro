"""Tests for LiveModeService (B24-T03)."""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from packages.application.live_mode_service import LiveModeService, LiveMaterialState
from packages.application.project_service import ProjectService
from packages.application.secrets_service import SecretsService
from packages.domain.project import Project
from packages.domain.entity import NarrativeEntity, EntityType, CanonState, VisibilityState
from packages.domain.session_models import Session, SessionState
from packages.domain.secrets_models import Secreto, Pista, RevelationState, DeliveryState
from packages.domain.faction_models import Faction
from packages.domain.campaign_models import CampaignClock
from packages.domain.result import Ok, Error

def _mk():
    p = Project(name="Test")
    p.entities.append(NarrativeEntity(name="Gandalf", entity_type=EntityType.PERSONAJE, canon_state=CanonState.CANONICO, visibility_state=VisibilityState.VISIBLE_USUARIO))
    p.entities.append(NarrativeEntity(name="Rivendel", entity_type=EntityType.LOCALIZACION, canon_state=CanonState.CANONICO, visibility_state=VisibilityState.VISIBLE_USUARIO))
    secret = Secreto(content="Secret", revelation_state=RevelationState.oculto, visibility_state="visible_usuario")
    p.secrets.append(secret)
    clue = Pista(content="Clue", delivery_state=DeliveryState.pendiente)
    p.clues.append(clue)
    p.factions.append(Faction(entity_id=p.entities[0].id, name="Fac"))
    ck = CampaignClock(name="Clock", max_value=4)
    p.campaign_clocks.append(ck)
    session = Session(name="S1", campaign_id="cam_1", planned_npc_ids=[p.entities[0].id], planned_location_ids=[p.entities[1].id],
                      revealable_secret_ids=[secret.id], available_clue_ids=[clue.id],
                      relevant_faction_ids=[p.factions[0].id], clock_ids=[ck.id])
    p.sessions.append(session)
    ps = MagicMock(spec=ProjectService); ps.active_project = p; ps.save.return_value = Ok(None)
    ss = MagicMock(); ss.get_session.return_value = Ok(session)
    sec = MagicMock(spec=SecretsService); sec.deliver_clue.return_value = Ok(clue); sec.reveal_secret.return_value = Ok(secret)
    svc = LiveModeService(project_service=ps, session_service=ss, secrets_service=sec)
    return p, svc, session

class TestLiveModeService:
    def test_activate(self):
        _, svc, s = _mk(); r = svc.activate_session(s.id)
        assert isinstance(r, Ok); assert r.value.state == SessionState.activa
    def test_queries(self):
        _, svc, s = _mk()
        assert len(svc.query_npcs(s.id)) == 1; assert len(svc.query_locations(s.id)) == 1
        assert len(svc.query_secrets(s.id)) == 1; assert len(svc.query_clues(s.id)) == 1
        assert len(svc.query_factions(s.id)) == 1; assert len(svc.query_clocks(s.id)) == 1
    def test_quick_note(self):
        _, svc, s = _mk(); svc.quick_note(s.id, "test note")
        assert "test note" in s.metadata["live"]["quick_notes"]
    def test_provisional_entity_borrador(self):
        _, svc, s = _mk(); r = svc.create_provisional_entity(s.id, "Orc", "personaje")
        assert isinstance(r, Ok); e = r.value
        assert e.canon_state == CanonState.BORRADOR
        assert e.custom_metadata.get("live_material_state") == "provisional_de_sesion"
        assert e.custom_metadata.get("session_id") == s.id
        assert s.metadata["live"]["provisional_entity_ids"] == [e.id]
    def test_provisional_entity_canon(self):
        _, svc, s = _mk(); r = svc.create_provisional_entity(s.id, "Elf", "personaje", force_canon=True)
        assert r.value.canon_state == CanonState.CANONICO
        assert r.value.custom_metadata.get("live_material_state") == "canon_inmediato"
    def test_provisional_relation(self):
        _, svc, s = _mk(); p = svc._proj()
        r = svc.create_provisional_relation(s.id, p.entities[0].id, p.entities[1].id, "ubicado_en")
        assert isinstance(r, Ok); rel = r.value
        assert rel.canon_state == CanonState.BORRADOR
        assert rel.custom_metadata.get("session_id") == s.id
        assert s.metadata["live"]["provisional_relation_ids"] == [rel.id]
    def test_mark_clue_delivered(self):
        p, svc, s = _mk(); svc.mark_clue_delivered(s.id, p.clues[0].id)
        assert p.clues[0].id in s.metadata["live"]["clues_delivered"]
    def test_mark_secret_revealed(self):
        p, svc, s = _mk(); svc.mark_secret_revealed(s.id, p.secrets[0].id, "parcialmente_revelado")
        assert p.secrets[0].id in s.metadata["live"]["secrets_revealed"]
    def test_prepare_post_session(self):
        _, svc, s = _mk(); svc.quick_note(s.id, "n1"); svc.register_player_decision(s.id, "d1")
        r = svc.prepare_post_session(s.id)
        assert isinstance(r, Ok); data = r.value
        assert data["quick_notes"] == ["n1"]; assert data["player_decisions"] == ["d1"]
        assert s.state == SessionState.preparacion
    def test_improvise_no_save(self):
        _, svc, s = _mk(); r = svc.improvise(s.id, "test")
        assert isinstance(r, Ok); assert "name" in r.value
    def test_improvise_save(self):
        _, svc, s = _mk(); svc.improvise(s.id, "test", save=True)
        assert len(s.metadata["live"]["improvisations"]) == 1
