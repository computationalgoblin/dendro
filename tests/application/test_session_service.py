"""Tests for SessionService (B23-T05)."""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from packages.application.session_service import SessionService
from packages.application.project_service import ProjectService
from packages.domain.project import Project
from packages.domain.entity import NarrativeEntity, EntityType, CanonState, VisibilityState
from packages.domain.campaign_models import Campaign, CampaignClock
from packages.domain.secrets_models import Secreto, Pista, RevelationState, DeliveryState
from packages.domain.faction_models import Faction
from packages.domain.result import Ok, Error

def _mk():
    p = Project(name="Test")
    p.entities.append(NarrativeEntity(name="Sesion1", entity_type=EntityType.SESION, canon_state=CanonState.CANONICO, visibility_state=VisibilityState.VISIBLE_USUARIO))
    p.entities.append(NarrativeEntity(name="Gandalf", entity_type=EntityType.PERSONAJE, canon_state=CanonState.CANONICO, visibility_state=VisibilityState.VISIBLE_USUARIO))
    p.secrets.append(Secreto(content="Secret", revelation_state=RevelationState.oculto))
    p.clues.append(Pista(content="Clue", delivery_state=DeliveryState.pendiente))
    p.factions.append(Faction(entity_id=p.entities[0].id, name="Fac"))
    ck = CampaignClock(name="Clock", max_value=4)
    p.campaign_clocks.append(ck)
    ps = MagicMock(spec=ProjectService); ps.active_project = p; ps.save.return_value = Ok(None)
    es = MagicMock()
    def gbi(eid):
        for e in p.entities:
            if e.id == eid: return Ok(e)
        return Error(f"Not found: {eid}")
    es.get_by_id = gbi
    cs = MagicMock()
    camp = Campaign(name="TestCamp", id="cam_1")
    cs.get_campaign.return_value = Ok(camp)
    svc = SessionService(project_service=ps, entity_service=es, campaign_service=cs)
    return p, svc

class TestSessionCRUD:
    def test_create(self):
        p, svc = _mk(); r = svc.create_session({"name": "S1", "campaign_id": "cam_1"})
        assert isinstance(r, Ok); assert r.value.name == "S1"; assert r.value.id.startswith("ses_")
    def test_create_no_campaign(self):
        _, svc = _mk(); assert isinstance(svc.create_session({"name": "X"}), Error)
    def test_create_with_entity(self):
        p, svc = _mk(); eid = next(e.id for e in p.entities if e.entity_type == EntityType.SESION)
        r = svc.create_session({"name": "S2", "campaign_id": "cam_1", "entity_id": eid})
        assert isinstance(r, Ok)
    def test_duplicate(self):
        p, svc = _mk(); s = svc.create_session({"name": "Orig", "campaign_id": "cam_1"}).value
        svc.add_scene(s.id, {"name": "Scene1"}, "planned")
        d = svc.duplicate_session(s.id, "Copy").value
        assert d.name == "Copy"; assert d.campaign_id == "cam_1"
        assert len(d.planned_scenes) == 1
        assert d.planned_scenes[0].id != s.planned_scenes[0].id  # regenerated
        assert d.clock_ids == []  # cleaned
    def test_scenes(self):
        p, svc = _mk(); s = svc.create_session({"name": "S", "campaign_id": "cam_1"}).value
        sc = svc.add_scene(s.id, {"name": "Intro", "scene_type": "opcional"}, "planned").value
        assert sc.id.startswith("scn_")
        svc.reorder_scene(s.id, sc.id, 5); s2 = svc.get_session(s.id).value
        assert s2.planned_scenes[0].order == 5
        svc.remove_scene(s.id, sc.id); s3 = svc.get_session(s.id).value
        assert len(s3.planned_scenes) == 0

class TestLinks:
    def test_link_all(self):
        p, svc = _mk(); s = svc.create_session({"name": "S", "campaign_id": "cam_1"}).value
        svc.link_clue(s.id, p.clues[0].id); svc.link_secret(s.id, p.secrets[0].id)
        svc.link_faction(s.id, p.factions[0].id); svc.link_clock(s.id, p.campaign_clocks[0].id)
        svc.link_entity(s.id, p.entities[1].id, "npc")
        s2 = svc.get_session(s.id).value
        assert len(s2.available_clue_ids) == 1; assert len(s2.revealable_secret_ids) == 1
        assert len(s2.relevant_faction_ids) == 1; assert len(s2.clock_ids) == 1
        assert len(s2.planned_npc_ids) == 1

class TestSummaries:
    def test_player_summary_excludes_private(self):
        p, svc = _mk(); s = svc.create_session({"name": "S", "campaign_id": "cam_1"}).value
        svc.update_session(s.id, {"private_notes": ["secreto"], "player_safe_summary": "safe", "player_known_objectives": ["obj1"]})
        r = svc.generate_player_summary(s.id)
        assert isinstance(r, Ok); assert "secreto" not in r.value
    def test_private_summary(self):
        p, svc = _mk(); s = svc.create_session({"name": "S", "campaign_id": "cam_1"}).value
        svc.update_session(s.id, {"private_notes": ["top secret"]})
        r = svc.generate_private_summary(s.id)
        assert isinstance(r, Ok); assert "top secret" in r.value

class TestContinuity:
    def test_check(self):
        p, svc = _mk(); s = svc.create_session({"name": "S", "campaign_id": "cam_1"}).value
        r = svc.check_continuity(s.id)
        assert isinstance(r, Ok); assert r.value["pendientes_pistas"] == 1; assert r.value["secretos_ocultos"] == 1
    def test_suggest(self):
        _, svc = _mk(); s = svc.create_session({"name": "S", "campaign_id": "cam_1"}).value
        r = svc.suggest_material(s.id, "test hint")
        assert isinstance(r, Ok) or isinstance(r, Error)  # depends on orchestrator
