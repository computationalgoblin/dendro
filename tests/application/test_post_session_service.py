"""Tests for PostSessionService (B25-T04)."""

from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from packages.application.post_session_service import PostSessionService
from packages.application.project_service import ProjectService
from packages.domain.project import Project
from packages.domain.entity import NarrativeEntity, EntityType, CanonState, VisibilityState
from packages.domain.relation import NarrativeRelation
from packages.domain.session_models import Session, SessionState
from packages.domain.result import Ok

def _mk():
    p = Project(name="Test")
    e = NarrativeEntity(name="Orc", entity_type=EntityType.PERSONAJE, canon_state=CanonState.BORRADOR, visibility_state=VisibilityState.VISIBLE_USUARIO)
    p.entities.append(e)
    rel = NarrativeRelation(source_id="e1", target_id="e2", relation_type="ubicado_en", canon_state=CanonState.BORRADOR)
    p.relations.append(rel)
    s = Session(name="S1", campaign_id="cam_1")
    s.metadata["live"] = {"quick_notes": ["n1"], "player_decisions": ["d1"], "events": ["e1"], "consequences": ["c1"],
                          "provisional_entity_ids": [e.id], "provisional_relation_ids": [rel.id],
                          "clues_delivered": ["c1"], "secrets_revealed": ["s1"], "improvisations": [{"name":"imp1","description":"d"}]}
    p.sessions.append(s)
    ps = MagicMock(spec=ProjectService); ps.active_project = p
    ss = MagicMock(); ss.get_session.return_value = Ok(s)
    cs = MagicMock(); cs.add_candidate.return_value = None
    hs = MagicMock(); hs.record.return_value = None
    svc = PostSessionService(project_service=ps, session_service=ss, candidate_service=cs, history_service=hs)
    return p, svc, s

class TestPostSessionService:
    def test_close_session(self):
        _, svc, s = _mk(); r = svc.close_session(s.id)
        assert isinstance(r, Ok); assert r.value.state == SessionState.completada
        assert r.value.post_session_summary != ""
    def test_convert_live_to_candidates(self):
        _, svc, s = _mk(); r = svc.convert_live_to_candidates(s.id)
        assert isinstance(r, Ok); assert len(r.value) > 0
    def test_idempotent(self):
        _, svc, s = _mk(); r1 = svc.convert_live_to_candidates(s.id)
        r2 = svc.convert_live_to_candidates(s.id)
        assert len(r2.value) == 0  # second run: no new candidates
    def test_provisional_entity_cambio_estado(self):
        p, svc, s = _mk(); cs = svc.candidate_service
        r = svc.convert_live_to_candidates(s.id)
        # Find the provisional entity candidate
        found = False
        for call in cs.add_candidate.call_args_list:
            c = call[0][0]
            if c.metadata.get("source_live_key","").startswith("provisional_entity:"):
                assert c.proposed_data.get("target_entity_id") == p.entities[0].id
                assert c.proposed_data["to_canon_state"] == "canonico"
                found = True
        assert found, "Should have CAMBIO_ESTADO candidate for provisional entity"
    def test_clue_not_candidate(self):
        _, svc, s = _mk(); cs = svc.candidate_service
        svc.convert_live_to_candidates(s.id)
        for call in cs.add_candidate.call_args_list:
            c = call[0][0]
            assert not c.metadata.get("source_live_key","").startswith("clues_delivered")
    def test_private_summary(self):
        _, svc, s = _mk(); r = svc.generate_private_summary(s.id)
        assert isinstance(r, Ok); assert "Notes: 1" in r.value
    def test_public_summary(self):
        _, svc, s = _mk(); r = svc.generate_public_summary(s.id)
        assert isinstance(r, Ok)
    def test_seeds(self):
        _, svc, s = _mk(); seeds = svc.generate_next_session_seeds(s.id)
        assert len(seeds) > 0
