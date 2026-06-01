"""Tests for FactionService (B22-T03)."""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from packages.application.faction_service import FactionService
from packages.application.project_service import ProjectService
from packages.domain.project import Project
from packages.domain.entity import NarrativeEntity, EntityType, CanonState, VisibilityState
from packages.domain.campaign_models import CampaignClock
from packages.domain.result import Ok, Error

def _mk():
    p = Project(name="Test")
    for n, t in [("La Compañía", EntityType.FACCION), ("Mordor", EntityType.FACCION), ("Gandalf", EntityType.PERSONAJE)]:
        p.entities.append(NarrativeEntity(name=n, entity_type=t, canon_state=CanonState.CANONICO, visibility_state=VisibilityState.VISIBLE_USUARIO))
    ps = MagicMock(spec=ProjectService); ps.active_project = p; ps.save.return_value = Ok(None)
    es = MagicMock()
    def gbi(eid):
        for e in p.entities:
            if e.id == eid: return Ok(e)
        return Error(f"Not found: {eid}")
    es.get_by_id = gbi
    fs = FactionService(project_service=ps, entity_service=es)
    return p, ps, es, fs

class TestFactionCRUD:
    def test_create_ok(self):
        p, ps, es, fs = _mk(); eid = p.entities[0].id
        r = fs.create_faction({"name": "Test", "entity_id": eid})
        assert isinstance(r, Ok); assert r.value.name == "Test"
    def test_create_no_entity(self):
        _, _, _, fs = _mk(); assert isinstance(fs.create_faction({"name": "X"}), Error)
    def test_create_wrong_type(self):
        p, _, _, fs = _mk(); gid = next(e.id for e in p.entities if e.entity_type == EntityType.PERSONAJE)
        assert isinstance(fs.create_faction({"name": "X", "entity_id": gid}), Error)
    def test_duplicate_entity(self):
        p, _, _, fs = _mk(); eid = p.entities[0].id
        fs.create_faction({"name": "A", "entity_id": eid})
        assert isinstance(fs.create_faction({"name": "B", "entity_id": eid}), Error)
    def test_archive(self):
        p, _, _, fs = _mk(); f = fs.create_faction({"name": "X", "entity_id": p.entities[0].id}).value
        fs.archive_faction(f.id)
        assert fs.get_faction(f.id).value.state.value == "inactiva"

class TestAlliesEnemies:
    def test_ally_symmetric(self):
        p, _, _, fs = _mk()
        e1, e2 = p.entities[0].id, p.entities[1].id
        f1 = fs.create_faction({"name": "A", "entity_id": e1}).value
        f2 = fs.create_faction({"name": "B", "entity_id": e2}).value
        fs.add_ally(f1.id, f2.id)
        assert f2.id in fs.get_faction(f1.id).value.ally_faction_ids
        assert f1.id in fs.get_faction(f2.id).value.ally_faction_ids
    def test_ally_self_error(self):
        p, _, _, fs = _mk(); f = fs.create_faction({"name": "A", "entity_id": p.entities[0].id}).value
        assert isinstance(fs.add_ally(f.id, f.id), Error)
    def test_remove_ally(self):
        p, _, _, fs = _mk()
        f1 = fs.create_faction({"name": "A", "entity_id": p.entities[0].id}).value
        f2 = fs.create_faction({"name": "B", "entity_id": p.entities[1].id}).value
        fs.add_ally(f1.id, f2.id); fs.remove_ally(f1.id, f2.id)
        assert f2.id not in fs.get_faction(f1.id).value.ally_faction_ids

class TestFronts:
    def test_advance_retreat(self):
        _, _, _, fs = _mk(); f = fs.create_front({"name": "Test"}).value
        fs.add_stage(f.id, {"name": "S1", "threshold": 1})
        fs.add_stage(f.id, {"name": "S2", "threshold": 2, "is_terminal": True})
        r = fs.advance_front(f.id)
        assert r.value.current_stage_index == 1
        r2 = fs.advance_front(f.id)
        # Second advance should error (no more stages)
        assert isinstance(r2, Error)
        # Retreat back to stage 0
        r3 = fs.retreat_front(f.id)
        assert r3.value.current_stage_index == 0
    def test_advance_last_error(self):
        _, _, _, fs = _mk(); f = fs.create_front({"name": "T"}).value
        fs.add_stage(f.id, {"name": "S1"})
        fs.advance_front(f.id)
        assert isinstance(fs.advance_front(f.id), Error)
    def test_retreat_first_error(self):
        _, _, _, fs = _mk(); f = fs.create_front({"name": "T"}).value
        assert isinstance(fs.retreat_front(f.id), Error)

class TestClocks:
    def test_assign_bidirectional(self):
        p, _, _, fs = _mk()
        f = fs.create_faction({"name": "A", "entity_id": p.entities[0].id}).value
        ck = CampaignClock(name="C", max_value=4)
        p.campaign_clocks.append(ck)
        r = fs.assign_clock_to_faction(ck.id, f.id)
        assert isinstance(r, Ok); assert ck.faction_id == f.id; assert ck.id in fs.get_faction(f.id).value.clock_ids
    def test_advance_with_reason(self):
        p, _, _, fs = _mk()
        ck = CampaignClock(name="C", max_value=6)
        p.campaign_clocks.append(ck)
        fs.advance_faction_clock(ck.id, by=2, reason="Progreso")
        assert ck.current_value == 2; assert len(ck.history) == 1; assert "Progreso" in ck.history[0]
    def test_link_front_to_clock(self):
        p, _, _, fs = _mk()
        f = fs.create_front({"name": "F"}).value
        ck = CampaignClock(name="C", max_value=4)
        p.campaign_clocks.append(ck)
        fs.link_front_to_clock(f.id, ck.id)
        assert f.clock_id == ck.id; assert ck.front_id == f.id
    def test_link_clock_already_linked(self):
        p, _, _, fs = _mk()
        f1 = fs.create_front({"name": "F1"}).value
        f2 = fs.create_front({"name": "F2"}).value
        ck = CampaignClock(name="C", max_value=4)
        p.campaign_clocks.append(ck)
        fs.link_front_to_clock(f1.id, ck.id)
        assert isinstance(fs.link_front_to_clock(f2.id, ck.id), Error)

class TestDetection:
    def test_idempotent(self):
        p, _, _, fs = _mk(); eid = p.entities[0].id
        fs.create_faction({"name": "NoObj", "entity_id": eid})
        i1 = fs.run_faction_validation(); assert len(i1) >= 1
        i2 = fs.run_faction_validation(); assert len(i2) == 0
    def test_find_fronts_without_stages(self):
        _, _, _, fs = _mk(); fs.create_front({"name": "NoStages"})
        assert len(fs.find_fronts_without_stages()) == 1
