"""Tests for B23 session domain models."""

from __future__ import annotations
import pytest
from packages.domain.session_models import SessionState, SceneType, SessionScene, Session
from packages.domain.campaign_models import Campaign

class TestSessionState:
    def test_4(self): assert len(list(SessionState)) == 4

class TestSceneType:
    def test_3(self): assert len(list(SceneType)) == 3

class TestSessionScene:
    def test_minimal(self):
        s = SessionScene(name="Intro"); assert s.id.startswith("scn_"); assert s.scene_type == SceneType.prevista
    def test_8_fields(self):
        s = SessionScene(name="X"); d = s.to_dict()
        assert len(d) == 8, f"Expected 8, got {len(d)}"
    def test_roundtrip(self):
        s = SessionScene(name="Combat", scene_type=SceneType.improvisada, order=2, location_id="loc_1", npc_ids=["n1"], notes="n")
        s2 = SessionScene.from_dict(s.to_dict())
        assert s2.id == s.id; assert s2.order == 2; assert s2.npc_ids == ["n1"]

class TestSession:
    def test_minimal(self):
        s = Session(name="Sesión 1", campaign_id="cam_1")
        assert s.id.startswith("ses_"); assert s.state == SessionState.preparacion
    def test_34_fields(self):
        s = Session(name="X", campaign_id="c1"); d = s.to_dict()
        assert len(d) == 34, f"Expected 34, got {len(d)}"
    def test_with_scenes(self):
        sc = SessionScene(name="S1"); s = Session(name="X", campaign_id="c1", planned_scenes=[sc], optional_scenes=[SessionScene(name="O1")], clock_ids=["clk1"])
        d = s.to_dict(); assert len(d["planned_scenes"]) == 1; assert len(d["optional_scenes"]) == 1; assert d["clock_ids"] == ["clk1"]
        s2 = Session.from_dict(d); assert len(s2.planned_scenes) == 1; assert s2.planned_scenes[0].id == sc.id
    def test_roundtrip(self):
        sc = SessionScene(name="S1", scene_type=SceneType.opcional)
        s = Session(name="R", campaign_id="cam_x", entity_id="ent_ses", session_number=3,
                    planned_scenes=[sc], clock_ids=["ck1"], ia_suggestion_candidate_ids=["cand1"], private_notes=["n1"])
        s2 = Session.from_dict(s.to_dict())
        assert s2.campaign_id == "cam_x"; assert s2.clock_ids == ["ck1"]; assert s2.private_notes == ["n1"]

class TestCampaignSessionIds:
    def test_session_ids_field(self):
        c = Campaign(name="Test", session_ids=["ses_1", "ses_2"])
        assert c.session_ids == ["ses_1", "ses_2"]
        d = c.to_dict(); assert d["session_ids"] == ["ses_1", "ses_2"]
        c2 = Campaign.from_dict(d); assert c2.session_ids == ["ses_1", "ses_2"]
