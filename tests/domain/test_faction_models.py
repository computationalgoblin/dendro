"""Tests for B22 domain models — Faction (26c), Front (19c), FrontStage (6c), CampaignClock extended."""

from __future__ import annotations
import pytest
from packages.domain.faction_models import FactionState, FrontType, FrontState, FrontStage, Faction, Front
from packages.domain.campaign_models import CampaignClock


class TestFactionState:
    def test_four(self): assert len(list(FactionState)) == 4

class TestFrontType:
    def test_three(self): assert len(list(FrontType)) == 3

class TestFrontState:
    def test_four(self): assert len(list(FrontState)) == 4

class TestFrontStage:
    def test_minimal(self):
        s = FrontStage(name="Rumores")
        assert s.name == "Rumores"
        assert s.threshold == 0

    def test_full(self):
        s = FrontStage(name="Guerra", threshold=3, description="Abierta", consequences=["c1"], conditions=["cond1"], is_terminal=True)
        assert s.threshold == 3
        assert s.is_terminal

    def test_roundtrip(self):
        s = FrontStage(name="X", threshold=2, description="d", consequences=["a"], conditions=["b"], is_terminal=True)
        s2 = FrontStage.from_dict(s.to_dict())
        assert s2.name == s.name
        assert s2.threshold == s.threshold
        assert s2.is_terminal

class TestFaction:
    def test_minimal(self):
        f = Faction(entity_id="ent_fac_1", name="La Compañía")
        assert f.entity_id == "ent_fac_1"
        assert f.id.startswith("fac_")
        assert f.state == FactionState.activa

    def test_26_fields(self):
        f = Faction(entity_id="e1")
        d = f.to_dict()
        assert len(d) == 26, f"Expected 26 fields, got {len(d)}: {sorted(d.keys())}"

    def test_full(self):
        f = Faction(entity_id="e1", name="Test", objectives=["o1"], resources=["r1"], leader_entity_ids=["l1"],
                    member_entity_ids=["m1"], ally_faction_ids=["f1"], enemy_faction_ids=["f2"],
                    territory_entity_ids=["t1"], plan_ids=["p1"], secret_ids=["s1"], methods=["m"], ideology="i",
                    state=FactionState.debilitada, clock_ids=["c1"], possible_reactions=["r"], relation_with_pcs="rpc",
                    relation_with_factions="rf", event_ids=["ev1"], inaction_consequences=["ic"], intervention_consequences=["ivc"],
                    visibility_state="v", metadata={"k":"v"})
        assert f.state == FactionState.debilitada

    def test_roundtrip(self):
        f = Faction(entity_id="ent_99", name="Round", objectives=["o1"], ally_faction_ids=["f1"], enemy_faction_ids=["f2"], secret_ids=["s1"], clock_ids=["c1"])
        f2 = Faction.from_dict(f.to_dict())
        assert f2.entity_id == f.entity_id
        assert f2.ally_faction_ids == ["f1"]
        assert f2.secret_ids == ["s1"]

class TestFront:
    def test_minimal(self):
        f = Front(name="La Guerra", front_type=FrontType.amenaza)
        assert f.id.startswith("frt_")
        assert f.state == FrontState.latente

    def test_19_fields(self):
        f = Front(name="X")
        d = f.to_dict()
        assert len(d) == 19, f"Expected 19 fields, got {len(d)}"

    def test_with_stages(self):
        s1 = FrontStage(name="Rumores", threshold=2, is_terminal=False)
        s2 = FrontStage(name="Guerra", threshold=4, is_terminal=True)
        f = Front(name="X", stages=[s1, s2], current_stage_index=1)
        d = f.to_dict()
        assert len(d["stages"]) == 2
        f2 = Front.from_dict(d)
        assert len(f2.stages) == 2
        assert f2.stages[1].is_terminal

    def test_roundtrip(self):
        s = FrontStage(name="S1", threshold=3, consequences=["c1"], conditions=["cond1"], is_terminal=True)
        f = Front(name="R", front_type=FrontType.inminente, faction_id="fac_x", clock_id="clk_x",
                  stages=[s], current_stage_index=0, entity_id="ent_e", session_ids=["ses1"], affected_entity_ids=["e1"],
                  history=["h1"], visibility_state="v", metadata={"k":"v"})
        f2 = Front.from_dict(f.to_dict())
        assert f2.faction_id == "fac_x"
        assert f2.clock_id == "clk_x"
        assert len(f2.stages) == 1
        assert f2.history == ["h1"]

class TestCampaignClockExtended:
    def test_extended_fields(self):
        ck = CampaignClock(name="Test", faction_id="fac_x", front_id="frt_x", advance_conditions=["ac"],
                          retreat_conditions=["rc"], stage_consequences=["sc"], session_ids=["s1"],
                          affected_entity_ids=["e1"], history=["h1"])
        assert ck.faction_id == "fac_x"
        assert ck.front_id == "frt_x"
        assert ck.history == ["h1"]

    def test_roundtrip_extended(self):
        ck = CampaignClock(name="Ext", max_value=6, current_value=2, faction_id="fac_x", front_id="frt_y",
                          history=["h1"], session_ids=["s1"])
        ck2 = CampaignClock.from_dict(ck.to_dict())
        assert ck2.faction_id == "fac_x"
        assert ck2.front_id == "frt_y"
        assert ck2.history == ["h1"]

    def test_backward_compat(self):
        ck = CampaignClock.from_dict({"id": "clk_old", "name": "Legacy", "current_value": 2, "max_value": 4, "state": "active"})
        assert ck.faction_id is None
        assert ck.front_id is None
        assert ck.history == []
        assert ck.advance_conditions == []
