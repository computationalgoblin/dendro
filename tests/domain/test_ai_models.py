"""Tests for AI domain models (B15-T01)."""
from packages.domain.ai_models import AIMode, AuthorizedContext, AIOperation, AIResponse

class TestAIMode:
    def test_8_values(self):
        assert len(AIMode) == 8
        assert AIMode.GENERATE_ENTITY.value == "generate_entity"

class TestAuthorizedContext:
    def test_defaults(self):
        ctx = AuthorizedContext()
        assert ctx.audience == "author"
        assert ctx.output_profile == "default"
        assert ctx.context_entities == []

    def test_roundtrip(self):
        ctx = AuthorizedContext(project_name="P", audience="player", selected_entity_ids=["e1"])
        d = ctx.to_dict()
        c2 = AuthorizedContext.from_dict(d)
        assert c2.project_name == "P"
        assert c2.audience == "player"
        assert "e1" in c2.selected_entity_ids

    def test_from_dict_partial(self):
        ctx = AuthorizedContext.from_dict({})
        assert ctx.audience == "author"
        assert ctx.allowed_canon_states == []

class TestAIOperation:
    def test_roundtrip(self):
        op = AIOperation(mode=AIMode.EXPAND_ENTITY, entity_id="e1", max_candidates=5)
        d = op.to_dict()
        o2 = AIOperation.from_dict(d)
        assert o2.mode == AIMode.EXPAND_ENTITY
        assert o2.entity_id == "e1"
        assert o2.max_candidates == 5

class TestAIResponse:
    def test_roundtrip(self):
        op = AIOperation()
        resp = AIResponse(id="r1", operation=op, raw_text="hello", provider="simulated", latency_ms=12.5)
        d = resp.to_dict()
        r2 = AIResponse.from_dict(d)
        assert r2.id == "r1"
        assert r2.raw_text == "hello"
        assert r2.latency_ms == 12.5
